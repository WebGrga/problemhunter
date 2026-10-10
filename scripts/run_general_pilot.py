"""Bounded cross-domain integration pilot, not an accuracy/demand benchmark.

Brave finds pages, HN supplies public comments, and a supplementary official
Stack Exchange API supplies attributed bodies. No reference labels are invented.
"""
import argparse
import asyncio
import hashlib
import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from problem_hunter.cli import prices_from_env
from problem_hunter.discovery import Discovery, deduplicate
from problem_hunter.discovery_audit import audit_sources, summarize_yield
from problem_hunter.extraction import Extractor
from problem_hunter.http import HTTP
from problem_hunter.models import Source
from problem_hunter.pipeline import Pipeline
from problem_hunter.reports import export_report
from problem_hunter.rubric import load_rubric, rubric_hash
from problem_hunter.storage import Store
from problem_hunter.universal import UniversalEvaluator
from scripts.collect_reference_v2 import API, normalize_question

PILOTS = [
    ('restaurants', 'Restaurant work, food service and restaurant operations', 'restaurant staff scheduling', 'cooking', 'restaurant'),
    ('workplace', 'Organizational coordination and workplace operations', 'workplace meetings coordination', 'workplace', 'meetings'),
    ('social', 'Meeting people, making friends and social participation', 'making friends loneliness', 'interpersonal', 'friends'),
]


async def run(args):
    root = args.output
    root.mkdir(parents=True, exist_ok=True)
    rubric = load_rubric('general-v4')
    snapshot = {'rubric': rubric, 'rubric_sha256': rubric_hash(rubric),
        'file_sha256': hashlib.sha256(Path('problem_hunter/rubrics/general-v4.json').read_bytes()).hexdigest(),
        'note': 'Frozen before collecting pilot texts; integration/qualitative review only, no reference labels.',
        'max_cost_usd': args.max_cost, 'max_requests': args.max_requests}
    protocol_path = root / 'protocol.json'
    if protocol_path.exists():
        original_protocol = json.loads(protocol_path.read_text())
        if original_protocol['rubric_sha256'] != snapshot['rubric_sha256']:
            raise ValueError('Frozen pilot rubric changed; use a new output directory')
        args.max_cost = min(args.max_cost, original_protocol['max_cost_usd'])
        args.max_requests = min(args.max_requests, original_protocol['max_requests'])
    else:
        protocol_path.write_text(json.dumps(snapshot, indent=2) + '\n')
    with Store(root / 'pilot.db') as store:
        unpriced = store.connection.execute("SELECT COUNT(*) FROM request_logs WHERE cached=0 AND cost IS NULL AND provider IN ('brave','jev','llm')").fetchone()[0]
        if unpriced:
            raise ValueError('Prior paid requests have unknown cost; cannot enforce a cumulative budget')
        spent = store.connection.execute('SELECT COALESCE(SUM(cost),0) FROM request_logs WHERE cached=0').fetchone()[0]
        attempts = store.connection.execute('SELECT COUNT(*) FROM request_logs WHERE cached=0').fetchone()[0]
        async with HTTP(store, max_requests=max(0, args.max_requests-attempts), max_cost=max(0, args.max_cost-spent), prices=prices_from_env(), retries=1) as http:
            discovery = Discovery(http, os.environ.get('BRAVE_SEARCH_API_KEY', ''))
            extractor = Extractor(http)
            summaries, failures = {}, []
            backoff = 0
            for name, scope, query, site, api_query in PILOTS:
                http.phase = 'collection'
                first_log = store.connection.execute('SELECT COALESCE(MAX(id),0) FROM request_logs').fetchone()[0]
                pools = {}
                for provider, search in [('brave', query + ' "frustrating"'), ('hn', query)]:
                    try:
                        pools[provider] = await discovery.search(search, provider=provider)
                    except Exception as exc:
                        failures.append({'topic': name, 'provider': provider, 'error': str(exc)})
                        pools[provider] = []
                pools['stackexchange'] = []
                if not backoff:
                    try:
                        response = await http.request('GET', API, provider='stackexchange', params={
                            'site': site, 'q': api_query, 'sort': 'relevance', 'order': 'desc',
                            'pagesize': 12, 'filter': 'withbody'})
                        response.raise_for_status()
                        data = response.json()
                        if data.get('error_id') or data.get('quota_remaining', 1) <= 0:
                            raise ValueError(data.get('error_message', 'API quota exhausted'))
                        backoff = data.get('backoff', 0)
                        for item in data.get('items', []):
                            row = normalize_question(item, site, api_query)
                            if row:
                                pools['stackexchange'].append(Source(row['url'], row['title'], row['content'], row['source'], row['author'], row['published_at'],
                                    metadata={'discovery_provider': 'stackexchange', 'original_html': row['original_html'],
                                        'license': row['license'], 'thread_url': row['thread_url'], 'author_id': row['author_id']}))
                    except Exception as exc:
                        failures.append({'topic': name, 'provider': 'stackexchange', 'error': str(exc)})
                else:
                    failures.append({'topic': name, 'provider': 'stackexchange', 'error': f'Collection stopped for API backoff {backoff}s; no bypass'})
                sources = deduplicate([s for pool in pools.values() for s in pool[:3]])
                # Preserve raw input before evaluating; never put outcomes into model state.
                (root / f'{name}-inputs.json').write_text(json.dumps({'scope': scope,
                    'provider_candidates': {p: len(rows) for p, rows in pools.items()},
                    'records': [__import__('dataclasses').asdict(s) for s in sources]}, indent=2) + '\n')
                audit = await audit_sources(sources, extractor, enrich=True)
                evaluator = UniversalEvaluator(http, os.environ.get('TYPESAFE_API_KEY', ''),
                    os.environ.get('JEV_MODEL', 'jev-latest'), scope, rubric)
                opportunities = await Pipeline(store, evaluator).process(audit['sources'])
                problems = store.load_problems()
                store.connection.row_factory = __import__('sqlite3').Row
                logs = list(store.connection.execute('SELECT * FROM request_logs WHERE id>?', (first_log,)))
                summaries[name] = {'collection': audit['metrics'], 'pipeline': summarize_yield(audit['sources'], problems, opportunities, logs)}
                print(name, json.dumps(summaries[name]['pipeline']['funnel']))
            for extension, format in (('.json', 'json'), ('.md', 'markdown')):
                export_report(store.load_opportunities(), store.load_sources(), root / ('opportunities' + extension), format=format, problems=store.load_problems())
            summary = {'topics': summaries, 'failures': failures, 'network_requests': http.requests,
                'estimated_new_cost_usd': http.cost, 'estimated_cumulative_cost_usd': spent + http.cost, 'usage': store.usage_summary(),
                'limitations': ['Small purposive samples; no independent human labels or accuracy metric',
                    'New collection, not necessarily newly published evidence', 'Company size is not established by workplace source membership',
                    'No automated solution research on unreviewed workflow labels', 'Community API sample is supplementary to Brave, not a fair scraper benchmark']}
            (root / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
            print('New estimated cost USD:', http.cost)


if __name__ == '__main__':
    load_dotenv(Path.cwd() / '.env', override=False)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('reports/general-pilot'))
    parser.add_argument('--max-cost', type=float, default=.15)
    parser.add_argument('--max-requests', type=int, default=100)
    args = parser.parse_args()
    if args.max_cost < 0 or args.max_requests < 1:
        parser.error('Budgets must be nonnegative cost and positive requests')
    if not os.environ.get('BRAVE_SEARCH_API_KEY') or not os.environ.get('TYPESAFE_API_KEY'):
        parser.error('Brave and TypeSafe keys are required')
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    logging.getLogger('httpx').setLevel(logging.WARNING)
    asyncio.run(run(args))
