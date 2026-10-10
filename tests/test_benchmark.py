import json

import httpx
import pytest

from problem_hunter.benchmark import compare, metrics, ranking, revised_priority, revised_questions, validate_records, write_comparison
from problem_hunter.http import HTTP
from problem_hunter.storage import Store


def payload(unknown=(), relevance="yes", kind="experienced_problem", genuine=.95):
    answers = {}
    for name, q in revised_questions().items():
        if q["type"] == "noul":
            answers[name] = {"type": "noul", "noul": genuine, "confidence": .9}
        elif q["type"] == "score":
            answers[name] = {"type": "score", "score": 3, "confidence": .8, "probabilities": {"3": 1}}
        else:
            value = "unknown" if name == "payment_signal" or name.removesuffix("_availability") in unknown else "known"
            value = {"relevance": relevance, "report_kind": kind}.get(name, value)
            answers[name] = {"type": "choice", "choice": value, "confidence": .8}
    return {"answers": answers, "model": "jev-test", "usage": {"input_tokens": 100, "output_tokens": 10}}


def record(identifier="r1", priority=3, split="development"):
    return {"id": identifier, "url": "https://example.com/" + identifier, "title": "Invoices", "content": "I manually track invoices in a spreadsheet and waste hours chasing unpaid invoices.", "author": "Alice", "source": "forum", "annotation": {"relevance": "relevant", "priority": priority, "reason": "Recurring costly invoice work", "split": split}}


def test_unknown_dimensions_do_not_become_zero_or_payment_probability():
    result = revised_priority(payload(unknown=("workaround_burden", "replacement_motivation")))
    assert result["score"] == 100
    assert result["coverage_weight"] == 45
    assert result["dimensions"]["replacement_motivation"] is None
    assert result["payment_signal"] == "unknown"
    assert "unknown" in result["payment_hypothesis"]


@pytest.mark.parametrize("kwargs", [{"relevance": "adjacent"}, {"kind": "advice_or_promotion"}, {"kind": "no_problem_or_hypothetical"}, {"genuine": .59}, {"unknown": ("pain", "workaround_burden", "replacement_motivation")}])
def test_gates(kwargs):
    assert not revised_priority(payload(**kwargs))["accepted"]


def test_invalid_score_rejected():
    response = payload()
    response["answers"]["pain"]["score"] = float("nan")
    with pytest.raises(ValueError):
        revised_priority(response)


def test_metrics_and_coverage_order():
    rows = []
    for i in range(12):
        row = record(str(i), priority=3 if i < 8 else 0)
        row["revised"] = revised_priority(payload())
        row["revised"]["score"] = 99 - i
        rows.append(row)
    rows[0]["revised"]["supported_dimensions"] = ["pain"]
    ordered = ranking(rows, "revised")
    assert ordered[-1]["id"] == "0"
    result = metrics(rows, "revised")
    assert result["precision_at_10"] == .7
    assert result["useful_recall_at_10"] == 7 / 8
    assert result["promising_misses"] == ["0"]
    assert 0 < result["ndcg_at_10"] < 1


def test_manual_annotations_required_and_ids_unique():
    with pytest.raises(ValueError):
        validate_records([record(), record()])
    row = record()
    del row["annotation"]
    with pytest.raises(ValueError):
        validate_records([row])


@pytest.mark.asyncio
async def test_compare_exact_baseline_cache_and_traceable_report(tmp_path):
    requests = []
    def handle(request):
        body = json.loads(request.content)
        requests.append(body)
        assert "annotation" not in json.dumps(body)
        if "0_genuine" not in body["questions"]:
            return httpx.Response(200, json=payload())
        from problem_hunter.intelligence import FIELDS
        answers = {"0_" + name: {"type": "noul", "noul": .95} for name in FIELDS}
        answers.update({"0_severity": {"type": "score", "score": 3}, "0_category": {"type": "choice", "choice": "services"}})
        return httpx.Response(200, json={"answers": answers, "model": "jev-test", "usage": {"input_tokens": 80}})
    with Store(str(tmp_path / "cache.db")) as store:
        async with HTTP(store, transport=httpx.MockTransport(handle), rate=0, prices={"jev": .042}) as http:
            result = await compare([record()], http, "secret")
            repeated = await compare([record()], http, "secret")
    assert len(requests) == 2
    assert result["accounting"]["requests"] == 2
    assert repeated["accounting"]["requests"] == 0
    assert repeated["accounting"]["estimated_cost_usd"] == 0
    assert result["records"][0]["baseline"]["score"] == 22.75  # 18.75 pain + 4 frequency, no literal payment
    assert repeated["records"][0]["revised"]["raw_response"] == result["records"][0]["revised"]["raw_response"]
    assert result["methodology"]["rubric_version"] == "v1"
    paths = write_comparison(result, tmp_path / "report")
    assert all(p.exists() for p in paths)
    assert "https://example.com/r1" in paths[1].read_text()
    assert "confidence" in paths[0].read_text()
    assert result["metrics"]["holdout"]["revised"]["useful_recall_at_10"] is None


@pytest.mark.asyncio
async def test_api_failures_reported_separately_and_wrapper_metadata(tmp_path):
    def handle(request):
        return httpx.Response(200, json={"unexpected": "shape"})
    with Store(str(tmp_path / "cache.db")) as store:
        async with HTTP(store, transport=httpx.MockTransport(handle), rate=0) as http:
            result = await compare({"records": [record()], "metadata": {"reviewer": "developer"}}, http, "secret")
    assert result["dataset_metadata"] == {"reviewer": "developer"}
    assert result["metrics"]["all"]["baseline"]["failed_ids"] == ["r1"]
    assert result["metrics"]["all"]["baseline"]["rejected"] == 0
    assert len(result["fingerprints"]["dataset_sha256"]) == 64
    write_comparison(result, tmp_path / "failed-report")


@pytest.mark.asyncio
async def test_collector_top_level_metadata_preserved(tmp_path):
    with Store(str(tmp_path / "cache.db")) as store:
        async with HTTP(store, transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})), rate=0) as http:
            result = await compare({"records": [record()], "reviewer": "engineer", "limitations": ["historical"]}, http, "secret")
    assert result["dataset_metadata"] == {"reviewer": "engineer", "limitations": ["historical"]}
