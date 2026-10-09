import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("collect_reference_v3", Path(__file__).parents[1] / "scripts/collect_reference_v3.py")
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


def test_excludes_id_and_normalized_copied_body_across_all_priors():
    prior = [{"id": "old", "content": "Original invoice text!"}]
    rows = [{"id": "old", "content": "different"}, {"id": "new", "content": "ORIGINAL   invoice text."}, {"id": "fresh", "content": "Fresh content"}]
    assert collector.exclude_prior(rows, prior) == [rows[2]]


def fixtures(tmp_path):
    row = {"id": "fresh", "content": "My invoices are blocked by a software incompatibility.", "original_html": "<p>Full body</p>", "author": "A", "published_at": "2020-01-01", "url": "https://example.com/question", "thread_url": "https://example.com/question", "license": "CC BY-SA 4.0", "source": "community"}
    candidates = tmp_path / "candidates.json"
    candidates.write_text(json.dumps({"records": [row], "collection_requests": 6}))
    annotations = tmp_path / "annotations.json"
    label = {"id": "fresh", "priority": 2, "relevance": "relevant", "status": "blocked", "reason": "Concrete blocker", "problem_excerpt": "My invoices are blocked"}
    annotations.write_text(json.dumps([label]))
    priors = [tmp_path / "prior1.json", tmp_path / "prior2.json"]
    for prior in priors:
        prior.write_text(json.dumps({"records": []}))
    return candidates, annotations, priors, row, label


def test_freeze_is_attributed_entirely_holdout_and_no_new_requests(tmp_path):
    candidates, labels, priors, row, _ = fixtures(tmp_path)
    output = tmp_path / "reference.json"
    digest = collector.freeze(candidates, labels, output, priors, enforce_size=False)
    payload = json.loads(output.read_text())
    assert len(digest) == 64
    assert payload["collection_requests"] == payload["collection_cost_usd"] == 0
    assert payload["records"][0]["original_html"] == row["original_html"]
    assert payload["records"][0]["annotation"]["split"] == "holdout"
    assert "not human" in payload["records"][0]["annotation"]["reviewer"]
    assert len(payload["prior_references"]) == 2


def test_freeze_rejects_overlap_with_second_prior_and_bad_excerpt(tmp_path):
    candidates, labels, priors, row, label = fixtures(tmp_path)
    output = tmp_path / "reference.json"
    priors[1].write_text(json.dumps({"records": [row]}))
    with pytest.raises(ValueError, match="overlaps"):
        collector.freeze(candidates, labels, output, priors, enforce_size=False)
    priors[1].write_text(json.dumps({"records": []}))
    label["problem_excerpt"] = "fabricated"
    labels.write_text(json.dumps([label]))
    with pytest.raises(ValueError, match="Excerpt not found"):
        collector.freeze(candidates, labels, output, priors, enforce_size=False)
    with pytest.raises(ValueError, match="30–40"):
        collector.freeze(candidates, labels, output, priors)
