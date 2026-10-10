from dataclasses import replace

import pytest

from problem_hunter.discovery_audit import audit_sources, summarize_yield
from problem_hunter.models import Opportunity, Problem, Source


@pytest.mark.asyncio
async def test_normalization_dedup_attribution_and_no_input_mutation():
    a = Source("https://example.com/a?utm_source=x", "A", "one", author="alice", metadata={"discovery_provider": "hn"})
    duplicate = replace(a, url="https://example.com/a")
    invalid = Source("file:///secret", "bad", "private")
    audit = await audit_sources([a, duplicate, invalid])
    assert audit["metrics"]["raw_results"] == 3
    assert audit["metrics"]["duplicates_removed"] == 1
    assert audit["metrics"]["invalid_results"] == 1
    assert audit["metrics"]["attributed_full_text"] == 1
    assert audit["metrics"]["upstream_raw_results"] is None
    assert audit["metrics"]["useful_complaints"] is None
    assert a.id == "" and "duplicate_urls" not in a.metadata
    assert audit["sources"][0].url == "https://example.com/a"


@pytest.mark.asyncio
async def test_enrichment_success_policy_failure_and_postfetch_dedup():
    inputs = [Source(f"https://example.com/{i}", "", f"snippet{i}", content_kind="snippet", metadata={"discovery_provider": "brave"}) for i in range(3)]
    class Extractor:
        async def enrich(self, source):
            if source.url.endswith("2"):
                raise PermissionError("Robots denied")
            return replace(source, content="same copied text " * 20, content_kind="full_text", author="alice", metadata={**source.metadata, "extraction": "public page"})
    result = await audit_sources(inputs, Extractor(), enrich=True)
    metrics = result["metrics"]
    assert metrics["fetch_attempts"] == 3
    assert metrics["fetch_successes"] == 2
    assert metrics["duplicates_after_fetch"] == 1
    assert metrics["retained"] == 2 and metrics["snippets"] == 1
    assert metrics["fallback_count"] == 1
    assert "Robots denied" in metrics["failures"][0]["error"]
    with pytest.raises(ValueError, match="extractor"):
        await audit_sources(inputs, enrich=True)


def test_funnel_separates_costs_and_ignores_orphan_problems():
    sources = [Source("https://example.com/a", "", "full", id="a", author="alice"), Source("", "", "imported", id="b", content_kind="imported", metadata={"import_file": "input.csv"})]
    problems = [Problem("a", "pain", "other", id="p1"), Problem("b", "pain2", "other", id="p2"), Problem("missing", "orphan", "other", id="p3")]
    groups = [Opportunity("g", "group", "", "other", problem_ids=["p1", "p2"])]
    logs = [{"provider": "brave", "cost": .01}, {"provider": "jev", "cost": .02}, {"provider": "llm", "cost": .03}, {"provider": "brave", "cost": None, "cached": True}]
    summary = summarize_yield(sources, problems, groups, logs)
    assert summary["funnel"] == {"sources": 2, "qualifying_problems": 2, "sources_with_qualifying_problems": 2, "recurring_groups": 1,
                                  "recurring_report_groups": 1, "recurring_independent_user_groups": 0}
    assert summary["full_content_yield"] == .5
    assert summary["costs"]["collection_cost_usd"] == .01
    assert summary["costs"]["evaluation_cost_usd"] == .02
    assert summary["costs"]["research_cost_usd"] == .03
    assert summary["collection_cost_per_useful_source_usd"] == .005
    assert summary["total_cost_per_useful_source_usd"] == pytest.approx(.03)


def test_unknown_prices_and_missing_logs_never_imply_free():
    source = Source("", "", "body", id="a")
    problem = Problem("a", "pain", "other", id="p")
    summary = summarize_yield([source], [problem], [], [{"provider": "brave", "cost": None}, {"provider": "jev", "cost": .02}])
    assert summary["costs"]["collection_cost_usd"] is None
    assert summary["costs"]["total_cost_usd"] is None
    assert summary["costs"]["evaluation_cost_usd"] == .02
    assert summary["total_cost_per_useful_source_usd"] is None
    assert summary["collection_cost_per_useful_source_usd"] is None
    assert summarize_yield([], [], [])["costs"]["collection_cost_usd"] is None
    aggregate = {"providers": {"web": {"requests": 1, "cache_hits": 0, "network_requests": 1, "priced_requests": 0, "unpriced_requests": 1, "estimated_cost": None}}}
    assert summarize_yield([], [], [], aggregate)["costs"]["unknown_prices"]


def test_explicit_phase_overrides_provider_for_research_calls():
    logs = [{"provider": "brave", "phase": "collection", "cost": .01},
            {"provider": "jev", "phase": "evaluation", "cost": .02},
            {"provider": "brave", "phase": "research", "cost": .03},
            {"provider": "jev", "phase": "research", "cost": .04}]
    costs = summarize_yield([], [], [], logs)["costs"]
    assert costs["phase_allocation"] == "explicit"
    assert costs["collection_cost_usd"] == .01
    assert costs["evaluation_cost_usd"] == .02
    assert costs["research_cost_usd"] == pytest.approx(.07)
    assert costs["providers"]["brave"]["requests"] == 2
    logs[0]["phase"] = "old-unknown"
    fallback = summarize_yield([], [], [], logs)["costs"]
    assert fallback["phase_allocation"] == "approximate_provider_fallback"
    assert fallback["approximate_phase_requests"] == 1


def test_aggregate_phases_override_provider_and_detect_incomplete_coverage():
    def summary(cost):
        return {"requests": 1, "cache_hits": 0, "network_requests": 1,
                "priced_requests": 1, "unpriced_requests": 0, "estimated_cost": cost}
    aggregate = {"providers": {"jev": summary(.04)}, "phases": {"research": summary(.04)}}
    costs = summarize_yield([], [], [], aggregate)["costs"]
    assert costs["research_cost_usd"] == .04
    assert costs["evaluation_cost_usd"] == 0
    assert costs["phase_allocation"] == "explicit"
    aggregate["phases"] = {}
    assert summarize_yield([], [], [], aggregate)["costs"]["research_cost_usd"] is None
    del aggregate["phases"]
    costs = summarize_yield([], [], [], aggregate)["costs"]
    assert costs["evaluation_cost_usd"] == .04
    assert costs["phase_allocation"] == "approximate_provider_fallback"


def test_recurring_independent_users_require_distinct_authors_and_declared_counts():
    sources = [Source("", "", "a", id="a", author="alice"), Source("", "", "b", id="b", author="bob")]
    problems = [Problem("a", "", "", id="p1"), Problem("b", "", "", id="p2")]
    opportunity = Opportunity("g", "", "", "", problem_ids=["p1", "p2"], independent_complainants=2)
    assert summarize_yield(sources, problems, [opportunity])["funnel"]["recurring_independent_user_groups"] == 1
    sources[1].author = "alice"
    funnel = summarize_yield(sources, problems, [opportunity])["funnel"]
    assert funnel["recurring_report_groups"] == 1 and funnel["recurring_independent_user_groups"] == 0
    sources[1].author = "bob"
    opportunity.independent_complainants = 1
    assert summarize_yield(sources, problems, [opportunity])["funnel"]["recurring_independent_user_groups"] == 0


@pytest.mark.asyncio
async def test_csv_import_and_csv_row_metadata_are_provider_csv():
    rows = [Source("", "", "one", content_kind="imported", metadata={"import_file": "input.csv"}),
            Source("", "", "two", content_kind="imported", metadata={"csv_row": 0})]
    result = await audit_sources(rows)
    assert result["metrics"]["providers"]["csv"]["raw_results"] == 2
