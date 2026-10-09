"""Portable opportunity reports retaining supporting evidence and uncertainty."""
from dataclasses import asdict
import json
from pathlib import Path


def _text(value):
    if isinstance(value, dict):
        return "; ".join(f"{key}: {_text(item)}" for key, item in value.items())
    if isinstance(value, list):
        return ", ".join(_text(item) for item in value)
    return str(value)


def export_report(opportunities, sources, path, format="markdown", problems=None):
    if format not in ("markdown", "json"):
        raise ValueError("Report format must be markdown or json")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    opportunities = sorted(opportunities, key=lambda item: (-item.score, item.id))
    source_map = {source.id: source for source in sources}
    problem_map = {problem.id: problem for problem in (problems or [])}
    referenced = {id for item in opportunities for id in item.source_ids}
    referenced_problems = {id for item in opportunities for id in item.problem_ids}
    payload = {"schema_version": 1,
        "score_note": "Opportunity score is distinct from evidence strength and does not prove market demand.",
        "opportunities": [asdict(item) for item in opportunities],
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
    for rank, item in enumerate(opportunities, 1):
        lines += [f"## {rank}. {item.title}", "", item.description, "",
            f"Opportunity ID: `{item.id}` | Category: {item.category}", "",
            f"Opportunity score: {item.score:.1f}/100 | Evidence strength: {item.evidence_strength}", "",
            f"Independent supporting sources: {item.independent_sources} | "
            f"Independent complainants: {item.independent_complainants}", "",
            f"Research status: {item.research_status} | Bookmarked: {'yes' if item.bookmarked else 'no'}", "",
            "### Scoring breakdown and evidence coverage", ""]
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
        lines += ["", "### Individual judgments and literal evidence", ""]
        if not item.problem_ids:
            lines += ["- No individual problem judgments recorded."]
        for problem_id in item.problem_ids:
            problem = problem_map.get(problem_id)
            if problem is None:
                lines += [f"- `{problem_id}`: individual judgments unavailable."]
                continue
            mode = problem.judgments.get("evaluation_mode", problem.evidence.get("mode", "unknown"))
            lines += [f"- `{problem_id}` ({problem.source_id}); evaluation mode: {mode}; {problem.statement}",
                      f"- Model judgments (inferences): {_text(problem.judgments)}"]
            source = source_map.get(problem.source_id)
            excerpts = [(key, value) for key, value in problem.evidence.items()
                        if key in {'genuine', 'first_hand', 'workaround', 'loss', 'willingness_to_pay'}
                        and isinstance(value, str) and value]
            for field, excerpt in excerpts:
                if source and excerpt in source.content:
                    lines += [f"- Literal {field} excerpt from `{problem.source_id}`: "
                              + json.dumps(excerpt, ensure_ascii=False)]
                else:
                    lines += [f"- {field}: excerpt could not be verified against the stored source."]
            if not excerpts:
                lines += ["- No literal evidence excerpts recorded."]
        for label, values, empty in (
                ("Existing solutions and weaknesses", item.solutions, "No existing solutions verified."),
                ("Potential fixes (hypotheses, requiring validation)", item.potential_fixes, "No fixes proposed."),
                ("Important unknowns", item.unknowns, "No unknowns recorded; this does not establish validation.")):
            lines += ["", f"### {label}", ""]
            lines += [f"- {_text(value)}" for value in values] or [f"- {empty}"]
        lines += ["", "### Recommended next validation step", "", item.next_step, ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
