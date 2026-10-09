# Problem Hunter

A Python CLI for discovering recurring real-world problems and ranking evidence-backed
opportunities. Brave searches broad industries; Hacker News adds attributed discussions.
URL inspection and scraped CSV imports use the same pipeline. SQLite stores original
content, judgments, evidence, grouped opportunities, bookmarks, research and usage.

## Setup

Requires Python 3.10+. Python 3.12 is recommended.

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
export BRAVE_SEARCH_API_KEY='your-key'
export TYPESAFE_API_KEY='your-key'
```

The CLI loads `.env` from the current directory; existing shell variables take precedence.
Copy [.env.example](.env.example) to `.env` and fill in your keys, or export them as above.
Never commit credentials. Brave is required for hunts and solution searches; JEV is
required for normal evaluation. CSV and URL analysis need only JEV. HN needs no key.

```sh
python main.py hunt --topic "restaurants" --queries 25 --top 20 --research-top 5
python main.py inspect-url "https://example.com/discussion"
python main.py import-csv results.csv --map content=Review --map url=Link --map author=Username
python main.py report --db problem_hunter.db --output reports/saved
python main.py bookmark OPPORTUNITY_ID
python main.py usage
```

`problem-hunter` and `python -m problem_hunter` provide the same commands. Run
`python main.py hunt --help` for limits and reporting options. Options belong after
the command. Reports default to `reports/opportunities.md` and `.json`. `--db`,
`--output`, `--format`, and `--top` control persistence and exports.

## Safe demonstration without API credentials

```sh
python main.py import-csv examples/restaurants.csv --offline --db demo.db --output reports/demo
python main.py import-csv examples/restaurants.csv --offline --db demo.db --output reports/demo
python -m pytest -q
```

The example data is fictional, uses reserved example URLs, and must not be treated
as market research. `--offline` selects labeled heuristic judgments; it never
silently replaces JEV. It suppresses model calls, but a hunt or URL inspection still
retrieves input from the network. The sample yields two opportunity groups from
three retained reports, with the copied complaint excluded. The repeat evaluates
zero unchanged sources. All evidence remains weak in this demonstration.

## Evaluation and deeper synthesis

The actual JEV questions are now readable/editable files:
[production](problem_hunter/rubrics/production.json),
[experiment v1](problem_hunter/rubrics/v1.json), and
[experiment v2](problem_hunter/rubrics/v2.json).
See [question-file instructions](problem_hunter/rubrics/README.md).
Preview any set without API calls:

```sh
python -m problem_hunter.benchmark questions --rubric v2
```

Every benchmark report saves the exact question/routing snapshots and hashes.
Use a new version for edits; do not tune frozen questions against their test results.

The official [TypeSafe API](https://docs.typesafe.ai/api) accepts `state`, `model`
and a map of typed questions at `POST /v1/systemone`, authenticated with a bearer
token. This application batches all seven judgments for one source into a supported
request. Each source has its own state: live testing found that mixing unrelated
documents can leak payment evidence across them. There is no invented batch endpoint.
Noul answers measure probability, Score answers use rubric indices, and Choice
answers identify categories. Raw responses, actual model and batch usage are retained.

Optional deeper extraction, semantic grouping and solution synthesis can use an
explicit JSON chat-completions provider:

```sh
export LLM_ENDPOINT='https://your-provider.example/v1/chat/completions'
export LLM_API_KEY='your-key'
export LLM_MODEL='your-model'
```

The provider must support `messages` and `response_format={"type":"json_object"}`.
Returned source IDs, functional excerpts and evidence quotes are checked against
the supplied records. Interpretations and suggested fixes remain model inferences
or hypotheses. Without this configuration, grouping uses conservative vocabulary
similarity and solution results remain candidates requiring verification.

## Scoring and evidence

The production rubric is intentionally separate from the new experimental JEV
comparison. A live 40-comment experiment improved triage with concrete Score
questions but exposed hard-gate false negatives. See
[results and limitations](docs/jev-evaluation-results.md) before interpreting scores.

The score is an evidence-supported lower bound out of 100:

| Criterion | Maximum points | Evidence used |
|---|---:|---|
| Pain severity | 25 | JEV rubric plus a literal loss excerpt |
| Frequency | 20 | Five distinct attributed complainants fill the scale |
| Willingness to pay | 20 | Three distinct attributed complainants with explicit payment statements |
| Existing solution weakness | 15 | Three relevant alternatives with literal weakness excerpts |
| Customer reachability | 10 | Unknown until independently validated |
| Implementation feasibility | 10 | Unknown until independently validated |

Unknown criteria contribute zero, and coverage is shown separately. Anonymous
reports are preserved but do not become identified users. Repeated authors and
copied content cannot inflate independent counts. Evidence strength is weak or
moderate based on source quality and recurrence; neither a high score nor model
confidence proves demand. No opportunity is automatically labeled validated.

## Reliability, budgets and collection policy

Searches are concurrent and bounded. Requests are cached in SQLite for 24 hours,
with credentials hashed into cache identity; secrets are excluded from request logs.
Content and evaluation fingerprints avoid repeated evaluation, including rejected
inputs. HTTP retries cover transient failures and honor bounded Retry-After delays.
`--max-requests 200`, `--rate 1`, `--max-sources 100` and `--research-top 0` are defaults.
Retries, robots checks, retrieval and synthesis all count toward the request limit.

Optional `--max-cost` enforces an estimated invocation budget. Configure your plan's
`BRAVE_COST_PER_REQUEST`, `JEV_COST_PER_MILLION_INPUT_TOKENS`, and, if used,
`LLM_COST_PER_REQUEST`. Unpriced paid providers are refused when a cost ceiling is
active. JEV reserves a conservative token allowance before a call and reconciles
with returned usage. Failed/retried calls are conservatively accounted for. Estimates
are not invoices; unconfigured prices are reported as unknown, not free. Official
[JEV model pricing](https://docs.typesafe.ai/models) is available for configuration.

Public-page collection checks robots, honors crawl delays, prohibits private network
destinations, validates redirects, pins checked DNS addresses, and bounds downloads.
It fails closed when robots cannot be verified. Authentication, paywalls, CAPTCHAs
and JavaScript-only content are not bypassed. Users must also respect applicable site
terms and their Brave plan's retention rights. Snippet fallback is explicitly flagged.

## Testing and limitations

Tests cover mocked Brave/HN/JEV responses, extraction, CSV mapping, deduplication,
grouping, scoring, SQLite transactions, cache/retry/budget behavior, reports and CLI
integration. GitHub Actions runs the suite on Python 3.10 and 3.12.

Paid Brave/JEV and optional synthesis require your credentials for live verification.
The deterministic offline path and mocked contracts do not establish live service
quality. Default grouping may miss broad paraphrases; only one main problem is
extracted per source. Whole-page author metadata can be incomplete, prices can be
stale, and this MVP deliberately leaves unresearched feasibility/reachability at zero.
Review promising groups, interview independent affected users, and confirm their
actual workflows, losses, budgets and existing alternatives before building a solution.

See [architecture and boundaries](docs/architecture.md). No dashboard or browser
extension is included.

## Reproduce the JEV rubric experiment

The benchmark does not modify production evaluations or opportunity scoring.
Its revised score is complaint investigation priority, not business viability.
`TYPESAFE_API_KEY` is the only credential needed; HN collection needs no key.

```sh
python scripts/collect_reference.py
python scripts/collect_reference.py --freeze
python -m problem_hunter.benchmark compare reports/jev-benchmark/reference.json \
  --db reports/jev-benchmark/evaluation.db --output reports/jev-benchmark/comparison \
  --max-requests 90 --max-cost 0.05
```

The freeze step applies the reviewed manifest to the captured candidate pool. HN
search results may change and omit manifest IDs; preserve the original reference
file rather than assuming a fresh search reproduces it. For new topics, supply
your own complete, attributed record JSON with pre-output annotations (`relevance`,
integer `priority` 0–3, `reason`, and `split`: `development` or `holdout`). Never let
the model being evaluated generate its own reference labels. The wrapper accepts
`records` with dataset metadata; inspect the collector for the schema.

Reports retain both rankings, errors, source links, supported dimensions, raw
answers, usage and input/rubric fingerprints. Repeated calls use the 24-hour cache;
use a different output prefix to preserve the original paid-run accounting.
The current price assumption is $0.042 per million JEV input tokens; configure
`JEV_COST_PER_MILLION_INPUT_TOKENS` for your plan. Review the official price before
a new run. Raw data, reports, SQLite databases and credentials stay Git-ignored.

For the fresh-sample v1-versus-v2 experiment (not production scoring):

```sh
python -m problem_hunter.benchmark compare reports/jev-benchmark-v2/reference.json \
  --rubric v2 --reference-rubric v1 --db reports/jev-benchmark-v2/evaluation.db \
  --output reports/jev-benchmark-v2/comparison --max-requests 90 --max-cost 0.05
```

Its [pre-output protocol](docs/jev-v2-protocol.md) uses new complete Stack Exchange
questions, independently labeled by another assistant engineer. The collector
`scripts/collect_reference_v2.py` retrieves full bodies through the public API and
can freeze separately supplied annotation JSON; it does not fabricate labels or
use JEV to label its own benchmark. The frozen artifacts remain local.
See [fresh test results and remaining failures](docs/jev-v2-results.md).
