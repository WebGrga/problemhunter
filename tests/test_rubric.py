import json

import httpx
import pytest

from problem_hunter.benchmark import compare, main, revised_priority
from problem_hunter.http import HTTP
from problem_hunter.rubric import load_rubric, readable_rubric, rubric_hash, snapshot, validate_rubric
from problem_hunter.storage import Store
from test_benchmark import record


def v2_payload(evidence="experienced_burden", relevance="yes", first_hand=.95, unknown=()):
    rubric = load_rubric("v2")
    answers = {}
    for name, q in rubric["questions"].items():
        value = "unknown" if name == "payment_signal" else "ongoing" if name == "need_status" else "known"
        if name.endswith("_availability") and name.removesuffix("_availability") in unknown:
            value = "unknown"
        value = {"evidence_kind": evidence, "relevance": relevance}.get(name, value)
        answers[name] = {"type": q["type"], q["type"]: first_hand if q["type"] == "noul" else 2 if q["type"] == "score" else value}
    return {"answers": answers, "usage": {"input_tokens": 100}}


def test_readable_questions_and_immutable_snapshot():
    rubric = load_rubric("v2")
    frozen = snapshot(rubric)
    before = rubric_hash(frozen)
    rubric["questions"]["pain"]["instructions"] = "Changed question"
    assert rubric_hash(rubric) != before
    assert rubric_hash(frozen) == before
    assert "Level 3:" in readable_rubric(frozen)
    assert frozen["routing"]["mode"] == "soft_v2"


@pytest.mark.parametrize("mutate", [
    lambda r: r["questions"]["pain"].update(type="magic"),
    lambda r: r["questions"]["pain"].update(criteria=["one"]),
    lambda r: r["weights"].update(pain=float("nan")),
    lambda r: r["weights"].update(pain=99),
    lambda r: r["routing"].update(first_hand_review_threshold=2),
    lambda r: r["questions"]["evidence_kind"]["criteria"].update(new_option="unsupported"),
])
def test_invalid_definition_rejected_before_calls(mutate):
    rubric = load_rubric("v2")
    mutate(rubric)
    with pytest.raises(ValueError):
        validate_rubric(rubric)


def test_v2_soft_review_and_clear_exclusions():
    rubric = load_rubric("v2")
    primary = revised_priority(v2_payload(), rubric)
    assert primary["accepted"] and primary["route"] == "primary"
    assert primary["payment_signal"] == "unknown"
    for kwargs in ({"evidence": "unclear"}, {"relevance": "adjacent"}, {"first_hand": .4}):
        review = revised_priority(v2_payload(**kwargs), rubric)
        assert review["accepted"] and review["route"] == "review"
        assert review["review_reasons"]
    for kwargs in ({"evidence": "promotion_or_general"}, {"evidence": "satisfied_low_burden"}, {"relevance": "no"}, {"unknown": tuple(rubric["weights"])}):
        excluded = revised_priority(v2_payload(**kwargs), rubric)
        assert not excluded["accepted"] and excluded["route"] == "excluded"


def test_malformed_choice_is_a_validation_error_not_type_error():
    payload = v2_payload()
    payload['answers']['evidence_kind']['choice'] = ['experienced_burden']
    with pytest.raises(ValueError, match='Invalid choice'):
        revised_priority(payload, load_rubric('v2'))


@pytest.mark.asyncio
async def test_production_definition_not_sent_as_experiment(tmp_path):
    calls = []
    with Store(str(tmp_path / 'cache.db')) as store:
        async with HTTP(store, rate=0, transport=httpx.MockTransport(lambda r: calls.append(r))) as http:
            with pytest.raises(ValueError, match='experimental rubrics'):
                await compare([record()], http, 'secret', rubric=load_rubric('production'))
    assert calls == []


def test_score_normalization_uses_file_level_count():
    rubric = load_rubric("v2")
    rubric["questions"]["pain"]["criteria"].append("Another anchored level")
    result = revised_priority(v2_payload(), rubric)
    assert result["dimensions"]["pain"] == .5


def test_questions_command_is_local_and_selectable(capsys, tmp_path):
    main(["questions", "--rubric", "production"])
    assert "current unresolved problem" in capsys.readouterr().out
    path = tmp_path / "rubric.json"
    rubric = load_rubric("v2")
    rubric["questions"]["pain"]["instructions"] = "A user's edited question"
    path.write_text(json.dumps(rubric))
    main(["questions", "--rubric", str(path), "--format", "json"])
    assert json.loads(capsys.readouterr().out)["questions"]["pain"]["instructions"] == "A user's edited question"


@pytest.mark.asyncio
async def test_custom_rubric_is_actual_request_and_saved_snapshot(tmp_path):
    from test_benchmark import payload
    requests = []
    rubric = load_rubric("v2")
    rubric["questions"]["pain"]["instructions"] = "Edited concrete pain question"
    def handle(request):
        body = json.loads(request.content)
        requests.append(body)
        return httpx.Response(200, json=v2_payload() if "evidence_kind" in body["questions"] else payload(genuine=.59))
    with Store(str(tmp_path / "cache.db")) as store:
        async with HTTP(store, rate=0, transport=httpx.MockTransport(handle)) as http:
            report = await compare([record()], http, "secret", rubric=rubric, reference_rubric=load_rubric("v1"))
    assert len(requests) == 2  # ablation reuses answers, never calls JEV again
    assert requests[1]["questions"]["pain"]["instructions"] == "Edited concrete pain question"
    assert report["rubric_snapshot"] == rubric
    assert report["fingerprints"]["rubric_sha256"] == rubric_hash(rubric)
    assert not report["records"][0]["baseline"]["accepted"]
    assert report["records"][0]["v1_no_genuine_gate"]["accepted"]
    assert report["metrics"]["all"]["v1_no_genuine_gate"]["useful_accepted"] == 1
