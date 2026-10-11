import json
import httpx
import pytest
from bs4 import BeautifulSoup

from problem_hunter.extraction import discussion_context
from problem_hunter.grouping import workflow_group
from problem_hunter.http import HTTP
from problem_hunter.models import Source, Problem
from problem_hunter.pipeline import Pipeline
from problem_hunter.storage import Store
from problem_hunter.universal import UniversalEvaluator
from test_universal import response
from test_usefulness import choices


@pytest.mark.asyncio
@pytest.mark.parametrize('status,author,date,expected,accepted', [
    ('author_resolved', 'merchant', '2026-02-01', 'author_resolved', False),
    ('author_resolved', 'merchant', '2025-12-01', 'unknown', True),
    ('author_resolved', 'another-person', '2026-02-01', 'remedy_reported', True),
    ('remedy_reported', 'vendor', '2026-02-01', 'remedy_reported', True),
    ('rejected', 'merchant', '2026-02-01', 'rejected', True),
])
async def test_reply_confirmation_keeps_attribution_and_never_assumes_resolution(tmp_path, status, author, date, expected, accepted):
    def handler(request):
        payload = json.loads(request.content)
        q = payload['questions']
        if 'relevance' in q:
            return httpx.Response(200, json=response(q))
        if 'actor_task_fit' in q:
            values = {'actor_task_fit': 'yes', 'experienced_failure': 'yes', 'experience_status': 'continuing',
                'workaround_same_speaker': 'unknown', **{f: 'p0' for f in ('actor', 'task', 'consequence', 'unmet_constraint', 'existing_remedy')}}
        elif 'r0' in q:
            assert payload['state']['replies']['r0']['author'] == author
            values = {'r0': status}
        else:
            values = {name: 'none' for name in q}
        return httpx.Response(200, json=choices(q, values))
    with Store(tmp_path / 'test.db') as store:
        async with HTTP(store, rate=0, transport=httpx.MockTransport(handler)) as http:
            source = Source('https://example.com/post', 'Bookings', 'We lose bookings because our calendar is broken.',
                author='merchant', published_at='2026-01-01', metadata={'discussion_context': {'posts': [
                    {'author': author, 'published_at': date, 'content': 'The workaround outcome.', 'page_url': 'https://example.com/post'}]}})
            groups = await Pipeline(store, UniversalEvaluator(http, 'fixture', rubric='general-v5')).process([source])
            saved = store.load_sources()[0]
            assert saved.metadata['discussion_review']['status'] == expected
            assert bool(groups) == accepted
            assert 'The workaround outcome.' not in saved.content
            assert not saved.metadata.get('workflow_brief')
            if expected == 'remedy_reported':
                assert saved.metadata['triage']['need_status'] == 'unknown'


def test_visible_reply_extraction_removes_quotes_duplicates_and_incomplete_attribution():
    post = '<div class="crawler-post"><span itemprop="author"><span itemprop="name">{author}</span></span><time datetime="2026-01-01"></time><div itemprop="text">{body}</div></div>'
    html = post.format(author='merchant', body='Original complaint.')
    html += post.format(author='vendor', body='Try this.<blockquote>Original complaint.</blockquote>') * 2
    html += '<div class="crawler-post"><div itemprop="text">Unattributed answer.</div></div>'
    result = discussion_context(BeautifulSoup(html, 'html.parser'), ('Original complaint.', 'merchant', '2026-01-01'), 'https://example.com')
    assert len(result['posts']) == 1 and result['posts'][0]['content'] == 'Try this.'
    assert result['posts'][0]['author'] == 'vendor' and result['skipped_unattributed'] == 1


@pytest.mark.asyncio
async def test_grouping_does_not_chain_different_constraints_and_respects_call_bound():
    problems = [Problem(str(i), 'Inventory mismatch', 'operations', {'first_hand': 1, 'triage': {'need_status': 'unknown'}},
        {'impact': f'Inventory synchronization failure {i}'}, id=str(i)) for i in range(3)]
    sources = [Source('', '', f'Inventory synchronization failure report {i}', author=str(i), id=str(i)) for i in range(3)]
    calls = []
    async def judge(state, questions):
        pair = {state['left']['failure'][-1], state['right']['failure'][-1]}; calls.append(pair)
        return {'equivalent': 'unknown' if pair == {'0', '2'} else 'yes'}
    groups = await workflow_group(problems, sources, judge)
    assert sorted(len(g.problem_ids) for g in groups) == [1, 2]
    calls.clear()
    await workflow_group(problems, sources, judge, max_pairs=1)
    assert len(calls) == 1
