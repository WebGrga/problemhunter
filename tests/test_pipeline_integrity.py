import sqlite3

import pytest

from problem_hunter.grouping import group_problems
from problem_hunter.intelligence import Evaluator
from problem_hunter.models import Opportunity, Problem, Source
from problem_hunter.pipeline import Pipeline
from problem_hunter.reports import export_report
from problem_hunter.research import workflow
from problem_hunter.scoring import score_opportunity
from problem_hunter.storage import Store


def test_experimental_groups_distinguish_families_and_count_authors():
    sources = [Source(f'https://example.org/{i}', 'Invoice', f'Unique account {i}', author=author, id=str(i))
               for i, author in enumerate(['alice', 'alice', 'bob', 'carol'])]
    families = ['payment_collection', 'payment_collection', 'payment_collection', 'invoice_generation']
    problems = [Problem(s.id, f'Complaint {s.id}', 'finance', id=s.id,
        judgments={'first_hand': 1, 'triage': {'problem_family': family, 'score': score, 'route': 'primary'}},
        evidence={'first_hand': s.content}) for s, family, score in zip(sources, families, [100, 0, 80, 30])]
    groups = group_problems(problems, sources)
    assert len(groups) == 2
    first = score_opportunity(groups[0], problems, sources)
    assert first.independent_sources == 3
    assert first.independent_complainants == 2
    assert first.investigation_priority == 65  # Alice mean 50, Bob 80
    assert workflow(first) == 'invoice payment collection'


@pytest.mark.asyncio
async def test_title_and_provenance_upgrade_invalidate_evaluation(tmp_path):
    class CountingEvaluator(Evaluator):
        count = 0
        async def evaluate(self, sources):
            self.count += len(sources)
            return await super().evaluate(sources)
    with Store(tmp_path / 'store.db') as store:
        evaluator = CountingEvaluator(None, offline=True)
        pipeline = Pipeline(store, evaluator)
        body = 'I waste hours manually managing appointments.'
        await pipeline.process([Source('https://example.org/a', 'Old', body, content_kind='snippet')])
        await pipeline.process([Source('https://example.org/a', 'Old', body, content_kind='full_text')])
        assert evaluator.count == 2
        await pipeline.process([Source('https://example.org/a', 'New', body, content_kind='full_text')])
        assert evaluator.count == 3
        await pipeline.process([Source('https://example.org/a', 'New', body, content_kind='full_text')])
        assert evaluator.count == 3


@pytest.mark.asyncio
async def test_outdated_original_post_never_reaches_evaluator(tmp_path):
    class Evaluator:
        offline, model = False, 'fixture'
        async def evaluate(self, sources):
            assert sources == []
            return []
    source = Source('https://example.com/post', 'Recently indexed', 'Old complaint',
        metadata={'original_published_at': '2014-01-01', 'requested_since': '2025-01-01'})
    with Store(tmp_path / 'store.db') as store:
        assert await Pipeline(store, Evaluator()).process([source]) == []
        assert store.load_sources() == []


def test_old_request_logs_migrate_without_loss(tmp_path):
    path = tmp_path / 'old.db'
    with sqlite3.connect(path) as connection:
        connection.execute('CREATE TABLE request_logs (id INTEGER PRIMARY KEY, created_at REAL NOT NULL, provider TEXT NOT NULL, url TEXT NOT NULL, status INTEGER, usage TEXT, cost REAL, cached INTEGER NOT NULL)')
        connection.execute("INSERT INTO request_logs VALUES(1,0,'brave','https://example.org',200,NULL,0.005,0)")
    with Store(path) as store:
        assert store.connection.execute('SELECT phase,cost FROM request_logs').fetchone() == ('unknown', .005)
        store.log_request('jev', 'https://example.org', 200, cost=.001, phase='research')
        assert store.usage_summary()['phases']['research']['estimated_cost'] == .001


def test_markdown_solution_summary_omits_raw_payload(tmp_path):
    opportunity = Opportunity('one', 'Invoice entry', 'Manual invoice entry', 'finance', solutions=[{
        'name': 'Tool', 'url': 'https://example.org/tool', 'status': 'candidate', 'relevance': 'unverified',
        'content': 'RAW_FULL_CONTENT_SENTINEL', 'jev_judgments': {'raw_response': 'RAW_MODEL_SENTINEL'},
        'functional_quote': 'Creates invoices.'}])
    path = tmp_path / 'report.md'
    export_report([opportunity], [], path)
    assert 'Creates invoices.' in path.read_text()
    assert 'RAW_FULL_CONTENT_SENTINEL' not in path.read_text()
    assert 'RAW_MODEL_SENTINEL' not in path.read_text()
