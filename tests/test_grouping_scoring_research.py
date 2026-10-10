import pytest

from problem_hunter.models import Source, Problem
from problem_hunter.grouping import group_problems, semantic_group
from problem_hunter.scoring import score_opportunity
from problem_hunter.research import Researcher


def fixture():
    sources = [Source(f"https://example.com/{i}", "Appointments", content, author=author, id=str(i)) for i, (content, author) in enumerate([
        ("I waste hours managing appointments manually.", "alice"),
        ("We waste hours managing bookings manually.", "bob"),
        ("I waste hours managing appointments manually.", "charlie"),
    ])]
    problems = [Problem(s.id, s.content, "services", {"severity": .75, "first_hand": 1, "loss": 1, "willingness_to_pay": 1}, {"first_hand": s.content, "loss": s.content, "mode": "jev"}, str(i)) for i, s in enumerate(sources)]
    return sources, problems


def test_equivalent_appointments_group_and_copies_do_not_inflate_counts():
    sources, problems = fixture()
    result = group_problems(problems, sources)
    assert len(result) == 1
    assert result[0].independent_sources == 2
    assert result[0].independent_complainants == 2
    assert len(result[0].source_ids) == 3


def test_unknown_authors_are_not_reported_as_known_people():
    sources, problems = fixture()
    for source in sources:
        source.author = None
    result = group_problems(problems, sources)[0]
    assert result.independent_sources == 2
    assert result.independent_complainants == 0


def test_shared_pain_language_does_not_merge_distinct_workflows():
    sources, problems = fixture()
    problems.append(Problem("4", "I waste hours managing invoices manually.", "services", id="4"))
    assert len(group_problems(problems, sources)) == 2


def test_score_does_not_turn_probability_into_payment_evidence():
    sources, problems = fixture()
    opportunity = score_opportunity(group_problems(problems, sources)[0], problems, sources)
    assert opportunity.score == 26.75
    assert opportunity.score_breakdown["willingness_to_pay"]["value"] is None
    assert opportunity.score_breakdown["methodology"]["coverage_weight"] == 45
    assert opportunity.evidence_strength == "weak"
    assert opportunity.score_breakdown["feasibility"]["points"] == 0


def test_payment_counts_independent_authors_and_rejects_invented_quotes():
    sources, problems = fixture()
    sources[0].content += " I would pay for automation."
    sources[1].content += " I would pay for automation."
    sources[0].author = sources[1].author = "same-author"
    for p in problems[:2]:
        p.evidence["willingness_to_pay"] = "I would pay for automation."
    problems[2].evidence["willingness_to_pay"] = "I pay $500 for a solution."
    opportunity = score_opportunity(group_problems(problems, sources)[0], problems, sources)
    assert opportunity.score_breakdown["willingness_to_pay"]["points"] == 6.67


@pytest.mark.asyncio
async def test_semantic_grouping_requires_exact_partition():
    sources, problems = fixture()
    class LLM:
        async def ask(self, *args):
            return {"groups": [["invented-id"]]}
    with pytest.raises(ValueError, match="partition"):
        await semantic_group(problems, sources, LLM())


@pytest.mark.asyncio
async def test_research_keeps_literal_prices_weaknesses_and_hypotheses():
    sources, problems = fixture()
    opportunity = group_problems(problems, sources)[0]
    product = Source("https://vendor.example", "Example scheduler", "Plans start at $20/month. I find this expensive and missing reminders.", id="product")
    class Discovery:
        calls = 0
        async def search(self, *args, **kwargs):
            self.calls += 1
            return [product]
    class Extractor:
        async def enrich(self, source):
            return source
    discovery = Discovery()
    await Researcher(discovery, Extractor()).research([opportunity], top=1)
    assert discovery.calls == 2
    assert len(opportunity.solutions) == 1
    solution = opportunity.solutions[0]
    assert solution["pricing_quote"] in product.content
    assert solution["weakness_quote"] in product.content
    assert opportunity.potential_fixes[0]["status"] == "hypothesis"
    assert opportunity.research_status == "researched"


@pytest.mark.asyncio
async def test_research_network_failure_is_partial():
    sources, problems = fixture()
    opportunity = group_problems(problems, sources)[0]
    class Discovery:
        async def search(self, *args, **kwargs):
            raise OSError("network unavailable")
    await Researcher(Discovery(), None).research([opportunity])
    assert opportunity.research_status == "partial"


@pytest.mark.asyncio
async def test_llm_research_promotes_only_source_grounded_workflow_quotes():
    sources, problems = fixture()
    opportunity = group_problems(problems, sources)[0]
    product = Source("https://vendor.example", "Scheduler", "This tool automates appointments. I find this expensive and missing reminders.", id="product")
    class Discovery:
        async def search(self, *args, **kwargs):
            return [product]
    class Extractor:
        async def enrich(self, source):
            return source
    class LLM:
        async def ask(self, *args):
            return {"solutions": [{"url": product.url, "role": "product", "relevant": True,
                    "functional_quote": "This tool automates appointments.", "weakness_quote": "I find this expensive and missing reminders.", "rationale": "Same appointment workflow"}],
                    "potential_fixes": ["Prototype a simpler appointment workflow"], "unknowns": ["Pricing not found"]}
    await Researcher(Discovery(), Extractor(), llm=LLM()).research([opportunity])
    solution = opportunity.solutions[0]
    assert solution["relevance"] == "verified"
    assert solution["verification_method"] == "model_source_check"
    assert solution["relevance_rationale"]["status"] == "inference"
    score_opportunity(opportunity, problems, sources)
    assert opportunity.score_breakdown["solution_weakness"]["points"] == 5


@pytest.mark.asyncio
async def test_llm_research_fabricated_quote_does_not_promote_candidate():
    sources, problems = fixture()
    opportunity = group_problems(problems, sources)[0]
    product = Source("https://vendor.example", "Scheduler", "Unrelated marketing text", id="product")
    class Discovery:
        async def search(self, *args, **kwargs):
            return [product]
    class Extractor:
        async def enrich(self, source):
            return source
    class LLM:
        async def ask(self, *args):
            return {"solutions": [{"url": product.url, "role": "product", "relevant": True, "functional_quote": "We manage appointments"}], "potential_fixes": [], "unknowns": []}
    await Researcher(Discovery(), Extractor(), llm=LLM()).research([opportunity])
    assert opportunity.solutions[0]["relevance"] == "unverified"
