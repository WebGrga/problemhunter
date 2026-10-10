"""Freeze fresh, attributed holdout records without model calls.

Unused records from the free official Stack Exchange API candidate pool can be
reused. Both prior reference sets are excluded by ID and normalized full text.
Labels are assistant judgments made before inspecting tested model outputs.
"""
import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from problem_hunter.discovery import content_signature


def exclude_prior(rows, prior):
    ids = {r["id"] for r in prior}
    bodies = {content_signature(r["content"]) for r in prior}
    result = []
    for row in rows:
        body = content_signature(row["content"])
        if row["id"] in ids or body in bodies:
            continue
        ids.add(row["id"])
        bodies.add(body)
        result.append(row)
    return result


def freeze(candidates, annotations, output, prior_paths, *, enforce_size=True):
    pool = json.loads(Path(candidates).read_text())
    indexed = {r["id"]: r for r in pool["records"]}
    labels = json.loads(Path(annotations).read_text())
    if len(labels) != len({r["id"] for r in labels}):
        raise ValueError("Duplicate annotation IDs")
    if enforce_size and not 30 <= len(labels) <= 40:
        raise ValueError("Fresh reference must have 30–40 records")
    records = []
    for label in labels:
        row = dict(indexed[label["id"]])
        if not all(row.get(k) for k in ("author", "published_at", "url", "original_html", "content", "license")):
            raise ValueError("Full attribution, original HTML and licensing required")
        annotation = {k: v for k, v in label.items() if k != "id"}
        if type(annotation.get("priority")) is not int or annotation["priority"] not in range(4):
            raise ValueError("Invalid priority")
        if annotation.get("relevance") not in {"relevant", "adjacent", "irrelevant"}:
            raise ValueError("Invalid relevance")
        if not annotation.get("reason") or not annotation.get("status"):
            raise ValueError("Reason and status required")
        excerpt = annotation.get("problem_excerpt", "")
        if excerpt and excerpt not in row["content"]:
            raise ValueError(f"Excerpt not found: {row['id']}")
        if annotation["priority"] >= 2 and not excerpt:
            raise ValueError("Useful positives require a verbatim excerpt")
        annotation.update(split="holdout", reviewer="assistant-engineer judgment, not human ground truth")
        row.update(annotation=annotation, split="holdout")
        records.append(row)
    prior = [r for p in prior_paths for r in json.loads(Path(p).read_text())["records"]]
    if len(exclude_prior(records, prior)) != len(records):
        raise ValueError("Reference overlaps prior ID/content or contains duplicates")
    dates = [r["published_at"] for r in records]
    payload = {
        "schema_version": 3, "topic": "Freelancer and small-business invoice administration",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "method": "Assistant-engineer judgments from full bodies before v3 model outputs; reviewer did not inspect v2/v3 rubrics or prior model outputs. Purposive unused candidates, all holdout.",
        "limitations": ["Assistant judgments, not independent human labels or demand validation",
                       "Purposive selection is not prevalence representative",
                       "Newly selected historical records, not necessarily newly published",
                       "Bodies only; linked images, answers and subsequent resolution not retrieved",
                       "Single public community ecosystem; incoming-expense gathering coverage is limited"],
        "collection_requests": 0, "collection_cost_usd": 0,
        "collection_note": "Reused unused free official API candidate records; no fresh network/model requests",
        "candidate_provenance": {k: v for k, v in pool.items() if k != "records"},
        "source_counts": dict(Counter(r["source"] for r in records)),
        "priority_counts": dict(Counter(r["annotation"]["priority"] for r in records)),
        "independent_authors": len({(r["source"], r.get("author_id") or r["author"]) for r in records}),
        "independent_threads": len({r["thread_url"] for r in records}),
        "publication_range": [min(dates), max(dates)], "prior_overlap_count": 0,
        "prior_references": [{"path": str(p), "sha256": hashlib.sha256(Path(p).read_bytes()).hexdigest()} for p in prior_paths],
        "records": records,
    }
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    print(f"Frozen {len(records)} records: SHA256 {digest}")
    return digest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=Path("reports/jev-benchmark-v2/candidates.json"))
    parser.add_argument("--annotations", type=Path, default=Path("reports/jev-benchmark-v3/annotations.json"))
    parser.add_argument("--output", type=Path, default=Path("reports/jev-benchmark-v3/reference.json"))
    parser.add_argument("--prior", type=Path, action="append")
    args = parser.parse_args()
    freeze(args.candidates, args.annotations, args.output, args.prior or [Path("reports/jev-benchmark/reference.json"), Path("reports/jev-benchmark-v2/reference.json")])
