"""Evidence-aware lower-bound opportunity scoring, separate from validation."""
import hashlib
import re

WEIGHTS = {"pain_severity": 25, "frequency": 20, "willingness_to_pay": 20, "solution_weakness": 15, "reachability": 10, "feasibility": 10}


def score_opportunity(opportunity, problems, sources):
    selected = [p for p in problems if p.id in opportunity.problem_ids]
    triages = [p.judgments['triage'] for p in selected if isinstance(p.judgments.get('triage'), dict)]
    scored = [t for t in triages if isinstance(t.get('score'), (int, float))]
    if scored:
        # Average unique identified complainants, not repeated posts from one author.
        by_author = {}
        source_lookup = {s.id: s for s in sources}
        for problem in selected:
            triage = problem.judgments.get('triage', {})
            source = source_lookup.get(problem.source_id)
            if source and isinstance(triage.get('score'), (int, float)):
                identity = (source.source, (source.author or source.id).casefold())
                by_author.setdefault(identity, []).append(triage['score'])
        opportunity.investigation_priority = round(sum(sum(v)/len(v) for v in by_author.values()) / len(by_author), 2) if by_author else None
        opportunity.review_required = any(t.get('route') == 'review' for t in triages)
        families = {t.get('problem_family') for t in triages if t.get('problem_family')}
        opportunity.priority_breakdown = {'method': 'mean priority per observed author, then across authors; inference not demand',
                                           'observed_author_groups': len(by_author),
                                           'problem_family': next(iter(families)) if len(families) == 1 else None,
                                           'record_scores': [t['score'] for t in scored]}
        for t in triages:
            for reason in t.get('review_reasons', []):
                if reason not in opportunity.unknowns:
                    opportunity.unknowns.append(reason)
    source_map = {s.id: s for s in sources}
    def valid_quote(problem, field):
        quote = problem.evidence.get(field)
        source = source_map.get(problem.source_id)
        return isinstance(quote, str) and bool(quote.strip()) and source is not None and quote in source.content
    def independent_reports(items):
        unique = {}
        for problem in items:
            content = source_map[problem.source_id].content
            fingerprint = hashlib.sha256(re.sub(r"\s+", " ", content.casefold()).strip().encode()).hexdigest()
            unique.setdefault(fingerprint, problem)
        return list(unique.values())
    values = {name: None for name in WEIGHTS}
    direct = independent_reports([p for p in selected if valid_quote(p, "loss") and p.judgments.get("loss", 0) >= .6])
    if direct:
        values["pain_severity"] = sum(p.judgments.get("severity", 0) for p in direct) / len(direct)
    if opportunity.independent_complainants:
        # Five identified independent complainants fill this MVP scale. This is
        # observed recurrence, not an estimate of total market size.
        values["frequency"] = min(opportunity.independent_complainants / 5, 1)
    paying = independent_reports([p for p in selected if valid_quote(p, "willingness_to_pay") and p.judgments.get("willingness_to_pay", 0) >= .6])
    if paying:
        identities = {(source_map[p.source_id].source, source_map[p.source_id].author.casefold()) for p in paying if source_map[p.source_id].author}
        if identities:
            values["willingness_to_pay"] = min(len(identities) / 3, 1)
    documented_weaknesses = [s for s in opportunity.solutions if s.get("weakness_quote") and s.get("url") and s.get("status") == "fact" and s.get("relevance") == "verified" and s["weakness_quote"] in s.get("content", "")]
    if documented_weaknesses:
        values["solution_weakness"] = min(len({s["url"] for s in documented_weaknesses}) / 3, 1)
    # Reachability and feasibility require explicit validation data; mere
    # discoverability on the web and plausible coding ideas are insufficient.
    opportunity.score_breakdown = {name: {"weight": weight, "value": values[name], "points": round(weight * (values[name] or 0), 2), "status": "unknown" if values[name] is None else "observed_or_judged"} for name, weight in WEIGHTS.items()}
    opportunity.score = round(sum(v["points"] for v in opportunity.score_breakdown.values()), 2)
    coverage = sum(WEIGHTS[name] for name, value in values.items() if value is not None)
    opportunity.score_breakdown["methodology"] = {"coverage_weight": coverage, "unknowns_contribute_zero": True, "frequency_full_scale_identified_complainants": 5, "payment_full_scale_identified_complainants": 3, "solution_weakness_full_scale_sources": 3, "score_type": "evidence-supported lower bound; not commercial validation"}
    full_text = [s for s in sources if s.id in opportunity.source_ids and s.content_kind == "full_text"]
    live = selected and all(p.evidence.get("mode") != "offline_heuristic" and p.judgments.get("evaluation_mode") != "offline_heuristic" for p in selected)
    opportunity.evidence_strength = "moderate" if live and opportunity.independent_sources >= 3 and len(full_text) >= 3 and direct else "weak"
    for name, value in values.items():
        if value is None:
            unknown = f"Insufficient direct evidence for {name.replace('_', ' ')}."
            if unknown not in opportunity.unknowns:
                opportunity.unknowns.append(unknown)
    if not live and "Offline heuristic judgments are demonstrations, not validated evidence." not in opportunity.unknowns:
        opportunity.unknowns.append("Offline heuristic judgments are demonstrations, not validated evidence.")
    return opportunity
