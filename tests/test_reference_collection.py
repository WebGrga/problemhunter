import importlib.util
import json
from collections import Counter
from pathlib import Path


spec = importlib.util.spec_from_file_location("collect_reference", Path(__file__).parents[1] / "scripts/collect_reference.py")
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


def test_complete_comment_fields_not_highlight_snippet():
    full = "Original invoice complaint. " * 8
    row = collector.normalize_hit({"objectID": "123", "comment_text": "<p>" + full + "</p>",
                                   "author": "author", "story_id": 12, "created_at": "2024-01-01",
                                   "_highlightResult": {"comment_text": {"value": "snippet"}}}, "invoice")
    assert row["content"] == full.strip()
    assert row["original_html"] == "<p>" + full + "</p>"
    assert row["url"].endswith("id=123")
    assert row["author"] == "author"
    assert row["published_at"] == "2024-01-01"


def test_long_and_unattributed_comments_skipped_not_truncated():
    assert collector.normalize_hit({"objectID": "1", "author": "a", "comment_text": "a" * 8001}, "invoice") is None
    assert collector.normalize_hit({"objectID": "1", "comment_text": "a" * 120}, "invoice") is None


def test_blind_labels_unique_and_cover_all_priorities():
    rows = collector.ANNOTATIONS
    assert len(rows) == len({r[0] for r in rows}) == 40
    assert {r[1] for r in rows} == {0, 1, 2, 3}
    assert all(r[2] in {"relevant", "adjacent", "irrelevant"} for r in rows)


def test_freeze_split_is_balanced_and_exact_excerpts_checked(tmp_path):
    # Synthetic fixture tests artifact mechanics only; not the reference labels.
    candidates = tmp_path / "candidates.json"
    output = tmp_path / "reference.json"
    candidates.write_text(json.dumps({"records": [
        {"id": "hn_" + id, "content": excerpt or "nonproblem fixture"}
        for id, _, _, _, excerpt in collector.ANNOTATIONS]}))
    collector.freeze_reference(candidates, output)
    records = json.loads(output.read_text())["records"]
    assert Counter(r["annotation"]["split"] for r in records) == {"development": 20, "holdout": 20}
    assert all(r["split"] == r["annotation"]["split"] for r in records)
    first_split = {r["id"]: r["split"] for r in records}
    collector.freeze_reference(candidates, output)
    assert first_split == {r["id"]: r["split"] for r in json.loads(output.read_text())["records"]}
