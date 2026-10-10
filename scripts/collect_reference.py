"""Collect complete HN comments for blind, local benchmark annotation.

No model evaluation is performed. Public text is kept in ignored local artifacts.
"""
import argparse
import asyncio
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from problem_hunter.http import HTTP
from problem_hunter.storage import Store

QUERIES = ("invoice", "invoicing", "unpaid client", "chasing invoices",
           "invoice spreadsheet", "freelancer invoice")

# Blind engineer annotations, frozen before paid-model evaluation. These are
# methodological review labels, not independently validated human ground truth.
# id, priority, relevance, reason, exact excerpt (empty for non-problems).
ANNOTATIONS = [
    ("32850721", 1, "relevant", "Firsthand frustration, no concrete frequency or consequence.", "chasing clients and invoices sucked, and was a waste of my time and skills"),
    ("42607730", 0, "relevant", "Experienced freelancer explicitly finds spreadsheets sufficient.", ""),
    ("9981402", 3, "relevant", "Repeated nonpayment approaching a year and agency workaround.", "Working directly I've run into non-payment issues several times with non-payment periods upto almost a year"),
    ("101393", 0, "relevant", "Satisfied existing-product customer, no unmet need stated.", ""),
    ("10174835", 0, "relevant", "Satisfied spreadsheet workflow, no complaint.", ""),
    ("10177970", 1, "relevant", "Dislikes spreadsheets but still endorses invoice template.", "I love Vim and hate spreadsheets."),
    ("10203494", 1, "relevant", "Experience-informed prevention advice, but no specific experienced loss or unresolved burden.", "There are opportunity costs for a small business when resources are devoted to chasing deadbeats instead of new work."),
    ("10204166", 3, "relevant", "Firsthand court action on two months unpaid with legal costs.", "I've actually only had to take an unpaid invoice (two months, actually, plus some short change on previous invoices) to court once and it was painful as hell."),
    ("11088618", 3, "relevant", "Repeated cash-flow stress led to contractual and service-stop workarounds.", "Employing those three strategies fixed most of our cash flow issues and helped stress levels go down drastically."),
    ("11091467", 3, "relevant", "Recurring late payments despite actual fee experiment.", "We have also tried inserting a admin fee of $150every time invoices remain unpaid after 30 days."),
    ("1133574", 1, "adjacent", "Generalized tedium analogy without a specific experienced invoice burden.", "Whether that is doing the dishes night in/night out, chasing down invoices, doing your taxes, provisioning servers, some things just need to get done."),
    ("11673141", 0, "relevant", "Creator promotion; not an independent customer complaint.", ""),
    ("12947052", 0, "relevant", "Automation description without dissatisfaction or unmet need.", ""),
    ("12968821", 2, "relevant", "Firsthand procrastination triggered custom invoice script.", "Now that I'm doing contracting work, I did the same thing again when I got tired of invoicing from a spreadsheet."),
    ("13004651", 0, "relevant", "Existing reminder process explicitly works well.", ""),
    ("1405939", 3, "relevant", "Observed administrative labor estimate and concrete collection process.", "Where I work the woman who does all the admin spends a good 20% of her time chasing invoices"),
    ("14229292", 0, "adjacent", "Publication subscription purchase is unrelated to buying invoice tools.", ""),
    ("14335156", 0, "relevant", "Maker solicits interest, no independent complaint.", ""),
    ("14791903", 0, "relevant", "Firsthand disconfirmation: invoices almost always paid on time.", ""),
    ("14987581", 1, "adjacent", "Invoice chasing is one item in broader freelancing dissatisfaction.", "More responsibilities (pension, taxes, vat returns, chasing invoices, legal etc.) It all gets pretty draining"),
    ("15118650", 0, "relevant", "Working office-document process without stated burden.", ""),
    ("1545754", 2, "relevant", "Concrete missing reminder automation for an existing product.", "If I could configure it to send an obviously-automated email whenever that happens, it'd solve most of my invoice-chasing problems."),
    ("15735837", 1, "relevant", "Occasional forgetful clients resolved with email; explicitly minor.", "But I don't really consider chasing up invoices to be a major problem in my work, it's just an occasional email to remind people."),
    ("1598624", 2, "relevant", "Firsthand substantial collection effort and late or missing payments.", "One of the issues I had as a contractor was amount of energy I spent chasing invoices."),
    ("16791081", 3, "relevant", "High-volume invoice automation with specific runtime failures and custom fixes.", "I managed to work around them all after a lot of hair-pulling... We ran ~15k invoices through it last year!"),
    ("18126772", 3, "relevant", "Firsthand severe missed invoicing with quantified loss claim.", "For me, it's been invoicing and chasing up invoices - to the tune of hundreds of thousands of dollars over the years missed completely."),
    ("1826991", 3, "relevant", "Unpaid invoices threaten payroll and require savings and second jobs.", "I paid all my employees and I had $3.62 left in the company bank account with several unpaid invoices from clients"),
    ("18754032", 3, "relevant", "Actual repeated collection and special paperwork led to rate increase.", "What did annoy me was their inability to pay bills on time, and time I spent chasing invoices and creating custom late payment paperwork"),
    ("20008975", 0, "relevant", "Prefers familiar Excel over acquiring new software.", ""),
    ("20174911", 1, "relevant", "Would use app but no urgency; current manual workflow functions.", "I would use an app, but never get round to sorting it out."),
    ("22335905", 3, "relevant", "Hired employee to relieve collection burden hampering core work.", "These manual back office tasks is exactly why I hired an office manager."),
    ("2386938", 2, "relevant", "Active request for alternative to inefficient invoice spreadsheet.", "Excel spreadsheet for tracking + invoice template is really inefficient for me."),
    ("23890058", 2, "adjacent", "Repeated failed time-tracking tools and custom reporting; invoices downstream.", "After years of trying to use time tracking systems, TODO systems, and journaling systems, I could never get past their data-entry-inefficiency"),
    ("25748013", 2, "relevant", "Experienced spreadsheet fragility and tiring manual imports; adopted alternative.", "Manually exporting and importing CSV files is fatiguing and error prone as well."),
    ("27207499", 2, "relevant", "Recurring one-to-two-month delayed invoicing with manual reconstruction.", "I work as a consultant and I regularly forget to send invoices for a month (sometimes two)."),
    ("27596722", 3, "relevant", "Extensive custom invoice collection with existing SaaS inadequacy.", "the ones I tried need more manual work than the solution I have today"),
    ("33763429", 2, "relevant", "Detailed recurring fee/credit-note workaround to enforce payment.", "every month (or even more freqently) they get a credit note for the old invoice and a new invoice with the interest and chasing fee added."),
    ("34658503", 0, "relevant", "Low-volume customer explicitly disconfirms invoice management burden.", ""),
    ("35539236", 2, "relevant", "Changed subscription duration to reduce accountant invoice collection.", "One thing I hate about being a freelancer is grabbing all invoices for my accountant."),
    ("35838986", 2, "relevant", "Recurring twelve-document monthly workload per freelancer, no monthly alternative.", "For every freelancer you work with, they send you 12 (!) PDFs per month."),
]

REVIEW_STATUS = {
    "32850721": "unclear", "42607730": "resolved_low_burden", "9981402": "historical_workaround",
    "101393": "resolved_low_burden", "10174835": "resolved_low_burden", "10177970": "resolved_low_burden",
    "10203494": "advice", "10204166": "historical_workaround", "11088618": "historical_workaround",
    "11091467": "ongoing", "1133574": "advice", "11673141": "promotion", "12947052": "resolved_low_burden",
    "12968821": "historical_workaround", "13004651": "resolved_low_burden", "1405939": "ongoing",
    "14229292": "unclear", "14335156": "promotion", "14791903": "resolved_low_burden",
    "14987581": "ongoing", "15118650": "resolved_low_burden", "1545754": "ongoing",
    "15735837": "resolved_low_burden", "1598624": "unclear", "16791081": "historical_workaround",
    "18126772": "ongoing", "1826991": "historical_workaround", "18754032": "historical_workaround",
    "20008975": "resolved_low_burden", "20174911": "resolved_low_burden", "22335905": "historical_workaround",
    "2386938": "ongoing", "23890058": "historical_workaround", "25748013": "historical_workaround",
    "27207499": "ongoing", "27596722": "historical_workaround", "33763429": "historical_workaround",
    "34658503": "resolved_low_burden", "35539236": "ongoing", "35838986": "ongoing",
}


def freeze_reference(candidates, output):
    pool = {row["id"]: row for row in json.loads(candidates.read_text())["records"]}
    records = []
    for id, priority, relevance, reason, excerpt in ANNOTATIONS:
        row = dict(pool["hn_" + id])
        if excerpt and excerpt not in row["content"]:
            raise ValueError(f"Excerpt not present in full source: {id}")
        row["annotation"] = {"relevance": relevance, "priority": priority, "reason": reason,
                             "status": REVIEW_STATUS[id],
                             "problem_excerpt": excerpt,
                             "reviewer": "assistant-engineer review, not independent human ground truth"}
        records.append(row)
    # Within each priority stratum, alternate deterministic hashed IDs; odd
    # strata start on the smaller side to preserve an exact 20/20 balance.
    counts = {"development": 0, "holdout": 0}
    for priority in range(4):
        group = sorted((r for r in records if r["annotation"]["priority"] == priority),
                       key=lambda r: hashlib.sha256(r["id"].encode()).hexdigest())
        start = "development" if counts["development"] <= counts["holdout"] else "holdout"
        for index, row in enumerate(group):
            row["split"] = start if index % 2 == 0 else ("holdout" if start == "development" else "development")
            row["annotation"]["split"] = row["split"]
            counts[row["split"]] += 1
    payload = {"schema_version": 1, "topic": "Freelancer and small-business invoicing administration",
               "frozen_at": datetime.now(timezone.utc).isoformat(),
               "reviewer": "assistant-engineer review, not independent human ground truth",
               "method": "Blind review of complete comments; deliberate mix of burdens, minor annoyances, satisfied users, advice, and promotion. Historical costly workflow evidence may warrant an interview even after a workaround; it does not establish unmet need today. No JEV judgments viewed. Not prevalence-representative.",
               "priority_rubric": {"0": "Nonproblem, satisfied user, informational, or promotion",
                                   "1": "Minor or vague grievance; limited actionable evidence",
                                   "2": "Concrete recurrent burden worth an interview",
                                   "3": "Strong consequential workflow with workaround, alternative, or spending behavior"},
               "split_method": "SHA256 ID ordering within priority strata, alternating balanced dev/holdout; fixed before model execution",
               "limitations": ["Single technically oriented community", "Historical comments; not current demand validation",
                               "Judgment labels are engineer assessments, not a market-viability ground truth",
                               "Comment-level context only; story title and thread URL retained, parents not fetched"],
               "records": records}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(f"Frozen {len(records)} annotated records, split {counts}, into {output}")


def normalize_hit(hit, query):
    raw = hit.get("comment_text") or ""
    content = BeautifulSoup(raw, "html.parser").get_text(" ", strip=True)
    if not hit.get("objectID") or not hit.get("author") or not 80 <= len(content) <= 8000:
        return None
    return {"id": "hn_" + hit["objectID"], "url": "https://news.ycombinator.com/item?id=" + hit["objectID"],
            "source": "Hacker News", "author": hit["author"], "published_at": hit.get("created_at"),
            "title": hit.get("story_title") or "HN comment", "content": content,
            "original_html": raw, "story_id": hit.get("story_id"),
            "thread_url": "https://news.ycombinator.com/item?id=" + str(hit.get("story_id")),
            "retrieval": {"api": "https://hn.algolia.com/api/v1/search", "queries": [query]},
            "content_sha256": hashlib.sha256(content.encode()).hexdigest()}


async def collect(output, db):
    with Store(db) as store:
        async with HTTP(store, max_requests=20, concurrency=2, rate=1) as http:
            rows, hashes = {}, set()
            for query in QUERIES:
                response = await http.request("GET", "https://hn.algolia.com/api/v1/search", provider="hn",
                                              params={"query": query, "tags": "comment", "hitsPerPage": 50})
                for hit in response.json().get("hits", []):
                    row = normalize_hit(hit, query)
                    if not row:
                        continue
                    if row["id"] in rows:
                        rows[row["id"]]["retrieval"]["queries"].append(query)
                    elif row["content_sha256"] not in hashes:
                        rows[row["id"]] = row
                        hashes.add(row["content_sha256"])
            # Favor on-topic records without judging complaint severity or payment.
            ranked = sorted(rows.values(), key=lambda r: (-len(r["retrieval"]["queries"]),
                            -bool(re.search(r"invoice|invoicing", r["content"], re.I)), r["id"]))[:120]
            payload = {"schema_version": 1, "collected_at": datetime.now(timezone.utc).isoformat(),
                       "topic": "Freelancer and small-business invoicing administration",
                       "api_docs": ["https://hn.algolia.com/api", "https://github.com/algolia/hn-search"],
                       "collection_requests": http.requests, "queries": list(QUERIES),
                       "selection": "Unique complete comments, 80–8000 characters; up to 120 candidates. No JEV judgments used.",
                       "records": ranked}
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
            print(f"Collected {len(ranked)} candidates using {http.requests} uncached HN requests into {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("reports/jev-benchmark/candidates.json"))
    parser.add_argument("--db", default="reports/jev-benchmark/collection.db")
    parser.add_argument("--freeze", action="store_true", help="Freeze the blind engineer labels; no API calls")
    args = parser.parse_args()
    if args.freeze:
        freeze_reference(args.output, args.output.with_name("reference.json"))
    else:
        asyncio.run(collect(args.output, args.db))
