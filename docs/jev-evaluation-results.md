# JEV rubric experiment — 2026-10-09

## Conclusion

Better questions and evidence-aware scoring improved complaint triage on this
small benchmark without a reasoning-model call. JEV is worth further testing as
a cheap structured judge, **not** a standalone judge of business viability. The
revised rubric is experimental; production scoring has not been replaced.

## Actual execution

- Six free HN Algolia search requests produced 120 deduplicated complete comments.
- An assistant engineer selected and annotated 40 comments before model outputs;
  the Commander reviewed all full texts and labels. There are 40 authors and 37
  threads, with dates spanning 2008–2025. Different authors are not proof of
  independent underlying incidents.
- The frozen set contains 20 relevant, interview-worthy records, with a deliberate
  mixture of negatives, minor complaints, advice and historical workarounds.
- Both rubrics evaluated the same 40 records, one comment per request. JEV returned
  `jev-1.13.0` for all responses to `jev-latest`. All 80 requests succeeded.
- Baseline: unchanged production evaluator and singleton opportunity score.
  Revised: 11 typed questions, including three concrete Score dimensions, explicit
  availability, topic/report classification and separate payment-evidence Choice.
- Baseline input tokens: 43,496; revised: 77,856. Estimated total cost:
  **$0.005096784**, about **0.51 US cents**, using $0.042 per million input tokens
  and no output-token charge. This is an estimate, not a billing receipt. No Brave
  or reasoning-model calls were made for this experiment.
- A full cached replay returned identical judgments and metrics with **zero new
  network requests and zero additional estimated cost**.

## Results against the frozen engineer labels

“Useful” means directly relevant and manually assigned investigation priority >=2.
It does not mean commercially viable. Top-ten slots not filled by accepted records
remain empty rather than admitting rejected records to improve the metric.

| Metric | Baseline, all 40 | Revised, all 40 | Baseline, 20 holdout | Revised, 20 holdout |
|---|---:|---:|---:|---:|
| Returned in top ten | 8 | 10 | 5 | 7 |
| Useful records returned | 6 | 10 | 3 | 7 |
| Useful / ten slots | 60% | 100% | 30% | 70% |
| Useful / returned records | 75% | 100% | 60% | 100% |
| Recall of useful records in top ten | 30% | 50% | 30% | 70% |
| nDCG@10, graded ranking agreement | 0.299 | 0.704 | 0.259 | 0.767 |

The revised rubric accepted 11 records overall versus eight for the baseline.
It recovered useful cases but still rejected nine of the 20 useful records; a tenth
was accepted but ranked eleventh. These figures must not be advertised as general
accuracy. Labels are assistant-engineer assessments, not independent human truth.
Although outputs did not inform rubric tuning, the developer reviewed the whole
set before execution, including scope clarification. The split is therefore an
exploratory holdout, **not an untouched independent test set**. The development
subset improved more modestly: three to four useful returned records.

## Concrete improvements and remaining failures

1. [Inefficient Excel invoicing](https://news.ycombinator.com/item?id=2386938):
   production accepted the complaint but scored it zero; the revised rubric gave
   investigation priority 45/100. Its pain, workaround and replacement Scores were
   0.98, 1.46 and 1.99 on the anchored 0–3 scale. Payment evidence stayed unknown.
   This is the desired distinction: worth investigating without claiming a buyer.
2. [Hiring an office manager](https://news.ycombinator.com/item?id=22335905):
   baseline rejected the account; revised accepted it at 59.63, recovering concrete
   costly-workaround behavior. However, JEV categorized the employee expense as
   `paid_solution`, illustrating that payment categories still need evidence checks
   and clearer boundaries between outsourcing and buying a product.
3. [Cash-flow crisis with unpaid invoices](https://news.ycombinator.com/item?id=1826991):
   revised pain was 2.99/3 and calculated priority 73.23, yet genuine probability
   0.59 failed the hard 0.60 gate. This is a serious false negative and demonstrates
   why a probability cutoff can overwhelm otherwise useful Score judgments.
4. [Experience embedded in advice](https://news.ycombinator.com/item?id=10204166):
   JEV recognized first-hand experience and high pain but rejected the record as
   insufficiently genuine. Other advice-heavy accounts were excluded by report-kind
   gating despite containing concrete experiences. Mixed-purpose text needs to be
   assessed for contained evidence rather than its dominant rhetorical purpose.
5. [Invoice collection scripts](https://news.ycombinator.com/item?id=27596722):
   accepted but ranked eleventh. The model appeared to emphasize the now-effective
   workaround over the engineering burden of getting there. Historical burden,
   current satisfaction and current buying motivation need separate judgments.
6. [Agency workaround](https://news.ycombinator.com/item?id=9981402): payment Choice
   returned `paid_solution` without a clear explicit purchase statement for the
   reported workaround. Raw model classifications are not verified evidence.

The baseline also sometimes used a thread title rather than the actual complaint
as its problem statement. This is an extraction issue, not something improved
solely by swapping Noul for Score. The experiment changed questions, gates and
aggregation together; it cannot attribute the gain to one question type alone.

## Recommended next experiment

Freeze a v2 rubric on development examples, then evaluate a **fresh, independently
reviewed set from actual customer communities**, including nontechnical industries.
Do not retune against this holdout and reuse its result as independent validation.

- Replace broad genuine/report-kind vetoes with evidence-based routing and an
  uncertain/review-needed lane. Keep clear irrelevance and promotion exclusions.
- Separate experienced/historical burden from present unmet need and replacement
  action. Advice containing first-hand evidence should remain eligible.
- Require literal supporting excerpts for payment classifications; frustration
  supports priority, never inferred purchase probability.
- Test fewer redundant questions for cost/quality tradeoffs rather than repeating
  all calls. Use extra calls only for disagreement or selected promising clusters.
- Improve full-content retrieval and complaint extraction; Brave discovers URLs
  rather than supplying a complete discussion corpus. This experiment does not
  measure Brave retrieval yield or prove that scraping would be better.
- Once source triage is reliable, group independent reports and research alternatives
  before assigning the original six-criterion opportunity score. Reserve deeper
  synthesis for a small number of promising groups, not every comment.

## Artifacts and reproducibility

Local ignored artifacts under `reports/jev-benchmark/` retain the frozen reference,
full source text, raw answers, distributions, model versions and source links:

- `reference.json`: complete frozen records and annotations.
- `comparison.json` / `.md`: original paid run with its actual usage and cost.
- `comparison-cache-check.json` / `.md`: identical cached judgments, enriched
  dataset metadata and zero incremental cost.
- `evaluation.db`: request cache and audit logs; `collection.db`: collection logs.

Reference file SHA256 before execution:
`25f9eb3dd3a15bcef960c1a088c91e9a276b111346c1ef66d2e71c666470e9d9`.
Frozen rubric SHA256 including weights and thresholds:
`b8fa07367208cdfec1efd2e4f7e8edf19da0cb1e78248e769333ae85b396ef69`.
Reporting-only metadata preservation and per-invocation accounting fixes were made
after the run; questions, labels, scores and rankings were not changed.

Full scraped text and provider responses are intentionally not committed. Preserve
the reference locally to reproduce the exact comparison: fresh search results can
change, and the fixed annotation manifest is not a universal labeling tool.
See [the frozen protocol](jev-evaluation-protocol.md) and README commands.
