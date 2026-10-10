# Fresh JEV rubric test — 2026-10-09

## What improved, and what did not

V2 retained **21 of 22 engineer-labeled useful leads**, compared with **14 of 22**
for the previous experimental v1. Its top ten contained ten useful leads versus
nine for v1. However, simply removing v1's genuine cutoff also retained 21 of 22
and achieved a better graded ranking on this sample. The result supports fixing
our filtering/aggregation, not claiming that elaborate questions unlock unlimited
model improvements. V2 remains experimental; production scoring is unchanged.

## Fresh reference and actual calls

The rubric was frozen before the Commander viewed the new records. A separate
assistant engineer selected and labeled the full texts without viewing v2 questions
or previous JEV outputs. These are still assistant judgments, **not independent
human ground truth**.

Six successful free public Stack Exchange API requests collected 508 attributed,
deduplicated complete candidates; two earlier sandbox DNS failures were also logged.
The reference includes 40 questions: 30 Freelancing, eight Money, two Workplace;
39 site-qualified author identities and 40 threads. No IDs or content overlap the
earlier HN set. All records were held out from question design. Publication dates
span June 2013–August 2025: “fresh” means newly selected, not current market demand.
Selection is purposive, not representative. Questions and comments have different
styles; cross-run metrics on different datasets are not directly comparable.

Both experimental rubrics evaluated every full record once. All **80 calls**
succeeded and returned model `jev-1.13.0`. V1 used 74,355 input tokens; v2 used
87,555, approximately 17.8% more. Total estimated cost was **$0.00680022**, about
**0.68 US cents**, using the [official input-token price](https://docs.typesafe.ai/models)
of $0.042 per million with free output tokens. This is an estimate, not an invoice.
No Brave or reasoning-model calls were used. Cached replay reproduced all answers,
scores, rankings and fingerprints with **zero new requests/cost**.

## Comparison on the same 40 held-out questions

Useful means directly relevant invoice administration with frozen engineer priority
>=2. All variants returned ten top-ranked records. Accepted leads below rank ten
are counted separately from top-ten recall.

| Metric | Experimental v1 | Same v1 answers, no genuine cutoff | Experimental v2 |
|---|---:|---:|---:|
| Useful retained / 22 | 14 | 21 | 21 |
| Total retained | 16 | 24 | 23 |
| Useful in top ten | 9 | 9 | 10 |
| Useful among top ten | 90% | 90% | 100% |
| Useful recall in top ten | 40.9% | 40.9% | 45.5% |
| nDCG@10: graded ranking agreement | 0.758 | 0.857 | 0.830 |
| Review-lane candidates | 0 | 0 | 0 |

Removing the genuine cutoff reused unchanged v1 responses and required no extra
API calls. Its report-kind, relevance, availability and score rules stayed intact.
V2 changed both wording and routing; this ablation shows the retention gain cannot
be attributed solely to improved questions. The new review lane is implemented
and unit-tested but received no candidates here, so its empirical value remains
unverified. Small differences such as nine versus ten hits need replication.

## Examples and remaining problems

- [Translator losing time to Excel invoices](https://freelancing.stackexchange.com/questions/1821):
  v1 and v2 both rank this useful lead highly. V2 priority is 57.43/100, payment
  intent unknown. Frustration and an active search for alternatives can warrant
  investigation without fabricating buying intent.
- [Photography installment invoicing](https://freelancing.stackexchange.com/questions/1801):
  a business tried multiple named tools and describes a specific tracking/forecasting
  gap. Both rubrics recover it; existing tools and current capabilities still need
  fresh research before claiming an opportunity today.
- [Denied payment over an invoice deadline](https://freelancing.stackexchange.com/questions/6966):
  v1 pain 2.85/3 was supported, but genuine 0.54 vetoed the record. Removing the
  gate ranked it second. V2 accepted it but marked pain availability unknown despite
  pain Score 2.85, leaving only workaround burden supported and pushing it down.
  Availability questions and coverage-prioritized ranking can still suppress severe
  cases. More questions are not automatically more reliable.
- [Wire-fee underpayment](https://freelancing.stackexchange.com/questions/10015):
  both rubrics reject this labeled useful record because all dimensions are marked
  unsupported. The text describes an actual payment shortfall, but our rubric does
  not reliably retain short, concrete financial-loss reports.
- [Collecting invoices for an accountant](https://freelancing.stackexchange.com/questions/10932):
  a concrete recurring manual workflow is correctly retained. V2 says
  `spending_workaround` although handing documents to an accountant does not itself
  explicitly establish paid labor. It is the only non-unknown v2 payment judgment
  in this sample and should **not** be treated as verified payment evidence.
- [Conditional lost-invoice question](https://freelancing.stackexchange.com/questions/2716):
  both rubrics retain a minor/conditional case that the engineer labels priority 1;
  v2 ranks it below the top ten. It still shows ambiguity is not fully solved.

V2 admits two lower-priority controls but only one useful lead is excluded. The
top ten still contains only ten of 22 useful leads: retention and ranking are
different problems, and interview-worthy does not mean software-solvable. Some
questions describe legal, compliance or service needs rather than product demand.

## Delivery and recommended next step

Actual definitions now live in readable files:
`problem_hunter/rubrics/production.json`, `v1.json`, and `v2.json`. The local
`questions` command formats them for reading. Custom JSON paths are supported;
incompatible IDs/types/options fail before API calls. Reports snapshot the exact
questions, weights, routing and hashes. Production question edits also invalidate
pipeline evaluation signatures; the existing production rules were not replaced.

Next, obtain human review of these examples and define v3 on development data:
retain concrete shortfall/loss evidence, avoid broad availability vetoes, and require
literal evidence before accepting payment classifications. Compare a simpler rubric
and gate-only variant on new data before adding complexity or promoting v2 into
production. Grouping, current solution research and market validation remain
separate steps; this experiment tests source-level triage only.

Local ignored artifacts: `reports/jev-benchmark-v2/reference.json`,
`comparison.json`/`.md`, `comparison-cache-check.json`/`.md`, `evaluation.db`,
`collection.db`, `candidates.json`, and `annotations.json`. Preserve these frozen
inputs to reproduce the exact test; API search results can change. The questions
and reference hashes are documented in [the pre-output protocol](jev-v2-protocol.md).
No questions or labels were tuned after reading results.
