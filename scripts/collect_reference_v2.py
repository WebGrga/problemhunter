"""Collect full public Stack Exchange questions; no models or paid search calls.

API docs: https://api.stackexchange.com/docs/advanced-search
Built-in withbody filter: https://api.stackexchange.com/docs/filters
Attribution/license: https://stackoverflow.com/help/licensing
Only ignored local artifacts contain third-party text.
"""
import argparse
import asyncio
import hashlib
import html
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from problem_hunter.http import HTTP
from problem_hunter.storage import Store

API = "https://api.stackexchange.com/2.3/search/advanced"
QUERIES = [(s, q) for s in ("freelancing", "money", "workplace")
           for q in ("invoice", "unpaid")]


def normalize_question(item, site, query):
    raw = item.get("body", "")
    text = BeautifulSoup(raw, "html.parser").get_text(" ", strip=True)
    owner = item.get("owner") or {}
    if not item.get("question_id") or not owner.get("display_name") or not 80 <= len(text) <= 10000:
        return None
    return {"id": f"se_{site}_{item['question_id']}", "url": item["link"],
            "source": f"Stack Exchange {site}", "author": html.unescape(owner["display_name"]),
            "author_id": owner.get("user_id"), "author_url": owner.get("link"),
            "published_at": datetime.fromtimestamp(item["creation_date"], timezone.utc).isoformat(),
            "title": html.unescape(item.get("title", "")), "content": text,
            "original_html": raw, "thread_url": item["link"], "story_id": item["question_id"],
            "license": item.get("content_license", "See post timeline for revision-specific CC BY-SA license"),
            "retrieval": {"api": API, "site": site, "queries": [query], "filter": "withbody"},
            "content_sha256": hashlib.sha256(text.encode()).hexdigest()}


def exclude_prior(rows, prior):
    ids = {r["id"] for r in prior}
    hashes = {hashlib.sha256(r["content"].encode()).hexdigest() for r in prior}
    seen_ids, seen_hashes, result = set(), set(), []
    for row in rows:
        h = row["content_sha256"]
        if row["id"] in ids | seen_ids or h in hashes | seen_hashes:
            continue
        seen_ids.add(row["id"])
        seen_hashes.add(h)
        result.append(row)
    return result


async def collect(output, db, prior_path):
    prior = json.loads(prior_path.read_text())["records"]
    with Store(db) as store:
        async with HTTP(store, max_requests=20, concurrency=1, rate=1, retries=1) as http:
            rows, attempts, backoff = {}, [], 0
            for site, query in QUERIES:
                if backoff:
                    # Stop rather than blocking a development turn for a large API backoff.
                    raise RuntimeError(f"API requests a {backoff}s backoff; resume later from cache")
                response = await http.request("GET", API, provider="stackexchange", params={
                    "site": site, "q": query, "sort": "relevance", "order": "desc",
                    "pagesize": 100, "filter": "withbody"})
                payload = response.json()
                if payload.get("error_id"):
                    raise ValueError(payload.get("error_message", "Stack Exchange API error"))
                backoff = payload.get("backoff", 0)
                attempts.append({"site": site, "query": query, "returned": len(payload.get("items", [])),
                                 "quota_remaining": payload.get("quota_remaining"), "backoff": backoff})
                if payload.get("quota_remaining", 1) <= 0:
                    raise RuntimeError("Stack Exchange daily quota exhausted")
                for item in payload.get("items", []):
                    row = normalize_question(item, site, query)
                    if row:
                        if row["id"] in rows:
                            rows[row["id"]]["retrieval"]["queries"].append(query)
                        else:
                            rows[row["id"]] = row
            unique = exclude_prior(rows.values(), prior)
            payload = {"schema_version": 2, "collected_at": datetime.now(timezone.utc).isoformat(),
                       "collection_requests": http.requests, "estimated_collection_cost_usd": http.cost,
                       "queries": attempts, "unique_before_prior_and_content_dedup": len(rows),
                       "deduplicated_or_prior_excluded": len(rows) - len(unique),
                       "api_docs": ["https://api.stackexchange.com/docs/advanced-search",
                                    "https://api.stackexchange.com/docs/filters",
                                    "https://api.stackexchange.com/docs/throttle"], "records": unique}
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
            print(f"Collected {len(unique)} complete attributed questions; {http.requests} free API requests")


def freeze(candidates, annotations, output, prior_path):
    pool = json.loads(candidates.read_text())
    indexed = {r["id"]: r for r in pool["records"]}
    labels = json.loads(annotations.read_text())
    if len(labels) != len({r["id"] for r in labels}):
        raise ValueError("Duplicate annotation IDs")
    records = []
    for label in labels:
        row = dict(indexed[label["id"]])
        annotation = {k: v for k, v in label.items() if k != "id"}
        excerpt = annotation.get("problem_excerpt", "")
        if excerpt and excerpt not in row["content"]:
            raise ValueError(f"Excerpt not found: {row['id']}")
        if annotation["priority"] not in range(4) or annotation["relevance"] not in {"relevant", "adjacent", "irrelevant"}:
            raise ValueError("Invalid annotation")
        annotation.update(split="holdout", reviewer="assistant-engineer review, not independent human ground truth")
        row.update(annotation=annotation, split="holdout")
        records.append(row)
    prior = json.loads(prior_path.read_text())["records"]
    if len(exclude_prior(records, prior)) != len(records):
        raise ValueError("Reference overlaps prior set or contains duplicates")
    dates = [r["published_at"] for r in records]
    payload = {"schema_version": 2, "topic": "Freelancer and small-business invoice administration",
               "frozen_at": datetime.now(timezone.utc).isoformat(),
               "method": "Assistant-engineer review of complete questions, before model outputs and without viewing tested questions. Purposive mixture of burdens and controls, all held out from prompt development.",
               "limitations": ["Engineer judgments, not independent human ground truth or demand validation",
                               "Purposive search and selection; not prevalence representative",
                               "Historical content; fresh reference means newly selected, not newly published",
                               "Question bodies only; answers and subsequent resolution not retrieved",
                               "Legal/tax questions may reveal service needs rather than software demand"],
               "collection_requests": pool["collection_requests"], "collection_cost_usd": pool["estimated_collection_cost_usd"],
               "source_counts": dict(Counter(r["source"] for r in records)),
               "priority_counts": dict(Counter(r["annotation"]["priority"] for r in records)),
               "independent_authors": len({(r["source"], r.get("author_id") or r["author"]) for r in records}),
               "independent_threads": len({r["thread_url"] for r in records}),
               "publication_range": [min(dates), max(dates)], "prior_overlap_count": 0,
               "candidate_provenance": {k: v for k, v in pool.items() if k != "records"}, "records": records}
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(f"Frozen {len(records)} records: SHA256 {hashlib.sha256(output.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("reports/jev-benchmark-v2/candidates.json"))
    parser.add_argument("--db", default="reports/jev-benchmark-v2/collection.db")
    parser.add_argument("--prior", type=Path, default=Path("reports/jev-benchmark/reference.json"))
    parser.add_argument("--annotations", type=Path, help="Freeze reviewed JSON labels without API calls")
    args = parser.parse_args()
    if args.annotations:
        freeze(args.output, args.annotations, args.output.with_name("reference.json"), args.prior)
    else:
        asyncio.run(collect(args.output, args.db, args.prior))
