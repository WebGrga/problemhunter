"""Command line entry point. External evaluation is explicit and configurable."""
import argparse
import asyncio
import logging
import os
import sys
import json
import httpx
from pathlib import Path
from dotenv import load_dotenv

from .discovery import Discovery
from .extraction import Extractor
from .http import HTTP
from .importing import import_csv
from .intelligence import Evaluator, SynthesisClient
from .pipeline import Pipeline
from .research import Researcher, validate_brief, research_queries
from .reports import export_report, _rank_key
from .storage import Store


def positive(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def nonnegative(value):
    number = float(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must be nonnegative")
    return number


def parser():
    root = argparse.ArgumentParser(description="Find recurring problems with traceable evidence.")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--db', default='problem_hunter.db', help='SQLite database path')
    common.add_argument('--offline', action='store_true', help='Explicit heuristic demo; no JEV or LLM calls')
    common.add_argument('--output', default='reports/opportunities', help='Report filename prefix')
    common.add_argument('--format', choices=['markdown', 'json', 'both'], default='both')
    common.add_argument('--top', type=positive, default=20)
    common.add_argument('--research-top', type=int, default=0, help='Research this many leading groups (default 0)')
    common.add_argument('--max-requests', type=positive, default=200, help='Total network attempts per invocation')
    common.add_argument('--max-cost', type=nonnegative, help='Estimated USD ceiling; requires configured provider prices')
    common.add_argument('--rate', type=nonnegative, default=1.0, help='Minimum seconds between requests per provider')
    common.add_argument('--verbose', action='store_true')
    common.add_argument('--evaluation-rubric', default='production', help='production (default), invoice v3, or general-v4/general-v5/custom experimental JSON')
    common.add_argument('--scope', help='Research topic for URL/CSV general-v4; hunts use --topic by default')
    common.add_argument('--audit-yield', action='store_true', help='Export a run-scoped source/complaint/group/cost funnel')
    sub = root.add_subparsers(dest='command', required=True)
    hunt = sub.add_parser('hunt', parents=[common], help='Discover complaints across Brave and Hacker News')
    hunt.add_argument('--topic', required=True)
    hunt.add_argument('--queries', type=positive, default=25)
    hunt.add_argument('--max-sources', type=positive, default=100)
    hunt.add_argument('--no-fetch', action='store_true', help='Use snippets only; reports flag this limitation')
    hunt.add_argument('--since', help='Earliest publication date, YYYY-MM-DD; search dates require original-source review')
    hunt.add_argument('--until', help='Latest publication date, YYYY-MM-DD')
    hunt.add_argument('--discussions', action='store_true', help='Prefer original discussion results over vendor guides')
    inspect = sub.add_parser('inspect-url', parents=[common], help='Analyze a public webpage')
    inspect.add_argument('url')
    csv = sub.add_parser('import-csv', parents=[common], help='Analyze scraped CSV records')
    csv.add_argument('path', type=Path)
    csv.add_argument('--map', action='append', default=[], metavar='FIELD=COLUMN', help='Map URL/title/content/author/date columns')
    sub.add_parser('report', parents=[common], help='Export stored opportunities')
    research = sub.add_parser('research', parents=[common], help='Research a stored opportunity without reevaluation')
    research.add_argument('id')
    research.add_argument('--brief', type=Path, help='JSON affected_person/task/desired_outcome/unmet_constraint brief')
    research.add_argument('--workflow', help='Explicit concise workflow override; requires a complete brief')
    research.add_argument('--plan-only', action='store_true', help='Save and export the brief and search plan without network calls')
    bookmark = sub.add_parser('bookmark', parents=[common], help='Mark an opportunity for investigation')
    bookmark.add_argument('id')
    bookmark.add_argument('--remove', action='store_true')
    sub.add_parser('usage', parents=[common], help='Show persisted API request and cost accounting')
    return root


def prices_from_env():
    result = {}
    for provider, name in [('brave', 'BRAVE_COST_PER_REQUEST'), ('jev', 'JEV_COST_PER_MILLION_INPUT_TOKENS'),
                           ('llm', 'LLM_COST_PER_REQUEST')]:
        if os.environ.get(name):
            result[provider] = nonnegative(os.environ[name])
    return result


async def run(args):
    audit = None
    with Store(args.db) as store:
        first_log = store.connection.execute('SELECT COALESCE(MAX(id),0) FROM request_logs').fetchone()[0]
        if args.command == 'usage':
            print(json.dumps(store.usage_summary(), indent=2))
            return 0
        if args.command == 'bookmark':
            store.bookmark(args.id, not args.remove)
            print(f"Updated bookmark for {args.id}")
            return 0
        if args.command == 'research':
            opportunities = await research_stored(args, store)
        elif args.command == 'report':
            opportunities = store.load_opportunities()
        else:
            if not args.offline and not os.environ.get('TYPESAFE_API_KEY'):
                raise ValueError('Set TYPESAFE_API_KEY for JEV evaluation, or use --offline for a labeled heuristic demo.')
            if args.command == 'hunt' and not os.environ.get('BRAVE_SEARCH_API_KEY'):
                raise ValueError('Set BRAVE_SEARCH_API_KEY for automated discovery. URL and CSV inputs do not require it.')
            async with HTTP(store, max_requests=args.max_requests, rate=args.rate,
                            max_cost=args.max_cost, prices=prices_from_env()) as http:
                discovery = Discovery(http, brave_key=os.environ.get('BRAVE_SEARCH_API_KEY', ''))
                extractor = Extractor(http)
                llm = None
                if not args.offline and os.environ.get('LLM_ENDPOINT'):
                    llm = SynthesisClient(http, os.environ['LLM_ENDPOINT'], os.environ.get('LLM_API_KEY', ''),
                                          os.environ.get('LLM_MODEL', ''))
                if args.evaluation_rubric == 'production':
                    evaluator = Evaluator(http, key=os.environ.get('TYPESAFE_API_KEY', ''),
                                          model=os.environ.get('JEV_MODEL', 'jev-latest'), offline=args.offline, llm=llm)
                else:
                    if args.offline:
                        raise ValueError('Experimental rubrics cannot use --offline; use production for the labeled heuristic demo.')
                    from .rubric import load_rubric
                    definition = load_rubric(args.evaluation_rubric)
                    if definition['routing']['mode'] == 'universal_v4':
                        from .universal import UniversalEvaluator
                        scope = args.scope or getattr(args, 'topic', None) or 'Any real-world experienced problem; no topic restriction'
                        evaluator = UniversalEvaluator(http, os.environ.get('TYPESAFE_API_KEY', ''),
                            os.environ.get('JEV_MODEL', 'jev-latest'), scope, definition)
                        print(f'Experimental general pain-point triage. Scope: {scope}. Not market validation.', file=sys.stderr)
                    else:
                        from .triage import ExperimentalEvaluator
                        evaluator = ExperimentalEvaluator(http, os.environ.get('TYPESAFE_API_KEY', ''),
                            os.environ.get('JEV_MODEL', 'jev-latest'), definition)
                        print('Experimental invoice-specific triage; scores are not market validation.', file=sys.stderr)
                researcher = Researcher(discovery, extractor, http=http, llm=llm,
                                        jev_key='' if args.offline else os.environ.get('TYPESAFE_API_KEY', ''),
                                        jev_model=os.environ.get('JEV_MODEL', 'jev-latest'))
                pipeline = Pipeline(store, evaluator, extractor, researcher, llm=llm)
                print(f"Collecting input for {args.command}…", file=sys.stderr)
                if args.command == 'hunt':
                    sources = await discovery.hunt(args.topic, queries=args.queries, max_sources=args.max_sources,
                        **({'since': args.since, 'until': args.until, 'discussions': args.discussions}
                           if args.since or args.until or args.discussions else {}))
                    if discovery.errors:
                        print(f"Warning: {len(discovery.errors)} searches failed; results are partial. Use --verbose for details.", file=sys.stderr)
                    if not sources:
                        raise RuntimeError('Discovery returned no sources. Check credentials, request budget, and API availability.')
                elif args.command == 'inspect-url':
                    sources = [await extractor.fetch(args.url)]
                else:
                    mapping = {}
                    for item in args.map:
                        if '=' not in item:
                            raise ValueError('--map expects FIELD=COLUMN')
                        field, column = item.split('=', 1)
                        mapping[field] = column
                    sources = import_csv(args.path, mapping=mapping or None)
                print(f"Processing {len(sources)} source records…", file=sys.stderr)
                enrich = args.command == 'hunt' and not args.no_fetch
                if args.audit_yield:
                    from .discovery_audit import audit_sources
                    audit = await audit_sources(sources, extractor, enrich=enrich)
                    audit['metrics']['upstream_collection'] = discovery.hunt_summary
                    if discovery.hunt_summary:
                        audit['metrics']['upstream_raw_results'] = sum(e['raw_results'] for e in discovery.hunt_summary['search_events'])
                    sources, enrich = audit['sources'], False
                opportunities = await pipeline.process(sources, enrich=enrich,
                                                       research_top=args.research_top)
        if audit is not None:
            from .discovery_audit import summarize_yield
            store.connection.row_factory = __import__('sqlite3').Row
            logs = list(store.connection.execute('SELECT * FROM request_logs WHERE id>?', (first_log,)))
            scoped_ids = {s.id for s in audit['sources']}
            scoped_problems = [p for p in store.load_problems() if p.source_id in scoped_ids]
            summary = summarize_yield(audit['sources'], scoped_problems, opportunities, logs)
            path = Path(args.output + '.yield.json')
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({'collection': audit['metrics'], 'pipeline': summary}, indent=2) + '\n')
            print(f'Yield audit: {path}')
        opportunities = sorted(opportunities, key=_rank_key)[:args.top]
        sources = store.load_sources()
        formats = ['markdown', 'json'] if args.format == 'both' else [args.format]
        for format in formats:
            path = Path(args.output).with_suffix('.md' if format == 'markdown' else '.json')
            export_report(opportunities, sources, path, format=format, problems=store.load_problems())
            print(f"Report: {path}")
        print(f"{len(opportunities)} ranked opportunities")
        for index, opportunity in enumerate(opportunities, 1):
            priority = f'priority {opportunity.investigation_priority:.1f}; ' if opportunity.investigation_priority is not None else ''
            print(f"{index:2}. {priority}opportunity {opportunity.score:5.1f}/100 [{opportunity.evidence_strength}] {opportunity.title} ({opportunity.id})")
    return 0


async def research_stored(args, store):
    """The stored research path never creates an evaluator or regroups evidence."""
    selected = next((item for item in store.load_opportunities() if item.id == args.id), None)
    if selected is None:
        raise KeyError(f'Opportunity not found: {args.id}')
    brief = json.loads(args.brief.read_text(encoding='utf-8')) if args.brief else dict(selected.research_brief)
    if args.workflow:
        if not isinstance(brief, dict):
            raise ValueError('Research brief must be an object')
        brief['workflow'] = args.workflow
    brief = validate_brief(brief)
    if brief != selected.research_brief:
        selected.solutions = []
        selected.solution_landscape = {}
        selected.potential_fixes = []
        selected.research_status = 'brief_ready'
        selected.next_step = f"Compare existing remedies for {brief['workflow']} against: {brief['unmet_constraint']}."
    selected.research_brief = brief
    print(json.dumps({'research_brief': brief, 'search_queries': research_queries(selected)}, indent=2))
    if not args.plan_only:
        if args.offline:
            raise ValueError('Use --plan-only for stored research without network calls')
        if not os.environ.get('BRAVE_SEARCH_API_KEY'):
            raise ValueError('Set BRAVE_SEARCH_API_KEY for solution discovery, or use --plan-only')
        async with HTTP(store, max_requests=args.max_requests, rate=args.rate,
                        max_cost=args.max_cost, prices=prices_from_env()) as http:
            http.phase = 'research'
            researcher = Researcher(Discovery(http, os.environ['BRAVE_SEARCH_API_KEY']), Extractor(http),
                http=http, jev_key=os.environ.get('TYPESAFE_API_KEY', ''),
                jev_model=os.environ.get('JEV_MODEL', 'jev-latest'))
            await researcher.research([selected], top=1)
    store.save_opportunities([selected])
    return [selected]


def main(argv=None):
    load_dotenv(Path.cwd() / '.env', override=False)
    args = parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format='%(levelname)s: %(message)s')
    # HTTP libraries can expose request query strings; keep third party logs quiet.
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    try:
        if args.research_top < 0:
            raise ValueError('--research-top must be nonnegative')
        return asyncio.run(run(args))
    except (ValueError, OSError, RuntimeError, KeyError, httpx.HTTPError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('Interrupted; previously saved records remain in SQLite.', file=sys.stderr)
        return 130
