import copy
from dataclasses import replace

import pytest

from problem_hunter.models import Opportunity, Source
from problem_hunter.research import JEV_ENDPOINT, Researcher


def opportunity():
    return Opportunity("group", "I spend hours doing invoices and chasing records every week", "I manually generate invoices.", "business",
                       priority_breakdown={"problem_family": "invoice_generation"})


class Discovery:
    def __init__(self, sources):
        self.sources, self.queries = sources, []

    async def search(self, query, provider):
        assert provider == "brave"
        self.queries.append(query)
        return self.sources


class Extractor:
    async def enrich(self, source):
        return source


class HTTP:
    def __init__(self, choices=None, mutate=None):
        self.calls = []
        self.choices = choices or {"role": "provider_product", "functional_excerpt": "s0", "weakness_excerpt": "none"}
        self.mutate = mutate

    async def request(self, method, url, **kwargs):
        assert method == "POST" and url == JEV_ENDPOINT and kwargs["provider"] == "jev"
        self.calls.append(kwargs)
        questions = kwargs["json"]["questions"]
        answers = {}
        for name, question in questions.items():
            choice = self.choices.get(name, "none")
            answers[name] = {"type": "choice", "choice": choice, "confidence": 1,
                             "probabilities": {key: float(key == choice) for key in question["criteria"]}}
        payload = {"model": "jev-1.13.0", "answers": answers, "usage": {"input_tokens": 100, "output_tokens": 10}}
        if self.mutate:
            self.mutate(payload)
        class Response:
            def raise_for_status(self):
                pass

            def json(self):
                return copy.deepcopy(payload)
        return Response()


@pytest.mark.asyncio
async def test_supported_jev_choices_ground_provider_and_leave_price_context_unverified():
    source = Source("https://vendor.example", "Invoicer", "Generate invoices with our software. Plans cost $20/month. We solve expensive invoice problems.")
    discovery, http, item = Discovery([source]), HTTP(), opportunity()
    await Researcher(discovery, Extractor(), http=http, jev_key="test").research([item])
    solution = item.solutions[0]
    assert discovery.queries == ["invoice generation software service alternatives pricing", "invoice generation existing tools complaints workaround"]
    assert len(http.calls) == 1
    assert http.calls[0]["headers"] == {"Authorization": "Bearer test"}
    assert set(http.calls[0]["json"]["questions"]) == {"role", "functional_excerpt"}
    assert solution["relevance"] == "verified" and solution["status"] == "fact"
    assert solution["functional_quote"] == "Generate invoices with our software."
    assert solution["verification_method"] == "jev_quote_selection"
    assert solution["weakness_quote"] is None
    assert solution["pricing_quote"] == "Plans cost $20/month."
    assert solution["pricing_quote_status"] == "unverified_context"
    assert solution["retrieved_at"].endswith("+00:00")
    assert solution["jev_judgments"]["model"] == "jev-1.13.0"
    assert solution["relevance_rationale"]["status"] == "inference"
    assert item.potential_fixes[0]["status"] == "hypothesis"


@pytest.mark.asyncio
async def test_undefined_experimental_workflow_does_not_spend_on_generic_search():
    item = opportunity()
    item.investigation_priority = 70
    item.priority_breakdown = {'problem_family': None}
    discovery, http = Discovery([]), HTTP()
    await Researcher(discovery, Extractor(), http=http, jev_key='test').research([item])
    assert item.research_status == 'needs_workflow_definition'
    assert discovery.queries == [] and http.calls == []
    assert any('Define the affected workflow' in warning for warning in item.unknowns)


@pytest.mark.asyncio
@pytest.mark.parametrize("mutate", [
    lambda p: p["answers"].pop("role"),
    lambda p: p["answers"]["functional_excerpt"].update(choice="invented sentence"),
    lambda p: p["answers"]["functional_excerpt"].pop("confidence"),
    lambda p: p["answers"]["role"].update(type="noul"),
    lambda p: p.pop("usage"),
    lambda p: p["answers"]["role"].update(probabilities={"provider_product": 1}),
])
async def test_bad_or_partial_response_never_promotes_candidate(mutate):
    source = Source("https://vendor.example", "Invoicer", "Generate invoices with our software.")
    item = opportunity()
    await Researcher(Discovery([source]), Extractor(), http=HTTP(mutate=mutate), jev_key="test").research([item])
    solution = item.solutions[0]
    assert solution["status"] == "candidate" and solution["relevance"] == "unverified"
    assert solution["verification_method"] == "none"
    assert solution["verification_detail"]["status"] == "failed"
    assert solution["jev_judgments"]["raw_response"]
    assert item.research_status == "partial"


@pytest.mark.asyncio
@pytest.mark.parametrize("role,functional", [("provider_product", "none"), ("customer_discussion", "s0"), ("other", "s0")])
async def test_none_or_nonprovider_is_not_a_verified_solution(role, functional):
    source = Source("https://example.com", "Discussion", "Generate invoices with our software.")
    item = opportunity()
    await Researcher(Discovery([source]), Extractor(), http=HTTP({"role": role, "functional_excerpt": functional}), jev_key="test").research([item])
    assert item.solutions[0]["relevance"] == "unverified"
    assert item.solutions[0]["status"] == "candidate"


@pytest.mark.asyncio
async def test_robots_snippet_fallback_is_partial_without_jev_call():
    source = Source("https://vendor.example", "Invoicer", "Invoice generation $10/month", content_kind="search_snippet")
    class BlockedExtractor:
        async def enrich(self, source):
            return replace(source, metadata={"extraction_error": "PermissionError: Robots policy denies access", "evidence_limit": "Search snippet only"})
    item, http = opportunity(), HTTP()
    await Researcher(Discovery([source]), BlockedExtractor(), http=http, jev_key="test").research([item])
    solution = item.solutions[0]
    assert item.research_status == "partial" and not http.calls
    assert solution["status"] == "candidate" and solution["weakness_quote"] is None
    assert solution["verification_detail"]["retrieved"] is False
    assert "Robots" in solution["verification_detail"]["extraction_error"]
    assert solution["retrieved_at"] is None


@pytest.mark.asyncio
async def test_quote_options_are_literal_relevant_and_bounded_per_source():
    text = "Unrelated marketing. " + " ".join(f"Invoice tool feature {i}." for i in range(12)) + " I find invoice tracking expensive. We prevent expensive invoice problems."
    source = Source("https://vendor.example", "Invoicer", text)
    item, http = opportunity(), HTTP({"role": "provider_product", "functional_excerpt": "s1", "weakness_excerpt": "s13"})
    await Researcher(Discovery([source]), Extractor(), http=http, jev_key="test").research([item])
    questions = http.calls[0]["json"]["questions"]
    assert len(questions["functional_excerpt"]["criteria"]) == 9
    assert questions["weakness_excerpt"]["criteria"] == {"none": "No supported first-hand customer complaint.", "s13": "I find invoice tracking expensive."}
    assert item.solutions[0]["weakness_quote"] == "I find invoice tracking expensive."
    assert item.solutions[0]["pricing_quote"] is None
    assert all(s in text for key, s in questions["functional_excerpt"]["criteria"].items() if key != "none")


@pytest.mark.asyncio
async def test_six_candidate_requests_maximum_and_no_key_preserves_candidates():
    sources = [Source(f"https://vendor{i}.example", "Invoicer", "Generate invoices.") for i in range(10)]
    class DistinctDiscovery(Discovery):
        async def search(self, query, provider):
            self.queries.append(query)
            return self.sources[:5] if len(self.queries) == 1 else self.sources[5:]
    item, http = opportunity(), HTTP()
    await Researcher(DistinctDiscovery(sources), Extractor(), http=http, jev_key="test").research([item])
    assert len(item.solutions) == len(http.calls) == 6
    legacy = opportunity()
    await Researcher(Discovery(sources[:1]), Extractor()).research([legacy])
    assert legacy.solutions[0]["relevance"] == "unverified"
    assert legacy.solutions[0]["verification_method"] == "none"
