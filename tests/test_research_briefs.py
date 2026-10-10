import json
from dataclasses import asdict

import httpx
import pytest

from problem_hunter import cli
from problem_hunter.models import Opportunity, Source
from problem_hunter.research import Researcher, validate_brief, research_queries
from problem_hunter.storage import Store
from problem_hunter.http import HTTP
from problem_hunter.pipeline import Pipeline
from problem_hunter.intelligence import Evaluator


def brief(task='restaurant staff scheduling', constraint='changing availability'):
    return {'affected_person': 'affected staff', 'task': task,
            'desired_outcome': 'complete the task with less effort', 'unmet_constraint': constraint}


@pytest.mark.parametrize('value', [None, [], {}, brief(task=' '), brief(task='word ' * 13),
    {**brief(), 'remedy_types': []}, {**brief(), 'remedy_types': ['invented']},
    {**brief(), 'unmet_constraint': 'x' * 301}])
def test_invalid_brief_fails_before_research(value):
    with pytest.raises(ValueError):
        validate_brief(value)


@pytest.mark.asyncio
@pytest.mark.parametrize('task,constraint', [
    ('restaurant staff scheduling', 'changing availability'),
    ('shorter workplace standups', 'preserve coordination'),
    ('video call privacy in small homes', 'limited space and sound leakage'),
])
async def test_reviewed_brief_unlocks_general_research_and_broad_remedies(task, constraint):
    item = Opportunity('a', 'Long complaint ' * 100, 'An experienced burden', 'other',
        investigation_priority=80, research_brief=brief(task, constraint))
    class Discovery:
        queries = []
        async def search(self, query, provider):
            self.queries.append(query)
            return [Source(f'https://example.org/{len(self.queries)}', 'Article title', 'An unverified approach.')]
    class Extractor:
        async def enrich(self, source):
            return source
    discovery = Discovery()
    await Researcher(discovery, Extractor()).research([item])
    assert len(discovery.queries) == 5
    assert any('physical products' in q for q in discovery.queries)
    assert any('process changes' in q for q in discovery.queries)
    assert all(q.startswith(task) and 'Long complaint' not in q for q in discovery.queries)
    assert item.research_status == 'researched'
    assert all(s['relevance'] == 'unverified' for s in item.solutions)
    assert item.independent_complainants == 0 and item.score == 0


def test_stored_cli_plan_needs_no_credentials_and_retains_other_groups(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for key in ('TYPESAFE_API_KEY', 'BRAVE_SEARCH_API_KEY'):
        monkeypatch.delenv(key, raising=False)
    db = tmp_path / 'test.db'
    with Store(db) as store:
        store.save_opportunities([Opportunity('a', 'A', 'A', 'other', solutions=[{'name': 'stale'}], solution_landscape={'stale': True}),
                                  Opportunity('b', 'B', 'B', 'other')])
        store.bookmark('a')
    path = tmp_path / 'brief.json'
    path.write_text(json.dumps(brief()))
    output = tmp_path / 'report'
    assert cli.main(['research', 'a', '--brief', str(path), '--plan-only', '--db', str(db), '--output', str(output)]) == 0
    with Store(db) as store:
        groups = {item.id: item for item in store.load_opportunities()}
        assert set(groups) == {'a', 'b'} and groups['a'].bookmarked
        assert groups['a'].solutions == [] and groups['a'].research_status == 'brief_ready'
        assert groups['a'].solution_landscape == {}
        assert store.usage_summary()['requests'] == 0
    assert 'changing availability' in output.with_suffix('.md').read_text()
    assert len(json.loads(output.with_suffix('.json').read_text())['opportunities']) == 1


def test_stored_research_calls_only_search_and_preserves_evidence(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('BRAVE_SEARCH_API_KEY', 'fixture')
    monkeypatch.delenv('TYPESAFE_API_KEY', raising=False)
    calls = []
    def handler(request):
        calls.append(request.url.host)
        assert request.url.host == 'api.search.brave.com'
        return httpx.Response(200, json={'web': {'results': []}})
    monkeypatch.setattr(cli, 'HTTP', lambda store, **kwargs: HTTP(store, **kwargs, transport=httpx.MockTransport(handler)))
    db = tmp_path / 'test.db'
    with Store(db) as store:
        source = Source('https://example.org/a', 'Scheduling', 'I waste hours managing appointments manually.', author='alice')
        import asyncio
        groups = asyncio.run(Pipeline(store, Evaluator(None, offline=True)).process([source]))
        group = groups[0]
        group.research_brief = validate_brief(brief())
        store.save_opportunities([group])
        before = ([asdict(s) for s in store.load_sources()], [asdict(p) for p in store.load_problems()])
    assert cli.main(['research', group.id, '--db', str(db), '--output', str(tmp_path / 'r'), '--rate', '0']) == 0
    assert len(calls) == 5
    with Store(db) as store:
        assert before == ([asdict(s) for s in store.load_sources()], [asdict(p) for p in store.load_problems()])
        assert store.load_opportunities()[0].score == group.score
        assert store.usage_summary()['phases']['research']['network_requests'] == 5


@pytest.mark.asyncio
async def test_pipeline_keeps_explicit_brief_on_repeat(tmp_path):
    with Store(tmp_path / 'test.db') as store:
        source = Source('https://example.org/a', 'Appointments', 'I waste hours managing appointments manually.', author='alice')
        pipeline = Pipeline(store, Evaluator(None, offline=True))
        group = (await pipeline.process([source]))[0]
        group.research_brief = validate_brief(brief('managing appointments'))
        group.solution_landscape = {'version': 'fixture'}
        store.save_opportunities([group])
        repeated = (await pipeline.process([source]))[0]
        assert repeated.research_brief == group.research_brief
        assert repeated.solution_landscape == group.solution_landscape
        assert research_queries(repeated)[0].startswith('managing appointments')
        changed = (await pipeline.process([Source('https://example.org/b', 'Scheduling',
            'We waste hours managing bookings manually.', author='bob')]))[0]
        assert changed.solution_landscape == {} and changed.research_status == 'brief_needs_review'
