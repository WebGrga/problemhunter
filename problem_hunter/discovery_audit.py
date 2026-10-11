"""Read-only source yield accounting using conservative existing extraction.

Counts describe the supplied sample, never market prevalence or demand. This
module neither searches nor evaluates complaints and never bypasses access policy.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import replace

from .discovery import deduplicate, normalize_url
from .extraction import date_exclusion


def _provider(source):
    return source.metadata.get("discovery_provider") or ("csv" if _csv(source) else source.source)


def _csv(source):
    return any(key in source.metadata for key in ("import_file", "import_row", "csv_row"))


def _counts(sources):
    kinds = Counter(s.content_kind for s in sources)
    return {
        "retained": len(sources), "full_text": kinds["full_text"],
        "snippets": kinds["snippet"], "imported_content": kinds["imported"],
        "attributed_full_text": sum(s.content_kind == "full_text" and bool((s.author or "").strip()) for s in sources),
        "attributed_content": sum(bool((s.author or "").strip()) for s in sources),
        "independent_authors": len({(s.source, s.author.strip()) for s in sources if (s.author or "").strip()}),
        "independent_threads": len({str(s.metadata.get("story_id") or s.metadata.get("thread_url") or s.url or s.id) for s in sources}),
    }


async def audit_sources(sources, extractor=None, enrich=False):
    """Normalize/deduplicate Sources, optionally using Extractor.enrich.

    Raw counts start at this function's boundary. Discovery.search and import_csv
    may have deduplicated beforehand; those upstream counts cannot be reconstructed.
    Inputs are copied so duplicate metadata and source IDs are not modified.
    fetch_attempts count enrich calls, not robots/page network requests.
    """
    if enrich and extractor is None:
        raise ValueError("An access-policy-aware extractor is required for enrichment")
    raw = [deepcopy(s) for s in sources]
    valid, failures = [], []
    for source in raw:
        try:
            if source.url:
                source.url = normalize_url(source.url)
            valid.append(source)
        except ValueError as exc:
            failures.append({"provider": _provider(source), "stage": "normalization", "error": str(exc)})
    normalized = deduplicate(valid)
    before = len(normalized)
    attempts, successes, fallback = 0, 0, 0
    attempted_by_provider, success_by_provider = Counter(), Counter()
    results = []
    for source in normalized:
        provider = _provider(source)
        if enrich and source.content_kind != "full_text" and source.url:
            attempts += 1
            attempted_by_provider[provider] += 1
            try:
                fetched = await extractor.enrich(source)
            except Exception as exc:
                fetched = replace(source, metadata={**source.metadata, "extraction_error": f"{type(exc).__name__}: {exc}"})
            if fetched.content_kind == "full_text" and fetched.content.strip():
                successes += 1
                success_by_provider[provider] += 1
            else:
                fallback += 1
                failures.append({"provider": provider, "url": source.url, "stage": "extraction", "error": fetched.metadata.get("extraction_error", "No full content returned")})
            source = fetched
        results.append(source)
    excluded_dates = [{'url': s.url, 'published_at': s.metadata.get('original_published_at'), 'reason': date_exclusion(s)}
                      for s in results if date_exclusion(s)]
    retained = deduplicate([s for s in results if not date_exclusion(s)])
    provider_rows = defaultdict(list)
    for source in retained:
        provider_rows[_provider(source)].append(source)
    raw_counts = Counter(_provider(s) for s in raw)
    metrics = {
        "raw_results": len(raw), "raw_scope": "audit_inputs",
        "upstream_raw_results": None,
        "upstream_note": "Search/import services may already have deduplicated; provider raw totals require collection instrumentation",
        "invalid_results": len(raw) - len(valid),
        "duplicates_removed": len(valid) - len(retained) - len(excluded_dates),
        "duplicates_before_fetch": len(valid) - before,
        "duplicates_after_fetch": len(results) - len(retained) - len(excluded_dates),
        "excluded_by_original_date": excluded_dates,
        **_counts(retained), "fetch_attempts": attempts, "fetch_successes": successes,
        "fallback_count": fallback, "failures": failures,
        "providers": {p: {"raw_results": raw_counts[p], **_counts(provider_rows[p]),
                            "fetch_attempts": attempted_by_provider[p], "fetch_successes": success_by_provider[p]}
                      for p in raw_counts},
        "provenance": dict(Counter(s.metadata.get("extraction") or s.metadata.get("discovery_provider") or ("csv import" if _csv(s) else "supplied source") for s in retained)),
        "useful_complaints": None,
        "limitations": ["Content/attribution yield only; no complaint usefulness evaluation",
                       "Imported CSV bodies are not verified complete original posts",
                       "Independent author/thread counts are observed identities, not verified unique people",
                       "Fetch counts are enrichment operations, not network request counts",
                       "Sample yield is not market frequency"],
    }
    return {"sources": retained, "metrics": metrics}


def _costs(request_logs):
    """Accept raw Store request rows or Store.usage_summary()."""
    if request_logs is None:
        return {"available": False, "collection_cost_usd": None, "evaluation_cost_usd": None,
                "research_cost_usd": None, "total_cost_usd": None, "requests": None,
                "unknown_prices": True}
    phase_names = {"collection", "evaluation", "research"}
    phases, approximate_requests = {}, 0

    def default_phase(provider):
        return "evaluation" if provider == "jev" else "research" if provider == "llm" else "collection"

    def blank():
        return {"requests": 0, "cache_hits": 0, "network_requests": 0,
                "priced_requests": 0, "unpriced_requests": 0, "estimated_cost": 0.0}

    def add_row(summary, row):
        summary["requests"] += 1
        if row.get("cached"):
            summary["cache_hits"] += 1
        else:
            summary["network_requests"] += 1
            if row.get("cost") is None:
                summary["unpriced_requests"] += 1
            else:
                summary["priced_requests"] += 1
                summary["estimated_cost"] += row["cost"]

    incomplete_phases = False
    if isinstance(request_logs, dict) and "providers" in request_logs:
        providers = deepcopy(request_logs["providers"])
        if "phases" in request_logs:
            phases = deepcopy(request_logs["phases"])
            incomplete_phases = (any(name not in phase_names for name in phases)
                                 or sum(p["requests"] for p in phases.values()) != sum(p["requests"] for p in providers.values()))
        else:
            # Old aggregate logs cannot distinguish Brave/JEV research calls.
            for provider, values in providers.items():
                summary = phases.setdefault(default_phase(provider), blank())
                for key in summary:
                    summary[key] += values.get(key) or 0
                approximate_requests += values["requests"]
    else:
        providers = {}
        for row in request_logs:
            row = dict(row)
            add_row(providers.setdefault(row["provider"], blank()), row)
            phase = row.get("phase")
            if phase not in phase_names:
                phase = default_phase(row["provider"])
                approximate_requests += 1
            add_row(phases.setdefault(phase, blank()), row)
    result = {"available": True, "providers": providers, "phases": phases,
              "phase_allocation": "incomplete" if incomplete_phases else "approximate_provider_fallback" if approximate_requests else "explicit",
              "approximate_phase_requests": approximate_requests,
              "requests": sum(p["requests"] for p in providers.values()),
              "cache_hits": sum(p["cache_hits"] for p in providers.values()),
              "network_requests": sum(p["network_requests"] for p in providers.values()),
              "unpriced_requests": sum(p["unpriced_requests"] for p in providers.values()),
              "known_cost_subtotal_usd": sum(p.get("estimated_cost") or 0 for p in providers.values())}
    for name in phase_names:
        values = phases.get(name, blank())
        result[f"{name}_cost_usd"] = None if incomplete_phases or values["unpriced_requests"] else values.get("estimated_cost") or 0.0
    result["unknown_prices"] = result["unpriced_requests"] > 0
    result["total_cost_usd"] = None if result["unknown_prices"] else result["known_cost_subtotal_usd"]
    result["note"] = "Estimates from logged configured prices; unknown prices are not free. Explicit phases override providers: Brave solution search and JEV solution classification may be research. Missing/unknown phases use approximate provider allocation; incomplete aggregate phases leave stage costs unknown."
    return result


def summarize_yield(sources, problems, opportunities, request_logs=None):
    """Summarize caller-retained evaluator problems and recurring groups.

    The caller must supply already qualifying problems. No new classification is
    performed here; neither relevance nor usefulness is inferred from raw Sources.
    """
    sources, problems, opportunities = list(sources), list(problems), list(opportunities)
    indexed = {s.id: s for s in sources}
    problems = [p for p in problems if p.source_id in indexed]
    problem_ids = {p.id for p in problems}
    useful_ids = {p.source_id for p in problems}
    recurring, independent_users = [], []
    for opportunity in opportunities:
        members = {p.source_id for p in problems if p.id in set(opportunity.problem_ids) & problem_ids}
        if len(members) >= 2:
            recurring.append(opportunity)
            authors = {(indexed[sid].source, indexed[sid].author.strip())
                       for sid in members if (indexed[sid].author or "").strip()}
            declared = getattr(opportunity, "independent_complainants", None)
            if len(authors) >= 2 and (declared is None or declared >= 2):
                independent_users.append(opportunity)
    costs = _costs(request_logs)
    providers = defaultdict(list)
    for source in sources:
        providers[_provider(source)].append(source)
    return {
        **_counts(sources),
        "funnel": {"sources": len(sources), "qualifying_problems": len(problems),
                   "sources_with_qualifying_problems": len(useful_ids), "recurring_groups": len(recurring),
                   "recurring_report_groups": len(recurring), "recurring_independent_user_groups": len(independent_users)},
        "qualification": "Caller-supplied evaluator-retained problems; usefulness/relevance threshold belongs to caller, not this audit",
        "qualifying_source_yield": len(useful_ids) / len(sources) if sources else 0.0,
        "full_content_yield": sum(s.content_kind == "full_text" for s in sources) / len(sources) if sources else 0.0,
        "author_yield": sum(bool((s.author or "").strip()) for s in sources) / len(sources) if sources else 0.0,
        "providers": {name: {**_counts(rows), "sources_with_qualifying_problems": sum(s.id in useful_ids for s in rows)} for name, rows in providers.items()},
        "costs": costs,
        "collection_cost_per_useful_source_usd": costs["collection_cost_usd"] / len(useful_ids) if costs["collection_cost_usd"] is not None and useful_ids else None,
        "total_cost_per_useful_source_usd": costs["total_cost_usd"] / len(useful_ids) if costs["total_cost_usd"] is not None and useful_ids else None,
        "limitations": ["Yield describes this sample; it is not market frequency or demand validation",
                       "recurring_groups is the compatibility alias for recurring_report_groups: two deduplicated source IDs",
                       "recurring_independent_user_groups additionally requires two observed author identities and at least two declared independent complainants when that field is available",
                       "Anonymous sources cannot establish independent complainants",
                       "Request logs must be scoped to this run for run-level cost comparisons"],
    }
