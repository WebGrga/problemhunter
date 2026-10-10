import json
import httpx
import pytest

from problem_hunter.cli import main
from problem_hunter.discovery import Discovery
from problem_hunter.http import HTTP
from problem_hunter.intelligence import Evaluator, FIELDS
from problem_hunter.models import Source
from problem_hunter.pipeline import Pipeline
from problem_hunter.storage import Store
from problem_hunter.rubric import load_rubric


@pytest.mark.asyncio
async def test_shared_pipeline_repeats_and_preserves_bookmarks_and_research(tmp_path):
    with Store(tmp_path / 'store.db') as store:
        evaluator = Evaluator(None, offline=True)
        pipeline = Pipeline(store, evaluator)
        source = Source('https://example.com/one', 'Scheduling', 'I waste hours managing appointments manually.', author='alice')
        result = await pipeline.process([source])
        assert len(result) == 1
        old_id = result[0].id
        store.bookmark(old_id)
        result[0].solutions = [{'name': 'Existing tool', 'url': 'https://example.com/tool'}]
        result[0].research_status = 'researched'
        store.save_opportunities(result)
        result = await pipeline.process([source])
        assert result[0].bookmarked
        assert result[0].solutions[0]['name'] == 'Existing tool'
        assert len(store.load_problems()) == 1
        second = Source('https://example.com/two', 'Scheduling', 'We waste hours managing bookings manually.', author='bob')
        result = await pipeline.process([second])
        assert len(result) == 1
        assert result[0].id == old_id
        assert result[0].bookmarked
        assert result[0].independent_complainants == 2


@pytest.mark.asyncio
async def test_mocked_brave_to_jev_to_sqlite_contract(tmp_path):
    calls = []
    def handler(request):
        calls.append(request.url.host)
        if request.url.host == 'api.search.brave.com':
            assert request.headers['X-Subscription-Token'] == 'fixture'
            return httpx.Response(200, json={'web': {'results': [{'url': 'https://example.com/complaint', 'title': 'Appointments',
                'description': 'I waste hours managing appointments manually.'}]}})
        assert request.headers['Authorization'] == 'Bearer fixture'
        payload = json.loads(request.content)
        assert payload['model'] == 'jev-latest'
        answers = {f'0_{field}': {'type': 'noul', 'noul': 1 if field != 'willingness_to_pay' else 0} for field in FIELDS}
        answers['0_severity'] = {'type': 'score', 'score': 3, 'confidence': .9}
        answers['0_category'] = {'type': 'choice', 'choice': 'services', 'confidence': .9}
        return httpx.Response(200, json={'model': 'jev-1.13.0', 'answers': answers, 'usage': {'input_tokens': 100, 'output_tokens': 20}})
    with Store(tmp_path / 'store.db') as store:
        async with HTTP(store, rate=0, transport=httpx.MockTransport(handler)) as client:
            discovery = Discovery(client, 'fixture')
            sources = await discovery.search('restaurants manual')
            pipeline = Pipeline(store, Evaluator(client, 'fixture'))
            result = await pipeline.process(sources)
            assert len(result) == 1
            assert result[0].evidence_strength == 'weak'
            await pipeline.process(sources)
            assert calls == ['api.search.brave.com', 'api.typesafe.ai']
            assert store.load_sources()[0].url == 'https://example.com/complaint'


def test_cli_csv_export_and_repeat(tmp_path, capsys):
    csv = tmp_path / 'input.csv'
    csv.write_text('link,text,username\nhttps://example.com/a,I waste hours managing appointments manually.,alice\n')
    options = ['--offline', '--audit-yield', '--db', str(tmp_path / 'store.db'), '--output', str(tmp_path / 'report')]
    assert main(['import-csv', str(csv), *options]) == 0
    assert main(['import-csv', str(csv), *options]) == 0
    report = json.loads((tmp_path / 'report.json').read_text())
    assert len(report['opportunities']) == 1
    assert len(report['sources']) == 1
    assert report['opportunities'][0]['evidence_strength'] == 'weak'
    assert report['problems'][0]['evidence']['mode'] == 'offline_heuristic'
    audit = json.loads((tmp_path / 'report.yield.json').read_text())
    assert audit['collection']['imported_content'] == 1
    assert audit['pipeline']['funnel']['qualifying_problems'] == 1
    assert audit['pipeline']['costs']['total_cost_usd'] == 0
    assert main(['usage', '--db', str(tmp_path / 'store.db')]) == 0
    assert 'ranked opportunities' in capsys.readouterr().out


def test_cli_missing_credentials_and_invalid_mapping(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('TYPESAFE_API_KEY', raising=False)
    csv = tmp_path / 'input.csv'
    csv.write_text('text\nProblem\n')
    assert main(['import-csv', str(csv), '--db', str(tmp_path / 'store.db')]) == 1
    assert 'TYPESAFE_API_KEY' in capsys.readouterr().err
    assert main(['import-csv', str(csv), '--offline', '--map', 'broken', '--db', str(tmp_path / 'store.db')]) == 1
    assert '--map' in capsys.readouterr().err


def test_dotenv_loads_without_overriding_shell(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / '.env').write_text('TYPESAFE_API_KEY=fixture-file-key\nBRAVE_SEARCH_API_KEY=fixture-brave-key\n')
    monkeypatch.setenv('TYPESAFE_API_KEY', 'fixture-shell-key')
    monkeypatch.delenv('BRAVE_SEARCH_API_KEY', raising=False)
    assert main(['usage', '--db', str(tmp_path / 'store.db')]) == 0
    import os
    assert os.environ['TYPESAFE_API_KEY'] == 'fixture-shell-key'
    assert os.environ['BRAVE_SEARCH_API_KEY'] == 'fixture-brave-key'


@pytest.mark.asyncio
async def test_updated_content_is_reevaluated_and_rejected_problem_removed(tmp_path):
    with Store(tmp_path / 'store.db') as store:
        pipeline = Pipeline(store, Evaluator(None, offline=True))
        await pipeline.process([Source('https://example.com/a', 'p', 'I waste hours manually managing appointments.')])
        assert len(store.load_problems()) == 1
        result = await pipeline.process([Source('https://example.com/a', 'p', 'Everything is working well.')])
        assert result == []
        assert store.load_problems() == []
        assert len(store.load_sources()) == 1


@pytest.mark.asyncio
async def test_changed_question_file_fingerprint_triggers_reevaluation(tmp_path):
    class CountingEvaluator(Evaluator):
        evaluated = 0
        async def evaluate(self, sources):
            self.evaluated += len(sources)
            return await super().evaluate(sources)
    source = Source('https://example.com/a', 'p', 'I waste hours manually managing appointments.')
    with Store(tmp_path / 'store.db') as store:
        first = CountingEvaluator(None, offline=True)
        pipeline = Pipeline(store, first)
        await pipeline.process([source])
        await pipeline.process([source])
        assert first.evaluated == 1
        rubric = load_rubric('production')
        rubric['questions']['genuine']['instructions'] += ' A revised question.'
        changed = CountingEvaluator(None, offline=True, rubric=rubric)
        await Pipeline(store, changed).process([source])
        assert changed.evaluated == 1
        assert store.load_problems()[0].evidence['evaluation_rubric_sha256'] == changed.rubric_fingerprint
