"""Portable opportunity reports retaining supporting evidence and uncertainty."""
from dataclasses import asdict
import json
from pathlib import Path

from .evidence_checks import ground_payment


def _text(value):
    if isinstance(value, dict):
        return "; ".join(f"{key}: {_text(item)}" for key, item in value.items())
    if isinstance(value, list):
        return ", ".join(_text(item) for item in value)
    return str(value)


def _verified_quote(value, source):
    return isinstance(value, str) and bool(value.strip()) and source is not None and value in source.content


def _excerpt(value, limit=700):
    text = str(value)
    return text if len(text) <= limit else text[:limit] + ' … [truncated; complete text in JSON]'


def _actionable_summary(item, source_map, problem_map):
    cards, quotes, statuses, payments, cautions = [], [], [], [], list(item.unknowns)
    dimensions = {}
    for problem_id in item.problem_ids:
        problem = problem_map.get(problem_id)
        if problem is None:
            cautions.append(f"Individual judgments unavailable: {problem_id}.")
            continue
        source = source_map.get(problem.source_id)
        triage = problem.judgments.get("triage", {})
        status = triage.get("need_status", "unknown")
        statuses.append({"problem_id": problem_id, "source_id": problem.source_id, "status": status})
        card = {"problem_id": problem_id, "source_id": problem.source_id,
                "source_url": source.url if source else None, "complaint": problem.statement,
                "need_status": status, "quotes": [],
                "evaluation_mode": problem.judgments.get("evaluation_mode", problem.evidence.get("mode", "unknown"))}
        for name in ("genuine", "first_hand", "impact", "workaround", "loss", "literal_loss", "willingness_to_pay"):
            quote = problem.evidence.get(name)
            if not isinstance(quote, str) or not quote.strip():
                continue
            if _verified_quote(quote, source):
                entry = {"field": name, "quote": quote, "source_id": problem.source_id,
                         "source_url": source.url, "problem_id": problem_id}
                card["quotes"].append(entry)
                if name != "willingness_to_pay":
                    quotes.append(entry)
            else:
                cautions.append(f"{name}: excerpt could not be verified against the stored source ({problem.source_id}).")
        payment = problem.evidence.get("verified_payment")
        candidate = problem.evidence.get('payment_candidate')
        if isinstance(candidate, dict) and _verified_quote(candidate.get('quote'), source):
            card['payment_candidate'] = candidate
            cautions.append('A literal payment candidate is selected by JEV; its meaning needs review and does not contribute verified payment points.')
        grounded_payment = (ground_payment(source.content, payment.get("signal"))
                            if source and isinstance(payment, dict) else None)
        if grounded_payment and grounded_payment["quote"] == payment.get("quote"):
            entry = {"signal": payment["signal"], "quote": payment["quote"],
                     "source_id": problem.source_id, "source_url": source.url}
            if entry not in payments:
                payments.append(entry)
        elif triage.get("payment_signal", "unknown") != "unknown" or payment:
            cautions.append(f"Payment signal is unverified for {problem.source_id}; willingness to pay remains unknown.")
        for reason in triage.get("review_reasons", []):
            cautions.append(_text(reason))
        for contradiction in triage.get("contradictions", []):
            cautions.append("Contradiction: " + _text(contradiction))
        for name in triage.get("supported_dimensions", []):
            value = triage.get("dimensions", {}).get(name)
            if isinstance(value, (int, float)):
                dimensions[name] = max(value, dimensions.get(name, value))
        cards.append(card)
    priority = getattr(item, "investigation_priority", None)
    review = getattr(item, "review_required", False)
    if priority is not None:
        observed = ", ".join(f"{name} ({value:.2f})" for name, value in sorted(dimensions.items(), key=lambda pair: (-pair[1], pair[0])))
        reason = f"Investigation priority {priority:.1f}/100; {'review required' if review else 'primary research candidate'}."
        reason += f" Supported triage dimensions: {observed}." if observed else " Supported triage dimensions are unavailable."
    else:
        reason = f"Ranked by commercial opportunity score ({item.score:.1f}/100); investigation priority has not been assessed."
    if any(entry["status"] == "historical_resolved" for entry in statuses):
        cautions.append("Historical resolved complaints do not establish a current unmet need.")
    if not statuses or any(entry["status"] == "unknown" for entry in statuses):
        cautions.append("Current versus historical need is unknown for some evidence.")
    cautions.append("Need status describes the source at publication: ongoing does not establish that the problem still exists today.")
    if not payments:
        cautions.append("No verified payment evidence; willingness to pay is unknown.")
    refusals = [entry for entry in payments if entry["signal"] == "explicit_refusal"]
    if refusals:
        cautions.append("Explicit refusal to pay is evidence against payment intent for those speakers, not evidence of a spending buyer.")
    research_next = item.solution_landscape.get('disposition', {}).get('next_check')
    next_steps = [research_next or item.next_step] if research_next or item.next_step else []
    if not item.solution_landscape:
        next_steps.append("Ask affected users whether the complaint still occurs and what resolved or changed it.")
    if not payments and not item.solution_landscape:
        next_steps.append("Ask affected users what they currently spend on solving this problem and verify any payment claim.")
    elif refusals:
        next_steps.append("Ask refusing users why they would not pay and which free or existing remedy they prefer.")
    universal = any(card['evaluation_mode'] == 'jev_universal_experimental' for card in cards)
    if universal and not item.solution_landscape:
        next_steps.append('Verify the described practical, emotional or social impact and its frequency using a current example; do not require monetary loss.')
        if item.category in {'social_relationships', 'health_wellbeing'}:
            cautions.append('Personal accounts may involve sensitive information or vulnerable people. Use consent and appropriate review; do not infer diagnoses or target individuals from this report.')
    elif not item.solution_landscape and not any(entry["field"] in ("loss", "literal_loss") for entry in quotes):
        next_steps.append("Verify the time or money lost using a concrete recent example.")
    # Prefer direct burden and experience over general problem excerpts.
    quote_order = {"literal_loss": 0, "impact": 0, "loss": 1, "first_hand": 2, "workaround": 3, "genuine": 4}
    quotes.sort(key=lambda entry: quote_order[entry["field"]])
    strongest = []
    seen_quotes = set()
    for entry in quotes:
        identity = (entry["source_id"], entry["quote"])
        if identity not in seen_quotes:
            strongest.append(entry)
            seen_quotes.add(identity)
    return {"investigation_priority": priority, "commercial_opportunity_score": item.score,
            "review_required": review, "ranking_reason": reason,
            "strongest_problem_quotes": strongest[:3], "need_status": statuses,
            "payment_evidence": payments, "cautions": list(dict.fromkeys(cautions)),
            "next_step": " ".join(dict.fromkeys(next_steps)), "evidence_cards": cards}


def _rank_key(item):
    priority = getattr(item, "investigation_priority", None)
    if priority is None:
        return (1, 0, 0, -item.score, item.id)
    if item.priority_breakdown.get('ranking_policy') == 'priority_before_review_flag':
        return (0, 0, -priority, -item.score, item.id)
    return (0, int(getattr(item, "review_required", False)), -priority, -item.score, item.id)


def export_report(opportunities, sources, path, format="markdown", problems=None):
    if format not in ("markdown", "json"):
        raise ValueError("Report format must be markdown or json")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    opportunities = sorted(opportunities, key=_rank_key)
    source_map = {source.id: source for source in sources}
    problem_map = {problem.id: problem for problem in (problems or [])}
    referenced = {id for item in opportunities for id in item.source_ids}
    referenced_problems = {id for item in opportunities for id in item.problem_ids}
    summaries = {item.id: _actionable_summary(item, source_map, problem_map) for item in opportunities}
    payload = {"schema_version": 1,
        "score_note": "Commercial opportunity score is an evidence lower bound, not validated market demand. Experimental investigation priority ranks research attention, not commercial viability. Model judgments are inferences, not proof.",
        "opportunities": [{**asdict(item), "actionable_summary": summaries[item.id]} for item in opportunities],
        "sources": [asdict(source_map[id]) for id in sorted(referenced) if id in source_map],
        "problems": [asdict(problem_map[id]) for id in sorted(referenced_problems) if id in problem_map],
        "missing_source_ids": sorted(referenced - source_map.keys()),
        "missing_problem_ids": sorted(referenced_problems - problem_map.keys())}
    if format == "json":
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path
    lines = ["# Problem Hunter opportunity report", "", payload["score_note"], ""]
    if not opportunities:
        lines += ["No qualifying opportunities were found.", ""]
    else:
        note = 'priority first; review flags remain visible' if any(o.priority_breakdown.get('ranking_policy') == 'priority_before_review_flag' for o in opportunities) else 'primary candidates before review-required candidates'
        lines += [f"Ranked research shortlist ({note}):", ""]
        for rank, item in enumerate(opportunities, 1):
            priority = getattr(item, "investigation_priority", None)
            priority_label = f"{priority:.1f}/100" if priority is not None else "not assessed"
            lines += [f"- {rank}. {item.title} — investigation priority: {priority_label}; commercial opportunity score: {item.score:.1f}/100."]
        lines += [""]
    for rank, item in enumerate(opportunities, 1):
        summary = summaries[item.id]
        lines += [f"## {rank}. {item.title}", "", _excerpt(item.description), "",
            f"Opportunity ID: `{item.id}` | Category: {item.category}", "",
            f"Opportunity score: {item.score:.1f}/100 | Evidence strength: {item.evidence_strength}", "",
            f"Independent supporting sources: {item.independent_sources} | "
            f"Independent complainants: {item.independent_complainants}", "",
            f"Research status: {item.research_status} | Bookmarked: {'yes' if item.bookmarked else 'no'}", "",
            "### Why ranked and current need", "", summary["ranking_reason"], ""]
        lines += [f"- Need status for `{entry['source_id']}`: {entry['status']}" for entry in summary["need_status"]] or ["- Need status: unknown."]
        lines += ["", "### Scoring breakdown and evidence coverage", ""]
        lines += ([f"- {key}: {_text(value)}" for key, value in item.score_breakdown.items()]
                  or ["- Scoring details unavailable; evidence coverage is unknown."])
        lines += ["", "### Original supporting sources", ""]
        for source_id in item.source_ids:
            source = source_map.get(source_id)
            if source is None:
                lines += [f"- `{source_id}`: original source unavailable."]
                continue
            detail = f"{source.source}; {source.content_kind}"
            if source.author:
                detail += f"; author: {source.author}"
            if source.published_at:
                detail += f"; published: {source.published_at}"
            mode = source.metadata.get("evaluation_mode", source.metadata.get("mode"))
            if mode:
                detail += f"; evaluation mode: {mode}"
            lines += [f"- [{source.title or source.url}](<{source.url}>) — {detail}; ID: `{source_id}`"]
            for original_url in source.metadata.get("duplicate_urls", []):
                lines += [f"- [Duplicate/reposted original](<{original_url}>) — supporting copy of `{source_id}`; not an independent report."]
        if not item.source_ids:
            lines += ["- No supporting sources recorded."]
        lines += ["", "### Complaint evidence", ""]
        if not item.problem_ids:
            lines += ["- No individual problem judgments recorded."]
        for card in summary["evidence_cards"][:3]:
            lines += [f"- Complaint summary (model inference): {_excerpt(card['complaint'])}",
                      f"  Source: `{card['source_id']}`; problem: `{card['problem_id']}`; need status: {card['need_status']}; evaluation mode: {card['evaluation_mode']}."]
            seen_quotes = set()
            for entry in card["quotes"]:
                if entry['quote'] in seen_quotes:
                    continue
                seen_quotes.add(entry['quote'])
                label = "payment-related" if entry["field"] == "willingness_to_pay" else entry["field"]
                lines += [f"- Literal {label} excerpt from `{entry['source_id']}`: " + json.dumps(_excerpt(entry["quote"]), ensure_ascii=False)]
            if not card["quotes"]:
                lines += ["- No verified literal evidence excerpts recorded."]
            if card.get('payment_candidate'):
                candidate = card['payment_candidate']
                lines += [f"- Payment candidate ({candidate['signal']}; model interpretation, not verified spending): " + json.dumps(_excerpt(candidate['quote']), ensure_ascii=False)]
        if len(summary["evidence_cards"]) > 3:
            lines += [f"- {len(summary['evidence_cards']) - 3} additional judgments retained in JSON; all supporting sources are linked above."]
        lines += ["", "### Payment evidence", ""]
        for entry in summary["payment_evidence"]:
            lines += [f"- Verified {entry['signal']} excerpt from [{entry['source_id']}](<{entry['source_url']}>): " + json.dumps(_excerpt(entry["quote"]), ensure_ascii=False)]
        if not summary["payment_evidence"]:
            lines += ["- Unknown: no verified payment evidence."]
        lines += ["", "### Existing solutions and weaknesses", ""]
        if item.research_brief:
            brief = item.research_brief
            lines += ["Research brief (explicit user interpretation; review against supporting evidence):", ""]
            for field in ('affected_person', 'task', 'desired_outcome', 'unmet_constraint', 'workflow'):
                lines += [f"- {field.replace('_', ' ').capitalize()}: {brief.get(field, 'Unknown')}"]
            lines += ["- Remedy types: " + ', '.join(brief.get('remedy_types', [])), ""]
        if item.solution_landscape:
            from .landscape import markdown
            lines += markdown(item.solution_landscape)
            lines += ['### Retrieved research pages', '', 'Page titles identify sources; named remedies are compared above.', '']
        for solution in item.solutions:
            lines += [f"- [{solution.get('name', 'Research source')}](<{solution.get('url', '')}>) — {solution.get('status', 'candidate')}; relevance: {solution.get('relevance', 'unverified')}."]
            for field, label in (("functional_quote", "Functional source claim"), ("pricing_quote", "Pricing excerpt (context unverified)"), ("weakness_quote", "Weakness excerpt")):
                if solution.get(field):
                    lines += [f"  {label}: " + json.dumps(_excerpt(solution[field]), ensure_ascii=False)]
        if not item.solutions:
            lines += ["- No existing solutions verified."]
        else:
            lines += ["- Full source text, verification questions and raw judgments are retained in JSON."]
        for label, values, empty in (
                ("Potential fixes (hypotheses, requiring validation)", item.potential_fixes, "No fixes proposed."),
                ("Important unknowns and cautions", summary["cautions"], "No unknowns recorded; this does not establish validation.")):
            lines += ["", f"### {label}", ""]
            lines += [f"- {_text(value)}" for value in values] or [f"- {empty}"]
        lines += ["", "### Recommended next validation step", "", summary["next_step"], ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
