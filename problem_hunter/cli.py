"""Command line entry point. External evaluation is explicit and configurable."""
import argparse
import asyncio
import logging
import os
import sys
import httpx
from pathlib import Path
from dotenv import load_dotenv

from .discovery import Discovery
from .extraction import Extractor
from .http import HTTP
from .importing import import_csv
from .intelligence import Evaluator, SynthesisClient
from .pipeline import Pipeline
from .research import Researcher
from .reports import export_report
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
    sub = root.add_subparsers(dest='command', required=True)
    hunt = sub.add_parser('hunt', parents=[common], help='Discover complaints across Brave and Hacker News')
    hunt.add_argument('--topic', required=True)
    hunt.add_argument('--queries', type=positive, default=25)
    hunt.add_argument('--max-sources', type=positive, default=100)
    hunt.add_argument('--no-fetch', action='store_true', help='Use snippets only; reports flag this limitation')
    inspect = sub.add_parser('inspect-url', parents=[common], help='Analyze a public webpage')
    inspect.add_argument('url')
    csv = sub.add_parser('import-csv', parents=[common], help='Analyze scraped CSV records')
    csv.add_argument('path', type=Path)
    csv.add_argument('--map', action='append', default=[], metavar='FIELD=COLUMN', help='Map URL/title/content/author/date columns')
    sub.add_parser('report', parents=[common], help='Export stored opportunities')
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
    with Store(args.db) as store:
        if args.command == 'usage':
            import json
            print(json.dumps(store.usage_summary(), indent=2))
            return 0
        if args.command == 'bookmark':
            store.bookmark(args.id, not args.remove)
            print(f"Updated bookmark for {args.id}")
            return 0
        if args.command == 'report':
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
                evaluator = Evaluator(http, key=os.environ.get('TYPESAFE_API_KEY', ''),
                                      model=os.environ.get('JEV_MODEL', 'jev-latest'), offline=args.offline, llm=llm)
                researcher = Researcher(discovery, extractor, http=http, llm=llm)
                pipeline = Pipeline(store, evaluator, extractor, researcher, llm=llm)
                print(f"Collecting input for {args.command}…", file=sys.stderr)
                if args.command == 'hunt':
                    sources = await discovery.hunt(args.topic, queries=args.queries, max_sources=args.max_sources)
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
                opportunities = await pipeline.process(sources, enrich=args.command == 'hunt' and not args.no_fetch,
                                                       research_top=args.research_top)
        opportunities = sorted(opportunities, key=lambda o: (-o.score, o.id))[:args.top]
        sources = store.load_sources()
        formats = ['markdown', 'json'] if args.format == 'both' else [args.format]
        for format in formats:
            path = Path(args.output).with_suffix('.md' if format == 'markdown' else '.json')
            export_report(opportunities, sources, path, format=format, problems=store.load_problems())
            print(f"Report: {path}")
        print(f"{len(opportunities)} ranked opportunities")
        for index, opportunity in enumerate(opportunities, 1):
            print(f"{index:2}. {opportunity.score:5.1f}/100 [{opportunity.evidence_strength}] {opportunity.title} ({opportunity.id})")
    return 0


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
