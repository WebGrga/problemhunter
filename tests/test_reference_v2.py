import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("collect_reference_v2", Path(__file__).parents[1] / "scripts/collect_reference_v2.py")
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


def item():
    return {"question_id": 123, "link": "https://money.stackexchange.com/questions/123",
            "title": "Invoice &amp; bill", "creation_date": 1704067200,
            "owner": {"user_id": 9, "display_name": "A &amp; B", "link": "https://money.stackexchange.com/users/9"},
            "body": "<p>Complete invoice question body. " + "Repeated complete text. " * 5 + "</p>",
            "content_license": "CC BY-SA 4.0"}


def test_complete_body_attribution_license_and_provenance():
    raw = item()
    row = collector.normalize_question(raw, "money", "invoice")
    assert row["original_html"] == raw["body"]
    assert "Repeated complete text." in row["content"]
    assert row["author"] == "A & B"
    assert row["author_id"] == 9
    assert row["title"] == "Invoice & bill"
    assert row["published_at"] == "2024-01-01T00:00:00+00:00"
    assert row["license"] == "CC BY-SA 4.0"
    assert row["retrieval"]["filter"] == "withbody"
    assert row["thread_url"] == row["url"]


def test_missing_authors_and_long_bodies_not_truncated():
    raw = item()
    raw["owner"] = {}
    assert collector.normalize_question(raw, "money", "invoice") is None
    raw = item()
    raw["body"] = "a" * 10001
    assert collector.normalize_question(raw, "money", "invoice") is None


def test_disjoint_ids_and_content_including_cross_site_duplicates():
    a = collector.normalize_question(item(), "money", "invoice")
    b = dict(a, id="se_workplace_456")
    c = dict(a, id="new", content="Different content", content_sha256="different")
    assert collector.exclude_prior([a, b, c, c], [a]) == [c]
    assert collector.exclude_prior([a, b], []) == [a]


def fixtures(tmp_path):
    row = collector.normalize_question(item(), "money", "invoice")
    pool = tmp_path / "candidates.json"
    pool.write_text(json.dumps({"collection_requests": 1, "estimated_collection_cost_usd": 0, "records": [row]}))
    labels = tmp_path / "labels.json"
    labels.write_text(json.dumps([{"id": row["id"], "priority": 2, "relevance": "relevant",
                                  "status": "ongoing", "reason": "fixture", "problem_excerpt": "Complete invoice question body."}]))
    prior = tmp_path / "prior.json"
    prior.write_text(json.dumps({"records": []}))
    return pool, labels, prior


def test_freeze_entirely_holdout_and_full_source_preserved(tmp_path):
    pool, labels, prior = fixtures(tmp_path)
    output = tmp_path / "reference.json"
    collector.freeze(pool, labels, output, prior)
    payload = json.loads(output.read_text())
    record = payload["records"][0]
    assert record["split"] == record["annotation"]["split"] == "holdout"
    assert record["original_html"] == item()["body"]
    assert payload["independent_threads"] == payload["independent_authors"] == 1
    assert payload["prior_overlap_count"] == 0


def test_freeze_rejects_invalid_excerpt_and_prior_overlap(tmp_path):
    pool, labels, prior = fixtures(tmp_path)
    output = tmp_path / "reference.json"
    annotation = json.loads(labels.read_text())
    annotation[0]["problem_excerpt"] = "fabricated"
    labels.write_text(json.dumps(annotation))
    with pytest.raises(ValueError, match="Excerpt not found"):
        collector.freeze(pool, labels, output, prior)
    annotation[0]["problem_excerpt"] = ""
    labels.write_text(json.dumps(annotation))
    prior.write_text(pool.read_text())
    with pytest.raises(ValueError, match="overlaps prior"):
        collector.freeze(pool, labels, output, prior)
