import json

import httpx
import pytest

from problem_hunter.models import Source, Opportunity
from problem_hunter.http import HTTP
from problem_hunter.pipeline import Pipeline
from problem_hunter.reports import export_report, _rank_key
from problem_hunter.rubric import load_rubric
from problem_hunter.storage import Store
from problem_hunter.universal import UniversalEvaluator, build_request, parse_choice


def response(questions, *, problem='p0', workaround='none', payment='none', signal='unknown', kind='experienced_burden', category='business_operations'):
    defaults = {'first_hand': 1, 'relevance': 'yes', 'evidence_kind': kind, 'pain': 3,
        'workaround_burden': 2, 'replacement_motivation': 2, 'need_status': 'ongoing',
        'category': category, 'payment_signal': signal, 'problem_excerpt': problem,
        'workaround_excerpt': workaround, 'payment_excerpt': payment}
    answers = {}
    for name, q in questions.items():
        value = defaults[name]
        answers[name] = {'type': q['type'], q['type']: value}
        if q['type'] == 'choice':
            answers[name].update(confidence=1, probabilities={key: float(key == value) for key in q['criteria']})
        elif q['type'] == 'score':
            answers[name]['confidence'] = 1
    return {'model': 'jev-fixture', 'answers': answers, 'usage': {'input_tokens': 100, 'output_tokens': 30}}


@pytest.mark.asyncio
@pytest.mark.parametrize('scope,body,category', [
    ('restaurants', 'We lose bookings because our tables get double booked.', 'hospitality'),
    ('large organizations', 'We repeatedly re-enter supplier approvals in three systems.', 'business_operations'),
    ('meeting friends', 'I feel isolated because I cannot find local people who share my interests.', 'social_relationships'),
])
async def test_general_pipeline_supports_business_and_personal_pain_without_payment(tmp_path, scope, body, category):
    requests = []
    def handler(request):
        payload = json.loads(request.content)
        requests.append(payload)
        assert payload['state']['research_scope'] == scope
        assert 'invoice' not in payload['questions']['relevance']['instructions'].lower()
        return httpx.Response(200, json=response(payload['questions'], category=category))
    with Store(tmp_path / 'store.db') as store:
        async with HTTP(store, rate=0, transport=httpx.MockTransport(handler)) as http:
            evaluator = UniversalEvaluator(http, 'fixture', scope=scope)
            pipeline = Pipeline(store, evaluator)
            source = Source('https://example.org/a', 'Specific experienced failure', body, author='alice')
            groups = await pipeline.process([source])
            await pipeline.process([source])
            assert len(requests) == 1
            assert len(groups) == 1 and groups[0].category == category
            assert groups[0].score_breakdown['pain_severity']['points'] == 18.75
            assert groups[0].score_breakdown['willingness_to_pay']['status'] == 'unknown'
            assert groups[0].independent_complainants == 1
            assert groups[0].priority_breakdown['problem_family'] is None
            problem = store.load_problems()[0]
            assert problem.evidence['impact'] == body
            assert problem.evidence['loss'] is None
            assert problem.statement.startswith(source.title)


@pytest.mark.asyncio
async def test_payment_flag_does_not_bury_pain_and_snippets_do_not_identify_users(tmp_path):
    def handler(request):
        q = json.loads(request.content)['questions']
        return httpx.Response(200, json=response(q, signal='paid_solution'))
    with Store(tmp_path / 'store.db') as store:
        async with HTTP(store, rate=0, transport=httpx.MockTransport(handler)) as http:
            evaluator = UniversalEvaluator(http, 'fixture')
            groups = await Pipeline(store, evaluator).process([Source('https://example.org/a', 'Context',
                'I am frustrated by repeatedly being excluded from local activities.', author='thread-owner', content_kind='snippet')])
            assert groups[0].independent_complainants == 0
            assert groups[0].review_required
            problem = store.load_problems()[0]
            assert problem.judgments['triage']['payment_signal'] == 'unknown'
            assert problem.judgments['triage']['payment_review_reasons']
            assert problem.evidence['first_hand'] is None


@pytest.mark.asyncio
async def test_model_selected_payment_is_visible_but_not_verified_spending(tmp_path):
    body = 'I cannot find an accessible local activity. I would pay for an accessible social event.'
    def handler(request):
        return httpx.Response(200, json=response(json.loads(request.content)['questions'], payment='p1', signal='explicit_intent'))
    with Store(tmp_path / 'store.db') as store:
        async with HTTP(store, rate=0, transport=httpx.MockTransport(handler)) as http:
            groups = await Pipeline(store, UniversalEvaluator(http, 'fixture')).process([Source('https://example.org/a', 'Accessible activities', body, author='alice')])
            assert groups[0].score_breakdown['willingness_to_pay']['points'] == 0
            path = tmp_path / 'report.md'
            export_report(groups, store.load_sources(), path, problems=store.load_problems())
            assert 'I would pay for an accessible social event.' in path.read_text()
            assert 'not verified spending' in path.read_text()


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['promotion_or_general', 'satisfied_low_burden'])
async def test_resumes_and_ordinary_activity_are_not_retained(tmp_path, kind):
    def handler(request):
        return httpx.Response(200, json=response(json.loads(request.content)['questions'], problem='none', kind=kind))
    with Store(tmp_path / 'store.db') as store:
        async with HTTP(store, rate=0, transport=httpx.MockTransport(handler)) as http:
            groups = await Pipeline(store, UniversalEvaluator(http, 'fixture')).process([Source('https://example.org/a', 'Resume', 'Looking for a job. I built a scheduling app.')])
            assert groups == []


@pytest.mark.asyncio
async def test_malformed_selection_fails_without_marking_source_evaluated(tmp_path):
    def handler(request):
        q = json.loads(request.content)['questions']
        return httpx.Response(200, json=response(q, problem='invented'))
    with Store(tmp_path / 'store.db') as store:
        async with HTTP(store, rate=0, transport=httpx.MockTransport(handler)) as http:
            with pytest.raises(ValueError):
                await Pipeline(store, UniversalEvaluator(http, 'fixture')).process([Source('https://example.org/a', 'Failure', 'I struggle with scheduling.')])
            assert 'evaluation_signature' not in store.load_sources()[0].metadata


def test_passages_are_bounded_and_exact_and_scope_changes_fingerprint():
    source = Source('https://example.org/a', 'Long', 'I struggle. ' * 10000)
    state, questions, truncated = build_request(source, 'anything', load_rubric('general-v4'))
    assert truncated and len(state['passages']) <= 48
    assert all(quote in source.content for quote in state['passages'].values())
    assert len(questions['problem_excerpt']['criteria']) <= 49
    assert UniversalEvaluator(None, 'fixture', scope='restaurants').rubric_fingerprint != UniversalEvaluator(None, 'fixture', scope='friendship').rubric_fingerprint


@pytest.mark.asyncio
async def test_scope_change_evaluates_current_inputs_not_prior_corpus(tmp_path):
    calls = []
    def handler(request):
        payload = json.loads(request.content)
        calls.append((payload['state']['research_scope'], payload['state']['title']))
        category = 'hospitality' if payload['state']['research_scope'] == 'restaurants' else 'social_relationships'
        return httpx.Response(200, json=response(payload['questions'], category=category))
    with Store(tmp_path / 'store.db') as store:
        async with HTTP(store, rate=0, transport=httpx.MockTransport(handler)) as http:
            await Pipeline(store, UniversalEvaluator(http, 'fixture', scope='restaurants')).process([
                Source('https://example.org/a', 'Booking failure', 'We repeatedly double book tables.', author='alice')])
            await Pipeline(store, UniversalEvaluator(http, 'fixture', scope='friendship')).process([
                Source('https://example.org/b', 'Social isolation', 'I cannot meet people with my interests.', author='bob')])
            assert calls == [('restaurants', 'Booking failure'), ('friendship', 'Social isolation')]
            assert len(store.load_problems()) == 2
            assert {p.judgments['triage']['research_scope'] for p in store.load_problems()} == {'restaurants', 'friendship'}


def test_review_flags_do_not_bury_severe_general_candidates():
    high = Opportunity('high', 'Severe', 'Severe', 'other', investigation_priority=90,
        review_required=True, priority_breakdown={'ranking_policy': 'priority_before_review_flag'})
    low = Opportunity('low', 'Minor', 'Minor', 'other', investigation_priority=10,
        priority_breakdown={'ranking_policy': 'priority_before_review_flag'})
    assert sorted([low, high], key=_rank_key)[0] == high


def test_tiny_choice_distribution_disagreement_is_flagged_not_rewritten():
    answer = {'type': 'choice', 'choice': 'p0', 'confidence': .03,
              'probabilities': {'none': .31, 'p0': .34, 'p1': .35}}
    assert parse_choice(answer, {'none': 'none', 'p0': 'first', 'p1': 'second'}) == ('p0', True)
    answer['probabilities'] = {'none': .2, 'p0': .2, 'p1': .6}
    with pytest.raises(ValueError):
        parse_choice(answer, {'none': 'none', 'p0': 'first', 'p1': 'second'})


def test_cli_general_csv_scope_uses_universal_evaluator(tmp_path, monkeypatch):
    import problem_hunter.cli as cli
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('TYPESAFE_API_KEY', 'fixture')
    monkeypatch.delenv('LLM_ENDPOINT', raising=False)
    calls = []
    def handler(request):
        payload = json.loads(request.content)
        calls.append(payload['state']['research_scope'])
        return httpx.Response(200, json=response(payload['questions'], category='social_relationships'))
    monkeypatch.setattr(cli, 'HTTP', lambda store, **kwargs: HTTP(store, **kwargs, transport=httpx.MockTransport(handler)))
    path = tmp_path / 'input.csv'
    path.write_text('url,title,content,author\nhttps://example.org/a,Social participation,I cannot find accessible local events.,alice\n')
    assert cli.main(['import-csv', str(path), '--scope', 'accessible social participation',
        '--evaluation-rubric', 'general-v4', '--audit-yield', '--db', str(tmp_path / 'store.db'),
        '--output', str(tmp_path / 'report')]) == 0
    assert calls == ['accessible social participation']
    report = json.loads((tmp_path / 'report.json').read_text())
    assert report['opportunities'][0]['category'] == 'social_relationships'


@pytest.mark.asyncio
async def test_invoice_comparator_refuses_universal_before_requests():
    from problem_hunter.benchmark import compare
    with pytest.raises(ValueError, match='invoice comparator'):
        await compare([], None, 'fixture', rubric=load_rubric('general-v4'))
