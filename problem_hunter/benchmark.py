"""Frozen, source-level JEV experiment; does not change production scoring.

Manual annotations must be recorded before calling compare. Neither rubric sees
annotations. Priority is a research triage judgment, never market validation.
"""
import argparse
import asyncio
import hashlib
import json
import math
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

from .grouping import group_problems
from .http import HTTP
from .intelligence import Evaluator
from .models import Source
from .scoring import score_opportunity
from .storage import Store
from .rubric import load_rubric, snapshot, rubric_hash, readable_rubric
from .evidence_checks import support_quotes, loss_quote, ground_payment, CHECK_VERSION

WEIGHTS = load_rubric("v1")["weights"]
LEVELS = {name: q["criteria"] for name, q in load_rubric("v1")["questions"].items() if q["type"] == "score"}


def revised_questions(rubric=None):
    return snapshot(rubric or load_rubric("v1"))["questions"]


def _answer(answers, name, kind, choices=None):
    result = answers.get(name)
    if not isinstance(result, dict) or result.get("type") != kind:
        raise ValueError(f"Invalid revised answer: {name}")
    value = result.get({"noul": "noul", "score": "score", "choice": "choice"}[kind])
    if kind == "choice":
        if not isinstance(value, str) or value not in choices:
            raise ValueError(f"Invalid choice: {name}")
    elif isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= (len(choices) - 1 if kind == "score" else 1):
        raise ValueError(f"Invalid numeric answer: {name}")
    return value


def revised_priority(payload, rubric=None, content=""):
    rubric = snapshot(rubric or load_rubric("v1"))
    if not isinstance(payload, dict):
        raise ValueError("Revised response must be an object")
    answers = payload.get("answers")
    if not isinstance(answers, dict):
        raise ValueError("Revised response is missing answers")
    questions, weights, routing = rubric["questions"], rubric["weights"], rubric["routing"]
    parsed = {name: _answer(answers, name, q["type"], q.get("criteria")) for name, q in questions.items()}
    grounded = routing["mode"] == "grounded_v3"
    quotes = support_quotes(content) if grounded else {}
    literal_loss = loss_quote(content) if grounded else None
    experienced = parsed.get("evidence_kind") in {"experienced_burden", "experienced_workaround"}
    if grounded:
        supported_names = {name for name in weights if (name == "pain" and (experienced or literal_loss)) or quotes.get(name)}
    else:
        supported_names = {name for name in weights if parsed[name + "_availability"] == "known"}
    supported = {name: parsed[name] / (len(questions[name]["criteria"]) - 1) for name in weights if name in supported_names}
    coverage = sum(weights[name] for name in supported)
    reasons, review_reasons = [], []
    if routing["mode"] == "hard_v1":
        if parsed["genuine"] < routing["genuine_threshold"]:
            reasons.append("not a concrete experienced workflow problem")
        if parsed["relevance"] != "yes":
            reasons.append("outside the specified workflow")
        if parsed["report_kind"] != "experienced_problem":
            reasons.append("advice, promotion, no experienced problem, or ungrounded hypothetical account")
    else:
        if parsed["relevance"] == "no":
            reasons.append("outside the specified workflow")
        elif parsed["relevance"] == "adjacent":
            review_reasons.append("adjacent workflow; check scope")
        if parsed["evidence_kind"] in {"satisfied_low_burden", "promotion_or_general"}:
            if grounded and literal_loss:
                review_reasons.append("literal experienced loss conflicts with nonproblem classification")
            else:
                reasons.append("no concrete experienced burden")
        elif parsed["evidence_kind"] == "unclear":
            review_reasons.append("experienced evidence is ambiguous")
        if parsed["first_hand"] < routing["first_hand_review_threshold"]:
            review_reasons.append("first-hand attribution uncertain")
    if not supported:
        reasons.append("no supported priority dimensions")
    verified_payment = ground_payment(content, parsed["payment_signal"]) if grounded else None
    payment_signal = parsed["payment_signal"]
    if grounded and payment_signal != "unknown" and not verified_payment:
        payment_signal = "unknown"
        review_reasons.append("payment classification lacks a literal remedy-payment statement")
    if grounded and literal_loss and parsed["pain"] <= 1:
        review_reasons.append("literal loss conflicts with low pain judgment; review severity")
    return {"accepted": not reasons, "rejection_reasons": reasons,
            "route": "excluded" if reasons else "review" if review_reasons else "primary",
            "review_reasons": review_reasons, "rubric_version": rubric["version"],
            "score": round(sum(weights[n] * v for n, v in supported.items()) / coverage * 100, 2) if coverage else None,
            "coverage_weight": coverage, "supported_dimensions": list(supported),
            "coverage_label": "multiple supported dimensions" if len(supported) >= 2 else "limited: one supported dimension" if supported else "insufficient",
            "dimensions": {n: supported.get(n) for n in weights},
            "rank_supported_dimensions_minimum": routing["minimum_supported_dimensions_for_primary_rank"],
            "dimension_quotes": quotes, "literal_loss": literal_loss, "verified_payment": verified_payment,
            "evidence_check_version": CHECK_VERSION if grounded else None,
            "need_status": parsed.get("need_status", "not assessed by v1"),
            "payment_signal": payment_signal, "payment_signal_model": parsed["payment_signal"], "payment_hypothesis": "unknown; no purchase probability inferred",
            "parsed": parsed, "raw_response": payload}


class _Capture:
    def __init__(self, http):
        self.http, self.payload = http, None

    async def request(self, *args, **kwargs):
        response = await self.http.request(*args, **kwargs)
        self.payload = response.json()
        return response


def validate_records(records):
    if not isinstance(records, list) or not records:
        raise ValueError("Dataset must be a nonempty JSON record array")
    seen = set()
    for record in records:
        if not isinstance(record, dict) or not all(isinstance(record.get(k), str) and record[k].strip() for k in ("id", "url", "content")):
            raise ValueError("Every record requires id, url, and content")
        if record["id"] in seen:
            raise ValueError("Duplicate record id")
        seen.add(record["id"])
        if len(record["content"]) > 16000:
            raise ValueError("Benchmark content exceeds 16000 characters; explicitly select a complete shorter record")
        a = record.get("annotation", {})
        if not isinstance(a, dict) or a.get("relevance") not in {"relevant", "adjacent", "irrelevant"} or type(a.get("priority")) is not int or a["priority"] not in range(4) or a.get("split") not in {"development", "holdout"} or not isinstance(a.get("reason"), str) or not a["reason"].strip():
            raise ValueError("Every record requires a pre-recorded manual annotation and split")


def ranking(rows, rubric):
    accepted = [r for r in rows if r[rubric]["accepted"]]
    if accepted and "supported_dimensions" in accepted[0][rubric]:
        return sorted(accepted, key=lambda r: (int(r[rubric].get("route") == "review"), -int(len(r[rubric]["supported_dimensions"]) >= r[rubric].get("rank_supported_dimensions_minimum", 2)), -r[rubric]["score"], r["id"]))
    return sorted(accepted, key=lambda r: (-r[rubric]["score"], r["id"]))


def metrics(rows, rubric, k=10):
    failures = [r["id"] for r in rows if r[rubric].get("error")]
    rows = [r for r in rows if not r[rubric].get("error")]
    ranked = ranking(rows, rubric)
    top = ranked[:k]
    useful = lambda r: r["annotation"]["relevance"] == "relevant" and r["annotation"]["priority"] >= 2
    gain = lambda r: 2 ** r["annotation"]["priority"] - 1 if r["annotation"]["relevance"] == "relevant" else 0
    hits = sum(useful(r) for r in top)
    total = sum(useful(r) for r in rows)
    dcg = sum(gain(r) / math.log2(i + 2) for i, r in enumerate(top))
    ideal = sum(gain(r) / math.log2(i + 2) for i, r in enumerate(sorted(rows, key=gain, reverse=True)[:k]))
    top_ids = {r["id"] for r in top}
    return {"precision_at_10": hits / k, "precision_denominator": k,
            "precision_among_returned": hits / len(top) if top else None,
            "evaluable_records": len(rows), "failed_ids": failures,
            "returned_in_top_10": len(top), "useful_recall_at_10": hits / total if total else None,
            "ndcg_at_10": dcg / ideal if ideal else None,
            "accepted": len(ranked), "rejected": len(rows) - len(ranked),
            "review_lane": sum(r[rubric].get("route") == "review" for r in ranked),
            "useful_accepted": sum(useful(r) for r in ranked),
            "useful_total": total,
            "false_positives": [r["id"] for r in top if not useful(r)],
            "promising_misses": [r["id"] for r in rows if useful(r) and r["id"] not in top_ids]}


def _raw_dict(result):
    raw = result.get("raw_response")
    return raw if isinstance(raw, dict) else {}


async def _evaluate_rubric(source, http, key, model, rubric):
    raw = None
    try:
        response = await http.request("POST", "https://api.typesafe.ai/v1/systemone", provider="jev", headers={"Authorization": f"Bearer {key}"}, json={"model": model, "state": {"title": source.title, "content": source.content}, "questions": rubric["questions"]})
        response.raise_for_status()
        raw = response.json()
        return revised_priority(raw, rubric, source.content)
    except (ValueError, httpx.HTTPError) as exc:
        return {"accepted": False, "score": None, "error": type(exc).__name__, "rejection_reasons": ["API/evaluation failure; not a model rejection"], "route": "failed", "coverage_weight": 0, "coverage_label": "evaluation failed", "supported_dimensions": [], "payment_signal": "unknown", "raw_response": raw}


async def compare(records, http, key, model="jev-latest", rubric=None, reference_rubric=None, gate_only_rubric=None):
    rubric = snapshot(rubric or load_rubric("v1"))
    reference_rubric = snapshot(reference_rubric) if reference_rubric else None
    if any(r and r.get('routing', {}).get('mode') == 'universal_v4' for r in (rubric, reference_rubric)):
        raise ValueError('Use the general pilot or CLI for universal_v4; the invoice comparator does not support its passage selections')
    if "routing" not in rubric or (reference_rubric and "routing" not in reference_rubric):
        raise ValueError("compare requires experimental rubrics; production is the default baseline")
    baseline_definition = reference_rubric or snapshot(load_rubric("production"))
    gate_only_rubric = snapshot(gate_only_rubric) if gate_only_rubric else None
    if gate_only_rubric and gate_only_rubric.get("routing", {}).get("mode") != "hard_v1":
        raise ValueError("Gate-only comparison requires a hard_v1 rubric")
    metadata = {}
    if isinstance(records, dict):
        metadata, records = records.get("metadata", {k: v for k, v in records.items() if k != "records"}), records.get("records")
    starting_requests, starting_cost = getattr(http, "requests", 0), getattr(http, "cost", 0)
    validate_records(records)
    def digest(value):
        return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    fingerprints = {"dataset_sha256": digest({"records": records, "metadata": metadata}),
                    "rubric_sha256": rubric_hash(rubric),
                    "baseline_rubric_sha256": rubric_hash(baseline_definition)}
    if gate_only_rubric:
        fingerprints["gate_only_rubric_sha256"] = rubric_hash(gate_only_rubric)
    if not key:
        raise ValueError("TYPESAFE_API_KEY is required")
    rows = []
    for record in records:
        source = Source(id=record["id"], url=record["url"], title=record.get("title", ""), content=record["content"], author=record.get("author"), published_at=record.get("published_at"), source=record.get("source", "web"))
        if reference_rubric:
            baseline = await _evaluate_rubric(source, http, key, model, reference_rubric)
        else:
            capture = _Capture(http)
            try:
                problems = await Evaluator(capture, key=key, model=model, batch_size=1, rubric=baseline_definition).evaluate([source])
                opportunities = group_problems(problems, [source])
                if opportunities:
                    opportunity = score_opportunity(opportunities[0], problems, [source])
                    baseline = {"accepted": True, "score": opportunity.score, "score_breakdown": opportunity.score_breakdown, "statement": opportunity.description}
                else:
                    baseline = {"accepted": False, "score": 0, "rejection_reasons": ["genuine below production threshold"]}
            except (ValueError, httpx.HTTPError) as exc:
                baseline = {"accepted": False, "score": None, "error": type(exc).__name__, "rejection_reasons": ["API/evaluation failure; not a model rejection"]}
            baseline["raw_response"] = capture.payload
        revised = await _evaluate_rubric(source, http, key, model, rubric)
        row = {**record, "baseline": baseline, "revised": revised}
        if reference_rubric and reference_rubric["routing"]["mode"] == "hard_v1":
            ablation = snapshot(reference_rubric)
            ablation["version"] += "-no-genuine-gate"
            ablation["routing"]["genuine_threshold"] = 0
            row["v1_no_genuine_gate"] = revised_priority(baseline["raw_response"], ablation) if not baseline.get("error") else dict(baseline)
        if gate_only_rubric:
            gate_result = await _evaluate_rubric(source, http, key, model, gate_only_rubric)
            ablation = snapshot(gate_only_rubric)
            ablation["version"] += "-no-genuine-gate"
            ablation["routing"]["genuine_threshold"] = 0
            row["gate_only"] = revised_priority(gate_result["raw_response"], ablation) if not gate_result.get("error") else gate_result
        rows.append(row)
    variants = ["baseline", "revised"] + (["v1_no_genuine_gate"] if rows and "v1_no_genuine_gate" in rows[0] else [])
    if gate_only_rubric:
        variants.append("gate_only")
    rank_minimum = rubric['routing'].get('rank_supported_dimensions_minimum', 2)
    return {"fingerprints": fingerprints, "dataset_metadata": metadata, "gate_only_rubric_snapshot": gate_only_rubric, "evidence_check_version": CHECK_VERSION, "rubric_snapshot": rubric, "baseline_rubric_snapshot": baseline_definition, "methodology": {"rubric_version": "v1" if rubric["version"] == "invoice-v1" else rubric["version"], "status": "developer-reviewed benchmark; not market demand statistics", "baseline": f"Experimental {reference_rubric['version']}" if reference_rubric else "Unchanged production evaluator, grouping, and singleton opportunity scoring", "revised": "Supported-dimension research priority; not commercial viability; numeric index, not physical units", "weights": rubric["weights"], "scale_max": {n: len(rubric['questions'][n]['criteria']) - 1 for n in rubric['weights']}, "unknowns": "excluded from supported-weight denominator", "ranking": f"primary before review; at least {rank_minimum} supported dimensions before fewer; then descending score; id breaks ties", "gates": rubric["routing"], "questions": rubric["questions"], "holdout": "Rubric frozen before outputs; no holdout-output tuning"},
            "records": rows, "ablation": {"v1_no_genuine_gate": "Same v1 answers/weights/report-kind gate; only genuine cutoff set to zero. No extra API calls."} if len(variants) > 2 else {}, "metrics": {split: {variant: metrics([r for r in rows if split == "all" or r["annotation"]["split"] == split], variant) for variant in variants} for split in ("all", "development", "holdout")},
            "accounting": {"requests": getattr(http, "requests", 0) - starting_requests, "estimated_cost_usd": getattr(http, "cost", 0) - starting_cost, "usage_note": "Response tokens include cached answers; only uncached requests contribute new estimated cost.", "response_usage": {rubric: {name: sum(_raw_dict(r[rubric]).get("usage", {}).get(name, 0) for r in rows) for name in ("input_tokens", "output_tokens")} for rubric in variants if rubric != "v1_no_genuine_gate"}}}


def write_comparison(report, path):
    prefix = Path(path)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    json_path, md_path = prefix.with_suffix(".json"), prefix.with_suffix(".md")
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = ["# JEV rubric comparison", "", "Developer-reviewed research triage experiment, not evidence of market demand. Annotations were recorded before model outputs. No holdout-output tuning.", "", f"Baseline: {report['methodology']['baseline']}. Revised: {report['methodology']['rubric_version']}.", "", "Experimental scores describe complaint investigation priority, not commercial viability. Production opportunity scores use a different scale. Unknown dimensions are excluded from the experimental weighted mean. Payment classifications are model judgments; literal rule checks do not establish purchase probability.", "", f"Revised ranking: {report['methodology']['ranking']}.", "", "## Metrics", "", "```json", json.dumps(report["metrics"], indent=2), "```", "", "## Usage and estimated cost", "", "```json", json.dumps(report["accounting"], indent=2), "```"]
    lines += ["", "Precision@10 uses ten slots even when fewer records qualify; precision among returned records and returned count distinguish ranking quality from yield. Failed evaluations are excluded from quality metrics and listed separately. Scores are judgment indices, not measurements of money, time, or market viability.", "", "Frozen input fingerprints:", "", "```json", json.dumps(report.get("fingerprints", {}), indent=2), "```"]
    def escape(value):
        return str(value).replace("|", "\\|").replace("\n", " ")
    lines += ["", "## Exact questions used", "", readable_rubric(report["rubric_snapshot"]), "", "## Baseline questions used", "", readable_rubric(report["baseline_rubric_snapshot"])]
    if report.get("gate_only_rubric_snapshot"):
        lines += ["", "## Gate-only ablation questions", "", readable_rubric(report["gate_only_rubric_snapshot"])]
    variants = list(report["metrics"]["all"])
    for rubric in variants:
        lines += ["", f"## {rubric.title()} top ten", "", "| Rank | Record | Score | Coverage | Manual priority | Payment judgment | Route | Need status |", "|---|---|---|---|---|---|---|---|"]
        for i, row in enumerate(ranking(report["records"], rubric)[:10], 1):
            result = row[rubric]
            lines.append(f"| {i} | {escape(row['id'])} | {result['score']} | {escape(result.get('coverage_label', 'production lower bound'))} | {row['annotation']['priority']} | {escape(result.get('payment_signal', 'see raw judgments'))} | {escape(result.get('route', 'production'))} | {escape(result.get('need_status', 'not assessed'))} |")
        lines += ["", f"### {rubric.title()} holdout top ten", "", "| Rank | Record | Score | Coverage | Manual priority |", "|---|---|---|---|---|"]
        heldout = [r for r in report["records"] if r["annotation"]["split"] == "holdout"]
        for i, row in enumerate(ranking(heldout, rubric)[:10], 1):
            result = row[rubric]
            lines.append(f"| {i} | {escape(row['id'])} | {result['score']} | {escape(result.get('coverage_label', 'production lower bound'))} | {row['annotation']['priority']} |")
    lines += ["", "## Traceable records and annotations", ""]
    for row in report["records"]:
        lines += [f"### {row['id']}: {row.get('title', '')}", "", f"Source: {row['url']} · Author: {row.get('author') or 'unknown'} · Date: {row.get('published_at') or 'unknown'}", "", f"Manual annotation: {json.dumps(row['annotation'], ensure_ascii=False)}", "", "Source excerpt:", "", "> " + row["content"][:1200].replace("\n", "\n> "), "", f"Baseline: {row['baseline']['score']} · accepted: {row['baseline']['accepted']}", f"Revised: {row['revised']['score']} · accepted: {row['revised']['accepted']} · coverage: {row['revised']['coverage_weight']}% · payment: {row['revised']['payment_signal']}", ""]
        for rubric in ("baseline", "revised"):
            raw = _raw_dict(row[rubric])
            lines += [f"{rubric.title()} model: {raw.get('model', 'unavailable')} · usage: {json.dumps(raw.get('usage', {}))}", ""]
            if row[rubric].get("error"):
                lines += [f"Evaluation failure: {row[rubric]['error']}. This is not a model rejection.", ""]
            lines += ["| Question | Judgment | Confidence | Probability distribution |", "|---|---|---|---|"]
            for name, answer in raw.get("answers", {}).items():
                if isinstance(answer, dict):
                    value = answer.get("score", answer.get("noul", answer.get("choice", "unavailable")))
                    lines.append(f"| {escape(name)} | {escape(value)} | {escape(answer.get('confidence', 'unavailable'))} | {escape(json.dumps(answer.get('probabilities', {})))} |")
            lines.append("")
    lines += ["Full raw responses, confidence, probability distributions, model versions, usage, source content, and frozen questions are retained in the companion JSON.", ""]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main(argv=None):
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("compare")
    command.add_argument("dataset", type=Path)
    command.add_argument("--db", default="benchmark.db")
    command.add_argument("--output", default="reports/jev-comparison")
    command.add_argument("--max-requests", type=int, default=90)
    command.add_argument("--max-cost", type=float, default=.05)
    command.add_argument("--rubric", default="v1", help="v1, v2, or a custom JSON path")
    command.add_argument("--reference-rubric", help="Compare against another experimental rubric instead of production")
    command.add_argument("--gate-only-rubric", help="Also evaluate a hard_v1 rubric with only its genuine cutoff removed")
    preview = commands.add_parser("questions", help="Show exact readable questions and routing; makes no API calls")
    preview.add_argument("--rubric", default="v2", help="production, v1, v2, or a JSON path")
    preview.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = parser.parse_args(argv)
    if args.command == "questions":
        rubric = load_rubric(args.rubric)
        print(json.dumps(rubric, indent=2, ensure_ascii=False) if args.format == "json" else readable_rubric(rubric))
        return
    if args.max_requests < 1 or not math.isfinite(args.max_cost) or args.max_cost < 0:
        parser.error("Request limit must be positive and cost finite/nonnegative")
    async def run():
        rubric = load_rubric(args.rubric)
        reference_rubric = load_rubric(args.reference_rubric) if args.reference_rubric else None
        gate_only_rubric = load_rubric(args.gate_only_rubric) if args.gate_only_rubric else None
        if "routing" not in rubric or (reference_rubric and "routing" not in reference_rubric):
            raise ValueError("compare requires experimental rubrics; production is the default baseline")
        print(f"Testing {rubric['version']} SHA256={rubric_hash(rubric)} against {reference_rubric['version'] if reference_rubric else 'production'}", flush=True)
        dataset_bytes = args.dataset.read_bytes()
        records = json.loads(dataset_bytes)
        price = float(os.environ.get("JEV_COST_PER_MILLION_INPUT_TOKENS") or ".042")
        if not math.isfinite(price) or price < 0:
            raise ValueError("JEV price must be finite and nonnegative")
        with Store(args.db) as store:
            async with HTTP(store, max_requests=args.max_requests, max_cost=args.max_cost, prices={"jev": price}) as http:
                report = await compare(records, http, os.environ.get("TYPESAFE_API_KEY", ""), os.environ.get("JEV_MODEL", "jev-latest"), rubric=rubric, reference_rubric=reference_rubric, gate_only_rubric=gate_only_rubric)
                report["fingerprints"]["dataset_file_sha256"] = hashlib.sha256(dataset_bytes).hexdigest()
                write_comparison(report, args.output)
                print(json.dumps(report["metrics"], indent=2))
    asyncio.run(run())


if __name__ == "__main__":
    main()
