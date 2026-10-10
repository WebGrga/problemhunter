# Fresh-sample JEV experiment: v1 versus v2

Protocol recorded before model outputs. V2 questions were frozen before the
Commander viewed the fresh reference records or annotations. A separate assistant
engineer selected and labeled them without seeing v2 questions or earlier JEV
outputs. This is independent question design versus annotation work, **not
independent human ground truth**.

## Frozen inputs

- V2 JSON file SHA256:
  `f02edb471c50155cf879f64b32881d3b6a501a6a1de094eb02e16143cf4196a6`.
- V2 canonical definition SHA256 (formatting independent):
  `a7195433252f9e319d80d58d0380d70495f63d0710d22a3733a9f34a672e2fcf`.
- Reference file SHA256:
  `091ecdf37249328fc035e5e22daf4f09e8e644385a3caa47e53a22974cb8ddc5`.
- 40 newly selected, complete public Stack Exchange questions, all held out from
  rubric design; no ID/content overlap with the preceding HN sample.
- Reference labels use the same priority 0–3 investigation rubric as before.
  Useful means priority >=2 and directly relevant invoice administration.
- Purposive sample, historical dates, site/question-format differences and
  assistant labels limit generalization. Different authors/threads do not certify
  independent incidents or representative frequency.

## Comparisons and hypotheses

Compare the previous **experimental invoice-v1**, not the production six-criterion
opportunity score, with **invoice-v2**, on exactly the same new questions.

V2 removes the broad genuine-probability veto and dominant-purpose report-kind
classification. A contained-evidence Choice decides whether an account includes
experienced burden or a consequential workaround, even inside advice. Clear
off-topic/nonproblem/promotion records are excluded. Ambiguous evidence, adjacent
scope or uncertain first-hand attribution go to an explicit review lane rather
than being silently discarded. Primary candidates rank before review candidates;
within a lane, two supported dimensions rank ahead of one, then score, then ID.
Unknown dimensions still do not become zero. Payment evidence remains separate.

V2 also distinguishes past experienced burden from the author's unmet need at
publication and rates explicitly described setup effort as well as maintenance.
No question establishes demand today or converts frustration into buying intent.

Predefined no-cost ablation: reuse **v1 answers unchanged**, set only its genuine
cutoff to zero, and retain its report-kind/relevance/availability gates and weights.
This separates the effect of that single gate from new question wording.

Hypothesis: v2 retains more relevant useful accounts than v1 without flooding its
top ten with low-value/off-topic records. Inspect useful-accepted counts and recall,
top-ten useful yield, precision among returned records and nDCG. Report review-lane
counts, false positives and missed useful records. An exploratory guardrail is at
least 80% useful among returned top-ten records; do not treat it as a calibrated
production acceptance test. No hypothesis guarantees improvement.

## Execution

One full record per state, all 11 questions in a single request for each rubric.
40 records × 2 rubrics = 80 model requests. No repeated reasoning-model calls.
90 network-attempt limit and $0.05 estimated JEV ceiling; shared HTTP cache/rate
limits and actual token accounting. Preserve paid-run accounting, then replay to
a different report prefix to verify zero new calls and identical judgments.

Snapshot both exact rubrics and hashes in every report. Do not change either
rubric or labels after reading outputs. Any v3 requires a new version and fresh
evaluation records. Reporting fixes must be identified separately from model or
label changes.
