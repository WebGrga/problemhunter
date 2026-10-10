import json

import httpx
import pytest

from problem_hunter.http import HTTP
from problem_hunter.models import Opportunity, Source
from problem_hunter.research import Researcher, validate_brief
from problem_hunter.landscape import build_questions
from problem_hunter.reports import export_report
from problem_hunter.storage import Store


class Discovery:
    def __init__(self, sources):
        self.sources = sources

    async def search(self, query, provider):
        return self.sources


class Extractor:
    async def enrich(self, source):
        return source


def opportunity(task='restaurant staff scheduling', constraint='changing availability'):
    return Opportunity('a', 'Complaint title', 'Experienced burden', 'other',
        research_brief=validate_brief({'affected_person': 'Affected person', 'task': task,
        'desired_outcome': 'Complete the task', 'unmet_constraint': constraint,
        'remedy_types': ['software']}))


def handler_for(specs, mutate=None):
    def handler(request):
        payload = json.loads(request.content)
        spec = specs[payload['state']['source']['url']]
        questions = payload['questions']
        selected = {'name': spec['name'], 'kind': spec.get('kind', 'software'),
            'role': spec.get('role', 'provider'), 'fit': spec.get('fit', 'yes'),
            'constraint_status': spec.get('constraint_status', 'unknown'),
            'adoption_type': spec.get('adoption_type', 'unknown')}
        for field in ('name', 'function', 'pricing', 'limits', 'setup', 'complaint', 'adoption', 'constraint'):
            literal = spec.get(field)
            selected[field] = next((key for key, quote in questions[field]['criteria'].items()
                                    if quote == literal), 'none')
        answers = {field: {'type': 'choice', 'choice': choice, 'confidence': 1,
            'probabilities': {key: float(key == choice) for key in questions[field]['criteria']}}
            for field, choice in selected.items()}
        response = {'model': 'jev-fixture', 'answers': answers, 'usage': {'input_tokens': 100, 'output_tokens': 20}}
        if mutate:
            mutate(response)
        return httpx.Response(200, json=response)
    return handler


async def run_research(tmp_path, item, sources, specs, mutate=None, key='fixture'):
    with Store(tmp_path / 'test.db') as store:
        async with HTTP(store, rate=0, transport=httpx.MockTransport(handler_for(specs, mutate))) as http:
            http.phase = 'research'
            await Researcher(Discovery(sources), Extractor(), http=http, jev_key=key).research([item])
        store.save_opportunities([item])
        assert store.load_opportunities()[0].solution_landscape == item.solution_landscape
        return store.usage_summary()


@pytest.mark.asyncio
async def test_consolidates_provider_pricing_and_customer_evidence_with_provenance(tmp_path):
    function = 'ShiftMate schedules restaurant staff based on changing availability.'
    price = 'ShiftMate Pro costs $20 per location per month in 2026.'
    setup = 'ShiftMate setup requires staff to enter their availability.'
    adoption = 'ShiftMate claims 10000 customers in 2026.'
    complaint = 'I use ShiftMate Pro and cannot export staff availability.'
    reviews = 'ShiftMate has 123 reviews as of October 2026.'
    sources = [
        Source('https://shift.example/features', 'Meet your new scheduling helper', function + ' ' + adoption),
        Source('https://shift.example/pricing', 'Plans for teams', price + ' ' + setup),
        Source('https://reviews.example/shift', 'Scheduling reviews', complaint + ' ' + reviews, author='alice'),
    ]
    specs = {
        sources[0].url: {'name': 'ShiftMate', 'function': function, 'constraint': function,
                        'constraint_status': 'satisfied', 'adoption': adoption, 'adoption_type': 'provider_claimed_usage'},
        sources[1].url: {'name': 'ShiftMate', 'pricing': price, 'setup': setup, 'fit': 'unknown'},
        sources[2].url: {'name': 'ShiftMate', 'role': 'customer', 'complaint': complaint,
                        'adoption': reviews, 'adoption_type': 'review_count', 'fit': 'unknown'},
    }
    item = opportunity()
    usage = await run_research(tmp_path, item, sources, specs)
    landscape = item.solution_landscape
    assert len(landscape['offerings']) == 1
    offering = landscape['offerings'][0]
    assert offering['name'] == 'ShiftMate' and len(offering['citations']) == 3
    assert offering['claims']['pricing'][0]['quote'] == price
    assert offering['claims']['complaint'][0]['author'] == 'alice'
    assert {claim['type'] for claim in offering['claims']['adoption']} == {'provider_claimed_usage', 'review_count'}
    assert all(c['retrieved_at'] for c in offering['citations'])
    assert landscape['disposition']['status'] == 'apparently_well_served'
    assert landscape['disposition']['evidence'][0]['quote'] == function
    assert usage['phases']['research']['network_requests'] == 3
    assert usage['providers']['jev']['network_requests'] == 3
    path = tmp_path / 'comparison.md'
    export_report([item], [], path)
    text = path.read_text()
    assert '| ShiftMate | software | source_supported | satisfied |' in text
    assert 'review_count (not established active users or market share)' in text
    assert price in text and 'retrieved ' in text and 'Plans for teams' in text


@pytest.mark.asyncio
@pytest.mark.parametrize('name,task,constraint,kind,function,limitation,expected', [
    ('Timebox', 'shorter workplace standups', 'preserve coordination', 'process',
     'Timebox limits workplace standups to ten minutes.',
     'Timebox cannot preserve coordination when blockers require discussion.', 'plausible_residual_gap'),
    ('QuietScreen', 'video call privacy in small homes', 'sound leakage', 'physical',
     'QuietScreen is a physical screen for video call privacy in small homes.',
     'QuietScreen provides visual privacy but cannot prevent sound leakage.', 'plausible_residual_gap'),
])
async def test_nonsoftware_remedies_and_constraint_backed_residual_gap(tmp_path, name, task, constraint, kind, function, limitation, expected):
    item = opportunity(task, constraint)
    source = Source('https://example.org/remedy', 'How to solve the problem', function + ' ' + limitation)
    specs = {source.url: {'name': name, 'kind': kind, 'role': 'guide' if kind == 'process' else 'provider',
        'function': function, 'limits': limitation, 'constraint': limitation, 'constraint_status': 'blocked'}}
    await run_research(tmp_path, item, [source], specs)
    disposition = item.solution_landscape['disposition']
    assert disposition['status'] == expected
    assert 'unsearched alternatives' in disposition['constraint_note']
    assert 'trial required' in disposition['non_build_option']
    assert any(claim['quote'] == limitation for claim in disposition['evidence'])
    assert item.score == 0 and item.independent_complainants == 0 and item.potential_fixes == []


@pytest.mark.asyncio
async def test_unrelated_quotes_do_not_establish_pricing_adoption_or_gap(tmp_path):
    function = 'ShiftMate schedules restaurant staff.'
    text = function + ' OtherTool costs $10 monthly. OtherTool cannot handle changing availability. OtherTool has 200 reviews.'
    source = Source('https://example.org/a', 'Do not use this title as a name', text)
    specs = {source.url: {'name': 'ShiftMate', 'function': function, 'pricing': 'OtherTool costs $10 monthly.',
        'constraint': 'OtherTool cannot handle changing availability.', 'constraint_status': 'blocked',
        'adoption': 'OtherTool has 200 reviews.', 'adoption_type': 'review_count'}}
    item = opportunity()
    await run_research(tmp_path, item, [source], specs)
    result = item.solution_landscape
    assert result['disposition']['status'] == 'insufficient_information'
    assert result['offerings'][0]['claims']['pricing'] == []
    assert result['offerings'][0]['claims']['adoption'] == []


@pytest.mark.asyncio
@pytest.mark.parametrize('mutate', [
    lambda r: r['answers'].pop('name'),
    lambda r: r['answers']['name'].update(choice='invented'),
    lambda r: r['answers']['fit'].pop('probabilities'),
    lambda r: r.update(usage={}),
])
async def test_malformed_model_response_cannot_partially_promote_remedy(tmp_path, mutate):
    source = Source('https://example.org/a', 'A title', 'ShiftMate schedules restaurant staff.')
    item = opportunity()
    await run_research(tmp_path, item, [source], {source.url: {'name': 'ShiftMate', 'function': source.content}}, mutate)
    assert item.research_status == 'partial'
    assert item.solutions[0]['verification_detail']['status'] == 'failed'
    assert item.solution_landscape['offerings'] == []
    assert item.solution_landscape['disposition']['status'] == 'insufficient_information'


@pytest.mark.asyncio
@pytest.mark.parametrize('kind,key', [('search_snippet', 'fixture'), ('full_text', '')])
async def test_snippets_or_no_model_key_leave_named_offerings_unknown(tmp_path, kind, key):
    item = opportunity()
    source = Source('https://example.org/a', 'ShiftMate article title', 'ShiftMate schedules restaurant staff.', content_kind=kind)
    await run_research(tmp_path, item, [source], {}, key=key)
    assert item.solution_landscape['offerings'] == []
    assert item.solutions[0]['status'] == 'candidate'


@pytest.mark.asyncio
async def test_provider_collision_and_conflicting_constraint_claims_are_visible(tmp_path):
    function = 'ShiftMate schedules restaurant staff.'
    satisfied = 'ShiftMate accommodates changing availability.'
    blocked = 'ShiftMate cannot accommodate changing availability for night shifts.'
    sources = [Source('https://first.example/a', 'First', function + ' ' + satisfied),
               Source('https://first.example/b', 'First limits', function + ' ' + blocked),
               Source('https://second.example/a', 'Second', function),
               Source('https://review.example/a', 'Ambiguous review', function, author='alice')]
    specs = {s.url: {'name': 'ShiftMate', 'function': function} for s in sources}
    specs[sources[0].url].update(constraint=satisfied, constraint_status='satisfied')
    specs[sources[1].url].update(constraint=blocked, constraint_status='blocked')
    specs[sources[3].url].update(role='customer')
    item = opportunity()
    await run_research(tmp_path, item, sources, specs)
    result = item.solution_landscape
    assert len(result['offerings']) == 3
    assert result['offerings'][0]['constraint_status'] == 'conflicting'
    assert result['disposition']['status'] == 'insufficient_information'


@pytest.mark.asyncio
async def test_review_counts_cannot_be_promoted_to_provider_users(tmp_path):
    function = 'ShiftMate schedules restaurant staff.'
    adoption = 'ShiftMate has 200 reviews in 2026.'
    source = Source('https://example.org/a', 'Review counts', function + ' ' + adoption)
    item = opportunity()
    await run_research(tmp_path, item, [source], {source.url: {'name': 'ShiftMate', 'function': function,
        'adoption': adoption, 'adoption_type': 'provider_claimed_usage'}})
    assert item.solution_landscape['offerings'][0]['claims']['adoption'] == []


def test_name_candidates_cover_lowercase_practices_and_numeric_brands_bounded():
    content = '7shifts schedules restaurant staff. The "two question check-in" reduces standup time.'
    questions, names, excerpts = build_questions(content + ' ' + 'MoreNames ' * 10000, opportunity().research_brief)
    assert '7shifts' in names.values() and 'two question check-in' in names.values()
    assert len(names) <= 64 and len(excerpts) <= 48
    assert all(name in content + ' ' + 'MoreNames ' * 10000 for name in names.values())
    assert 'none' in questions['name']['criteria']


@pytest.mark.asyncio
async def test_unknown_authorship_and_provider_promises_do_not_become_customer_experiences(tmp_path):
    function = 'ShiftMate schedules restaurant staff.'
    promise = 'We at ShiftMate solve your frustrating availability problems.'
    item = opportunity()
    source = Source('https://example.org/a', 'Provider', function + ' ' + promise)
    await run_research(tmp_path, item, [source], {source.url: {'name': 'ShiftMate', 'function': function,
        'complaint': promise, 'role': 'unknown'}})
    offering = item.solution_landscape['offerings'][0]
    assert offering['task_fit'] == 'unknown' and offering['claims']['complaint'] == []
    assert item.solution_landscape['disposition']['status'] == 'insufficient_information'
