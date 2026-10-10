# V3 implementation and live verification

Verified October 9, 2026, using local ignored credentials. V3 stays opt-in;
production questions and production commercial score rules are not promoted or
replaced. No dashboard or extension was added.

## Implemented work

1. Literal short-loss checks, remedy-payment quote checks and contradiction review.
   Customer invoice payments and payroll do not establish spending on a remedy.
2. Eight readable v3 questions, versus eleven in v2, plus a fresh 40-record holdout
   and a genuine-gate-only v1 ablation on the same texts.
3. Investigation priority, commercial lower-bound score, payment evidence, need
   status, review cautions and next validation steps in reports. Markdown omits
   raw research payloads; JSON retains them and all supporting evidence.
4. Discovery result/extraction/attribution/complaint/recurrence funnels and costs
   tagged by collection, evaluation and research. Unknown prices stay unknown.
5. An opt-in shared pipeline, invoice workflow grouping hypotheses, bounded
   existing-solution research and a label-free reference/CSV replay utility.

Actual tested questions: `problem_hunter/rubrics/v3.json`. The freeze hashes,
selection procedure and restrictions are in `jev-v3-protocol.md`. Do not retune
the frozen questions, labels or literal rules against these results.

## Same-text comparison

All 40 records were unused historical Stack Exchange questions from an existing
official API candidate pool. They have full bodies, URLs, author/date attribution
and licensing. Another assistant labeled them before seeing the tested questions
or outcomes: these are not independent human ground-truth labels. There were 17
assistant-labeled useful records; the purposive sample does not measure prevalence.

| Variant | Questions | Useful retained | Total retained | Top-10 useful | nDCG@10 | Review records |
|---|---:|---:|---:|---:|---:|---:|
| V2 | 11 | 16/17 | 17 | 10/10 | 0.952 | 0 |
| V1, genuine cutoff removed only | 11 | 16/17 | 17 | 10/10 | 0.897 | 0 |
| V3, grounded checks | 8 | 17/17 | 19 | 10/10 | 0.867 | 2 |

The V1 question count includes genuine, retained in requests for this gate-only
ablation; removing its cutoff does not remove its question. V3 admitted two weak
controls below the top ten. Its retention improved by one useful record, but its
graded ranking worsened. None of this demonstrates an enormous overall accuracy
gain, calibrated demand prediction or commercial viability.

All 120 model requests completed as `jev-1.13.0`. Input tokens were 87,184 for v2,
73,984 for the gate-only variant and 77,824 for v3: v3 used about 10.7% fewer input
tokens than v2. Estimated comparison cost was $0.010037664. A cached replay made
zero new network requests, cost $0, and produced identical metrics.

The two v3 review flags rejected unsupported payment interpretations: a customer's
refusal to pay an invoice was not the author's refusal to buy a remedy; merely
mentioning an outsourcing agency did not prove remedy expenditure. Literal rule
checks are conservative keyword checks, not semantic truth or calibrated intent.

## Live hunt and source yield

Six Brave queries and three HN queries for `freelancer invoicing` returned 82 raw
results (29 Brave, 53 HN). There were 69 unique candidates; the balanced source
limit retained 24. Of those:

| Provider | Retained | Full bodies | Attributed full bodies | Triage-retained sources |
|---|---:|---:|---:|---:|
| Brave + permitted page extraction | 12 | 4 | 2 | 4 |
| HN official discussion API | 12 | 12 | 12 | 3 |

Eight sources remained snippets after robots/access restrictions or retrieval
failures; restrictions were respected. Seven posts passed triage, producing one
multi-report group but **zero recurring groups across identified complainants**.
The shortlist included a résumé and promotional/tool material. This is weak,
noisy discovery, not a validated opportunity set. Full text alone is insufficient:
HN attribution was better, but only three HN posts passed this triage.

The original hunt used 77 network attempts, including research: collection
$0.030000000, evaluation $0.002450364, research $0.020937566, total $0.053387930.
A fixed export replay reused all search/evaluation requests, retried two free web
retrievals, and cost $0. Its `.yield.json` describes the replay, not original cost.
The original paid amounts above are preserved in the same database's first 77 logs.

## Grouping, research and CSV replay

The 40 full reference posts passed the same pipeline: 19 retained statements,
12 groups, and three groups with at least two identified complainants. Broad
invoice family assignment is a grouping **hypothesis**, not a measured semantic
equivalence result; some groups may combine different root causes.

Forty cached JEV evaluations cost $0 in the pipeline replay. Initial research on
two vague titles cost $0.021113714 and surfaced generic finance results. A guard
now marks such groups `needs_workflow_definition`, downgrades their previous
generic candidates, and spends research requests only on defined experimental
workflows. This does not change frozen benchmark evaluations.

CSV parity imported the same 40 attributed bodies into the existing corpus,
retained the same 19 statements/12 groups and evaluated zero unchanged posts.
Existing full-API evidence was preserved, not downgraded to CSV. New research on
invoice generation/installment workflows cost $0.020838698; all returned products
remained unverified candidates and research partial. No missing weaknesses or
current prices were invented. This is import/cache parity, not an independent
scraper benchmark or evidence that CSV acquisition outperforms APIs.

Total new estimated paid cost across comparison, hunt and both research tests:
$0.105378006 (about 10.54 US cents). Estimates used published list rates:
[Brave $5/1,000 search requests](https://api-dashboard.search.brave.com/documentation/pricing)
and [JEV $0.042/million input tokens](https://docs.typesafe.ai/models).
Free credits, taxes and provider billing rounding are not modeled.

## Tests and reproduction

144 local tests passed on Python 3.12, covering mocked API contracts, evidence
checks, grouping/scoring, request accounting, database migration, reports and CLI
imports/repeats. Wheel construction succeeded and includes the readable rubrics.

```sh
python -m pytest -q
python -m problem_hunter.benchmark questions --rubric v3
python main.py hunt --topic 'freelancer invoicing' --queries 6 --max-sources 24 \
  --evaluation-rubric v3 --audit-yield --research-top 2 --top 5 \
  --db reports/new-hunt.db --output reports/new-hunt
```

Set `BRAVE_SEARCH_API_KEY` and `TYPESAFE_API_KEY` in ignored `.env`; price settings
are required to enforce `--max-cost`. Raw reports/databases and attribution-rich
reference artifacts stay local and ignored. `scripts/run_reference_pipeline.py`
accepts a collected reference JSON, strips labels before evaluation, and can export
its bodies with `--csv`; use it for reproducible replay, not fresh collection.

## Decision and next validation

Do not promote v3 to production based on this test. The next bottlenecks are
source relevance/first-hand quality, representative multi-community acquisition,
workflow extraction and root-cause grouping, followed by human review. A future
v4 needs new frozen questions and an independently reviewed fresh dataset. Better
questions can change retention, but cannot turn frustration into observed buying
intent or compensate for unavailable discussion bodies. Optional stronger-model
synthesis has not been tested and is not required for this implementation.
