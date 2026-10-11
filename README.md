# Problem Hunter

Problem Hunter collects public discussions, selects source-backed complaints and
compares existing remedies. It is an experimental research assistant. Fresh tests
have **not established reliable automatic discovery of useful business opportunities**.
See [current results](docs/CURRENT_RESULTS.md).

## Run it

Python 3.10+ is required. Install locally and fill in the keys and actual provider
prices in `.env` using [.env.example](.env.example):

```sh
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

Brave supplies search results; TypeSafe/JEV evaluates bounded source passages.
Hacker News supplies public discussion records. No per-industry code or question
edits are required: change the topic and scope. This is the unchanged command used
for the October 11 mobile-detailing test:

```sh
.venv/bin/python main.py hunt \
  --topic "mobile car detailing appointments" \
  --scope "Owners and staff of small mobile car detailing businesses scheduling customers and handling cancellations, no-shows and weather disruptions" \
  --evaluation-rubric general-v5 --since 2025-01-01 --until 2026-10-11 \
  --discussions --queries 4 --max-sources 20 --research-top 3 --audit-yield \
  --max-requests 110 --max-cost 0.15 --rate 1 \
  --db reports/fresh-e2e-2026-10-10/ledger.db \
  --output reports/mobile-detailing-2026-10-11/results
```

For an independent new corpus, use a separate database and output prefix.
The application ceiling is per invocation: track cumulative spend across databases
and retries separately. The recorded test reused the shared budget ledger, which
contained no stored sources or opportunities before this run.

Collection, extraction, evaluation, grouping, ranking and exports run from that
command. General solution research currently needs a manually reviewed workflow
brief; `--research-top` alone cannot complete it for a generic complaint.
Save a brief with affected person, task, desired outcome and remaining constraint,
using [the example](examples/solution-brief.json), then run:

```sh
.venv/bin/python main.py research OPPORTUNITY_ID --brief brief.json --plan-only --db PATH_TO_DB
.venv/bin/python main.py research OPPORTUNITY_ID --db PATH_TO_DB --max-cost 0.15
```

Only define a brief when the supporting evidence justifies it. See
[solution research](docs/SOLUTION_LANDSCAPE.md) for interpretation and limits.

## Outputs and limits

The SQLite database stores evidence, evaluations, opportunities, caches and request
costs. Markdown is for reading; JSON retains detailed audit records; `--audit-yield`
adds a run-scoped collection/evaluation/cost funnel. Snippets, missing attribution
and uncertain publication dates require review. Publication date does not prove a
complaint remains unsolved today, including after AI adoption.

Recognized forum layouts yield one visible post with its author and timestamp,
excluding quoted replies. Known original publication dates outside the requested
window are dropped before evaluation; the yield audit lists these exclusions.
This is not universal forum support or proof of current unmet need.

Permitted Discourse and Square community pages are supported. For example, use
`--topic 'site:community.shopify.com inventory'` with an appropriate `--scope` and
the same hunt options. This changes the target, not the evaluator questions.
Visible replies are retained separately with author/date and bounded coverage.
General-v5 reviews reported fixes and rejected workarounds; confirmed original-author
resolution excludes a current lead. These labels require present-day verification.
General-v5 also makes up to 16 model comparisons to group the same specific
failure/task, keeping uncertain pairs separate. These are experimental improvements,
not proof of current demand or general grouping accuracy.
YouTube was tested separately through vidIQ and is not a built-in hunt collector.

Investigation priority ranks attention, not business potential. Commercial scores
are evidence lower bounds; zero with unknown evidence is not evidence of no market.
Search snippets can mix speakers, remedies and promotion. Exact quotations prevent
invented text but do not establish correct interpretation.

The default evaluator remains `production`; `general-v5` is the explicitly selected
current experiment. Frozen `general-v4` remains for compatibility and regressions.
Historical invoice experiment code and collection scripts have been removed.

`inspect-url`, `import-csv`, `report`, `bookmark` and `usage` are also available.
Run `.venv/bin/python main.py hunt --help` for options. The fictional
`examples/restaurants.csv` and `--offline` are demonstrations, not live validation.
A hunt or URL inspection still retrieves input even with `--offline`.

## Maintenance

Run `.venv/bin/python -m pytest -q`. Tests check implementation and evidence
handling, not whether the discovered problems are commercially useful.
Start a continuation with [the handoff](docs/SESSION_HANDOFF.md), then
[next steps](docs/NEXT_STEPS.md). Old tracked experiments remain in Git history.
Local raw evidence is retained only where needed for recent audits; it is not
automatically sent to the evaluation API.
