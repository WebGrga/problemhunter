"""Run an attributed reference corpus through the shared pipeline without labels.

This is a replay of public API evidence, not fresh discovery or a scraper. The
CSV option exports the same bodies to test import parity, not acquisition yield.
"""
import argparse
import asyncio
import csv
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from problem_hunter.cli import prices_from_env
from problem_hunter.discovery import Discovery
from problem_hunter.discovery_audit import audit_sources, summarize_yield
from problem_hunter.extraction import Extractor
from problem_hunter.http import HTTP
from problem_hunter.models import Source
from problem_hunter.pipeline import Pipeline
from problem_hunter.reports import export_report
from problem_hunter.research import Researcher
from problem_hunter.storage import Store
from problem_hunter.triage import ExperimentalEvaluator


def source_records(path):
    records = json.loads(Path(path).read_text())["records"]
    return [Source(url=r["url"], title=r["title"], content=r["content"],
                   source=r["source"], author=r.get("author"), published_at=r.get("published_at"),
                   metadata={"discovery_provider": "stackexchange", "reference_record_id": r["id"],
                             **{k: r[k] for k in ("original_html", "license", "thread_url", "author_id") if k in r}})
            for r in records]


async def run(args):
    sources = source_records(args.reference)
    if args.csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        with args.csv.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=["url", "title", "content", "source", "author", "published_at"])
            writer.writeheader()
            writer.writerows({k: getattr(s, k) for k in writer.fieldnames} for s in sources)
    with Store(args.db) as store:
        first_log = store.connection.execute("SELECT COALESCE(MAX(id),0) FROM request_logs").fetchone()[0]
        async with HTTP(store, max_requests=args.max_requests, max_cost=args.max_cost, prices=prices_from_env()) as http:
            audit = await audit_sources(sources)
            discovery = Discovery(http, os.environ.get("BRAVE_SEARCH_API_KEY", ""))
            extractor = Extractor(http)
            key, model = os.environ.get("TYPESAFE_API_KEY", ""), os.environ.get("JEV_MODEL", "jev-latest")
            evaluator = ExperimentalEvaluator(http, key, model)
            researcher = Researcher(discovery, extractor, http=http, jev_key=key, jev_model=model)
            opportunities = await Pipeline(store, evaluator, extractor, researcher).process(audit["sources"], research_top=args.research_top)
        sources, problems = store.load_sources(), store.load_problems()
        for extension, format in ((".md", "markdown"), (".json", "json")):
            export_report(opportunities, sources, Path(str(args.output) + extension), format=format, problems=problems)
        store.connection.row_factory = __import__("sqlite3").Row
        logs = list(store.connection.execute("SELECT * FROM request_logs WHERE id>?", (first_log,)))
        summary = summarize_yield(audit["sources"], problems, opportunities, logs)
        path = Path(str(args.output) + ".yield.json")
        path.write_text(json.dumps({"input_note": "Frozen public API evidence replay; labels not passed to evaluator. No new acquisition requests.", "collection": audit["metrics"], "pipeline": summary}, indent=2) + "\n")
        print(json.dumps({"funnel": summary["funnel"], "costs": summary["costs"]}, indent=2))


if __name__ == "__main__":
    load_dotenv(Path.cwd() / ".env", override=False)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("--db", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--research-top", type=int, default=0)
    parser.add_argument("--max-requests", type=int, default=60)
    parser.add_argument("--max-cost", type=float, default=.05)
    asyncio.run(run(parser.parse_args()))
