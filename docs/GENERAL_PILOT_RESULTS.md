# Universal pain-point pilot — October 10, 2026

## Purpose and scope

Problem Hunter is a universal researcher of experienced friction and unmet needs,
not a software-idea generator limited to invoicing. Social/emotional problems,
physical-product opportunities, services and process improvements belong in scope.
The ten-case development review is in `PAIN_POINT_REVIEW.md`.

The new `general-v4.json` is opt-in. Its research scope comes from the user at
runtime; no invoice family or finance-only category is applied. Twelve questions
include three exact passage selections. More questions are justified here by
traceability, not an assumption that more calls mean better reasoning. All twelve
are sent together in one official JEV request per source. Definitions remain
readable, and actual rendered questions/selections are preserved in evidence.

The universal parser verifies literal passage membership and response structure,
not semantic truth. Explicit model-selected payment candidates remain visible,
but are not verified spending and do not automatically earn commercial payment
points. Practical/social/emotional impact can support research priority without
money-loss wording. Review flags do not automatically sink severe candidates.

## Live pilot

The user approved a shared $0.15 estimated cost ceiling. Three domains used one
Brave query, one HN query and one supplementary public Stack Exchange API query
each. Up to three sources per provider/domain were retained without outcome-based
selection. Permitted page extraction was attempted for snippets; restrictions
were not bypassed. Original HTML/licensing was retained for public API posts.

| Domain | Retained sources | Full bodies | Triage-retained candidates | Identified-user recurring groups |
|---|---:|---:|---:|---:|
| Restaurants/food service | 9 | 7 | 5 | 0 |
| Workplace coordination | 9 | 8 | 6 | 0 |
| Meeting people/social participation | 8 | 8 | 5 | 0 |

These are model-retained candidates, not independently judged useful positives.
Twenty-six sources produced sixteen separate candidate groups. This is a small
qualitative/integration pilot, not an accuracy benchmark or a prevalence estimate.
Newly collected historical posts do not establish current need. Workplace source
membership does not establish company size; larger businesses need direct sampling.
The home-cooking result below illustrates an adjacent-scope admission.

Total estimated cost including the interrupted run: **$0.019601898** (about
1.96 US cents), comprising Brave $0.015 and JEV $0.004601898. There were 51 network
attempts: three Brave, three HN, three Stack Exchange, eleven web and thirty-one
JEV. Public collection calls have no configured per-request provider fee. JEV
reported 109,569 input tokens across all calls. Estimates use configured list
rates, not provider invoices or free-credit accounting.

## What became more useful

The following are concrete leads, not recommendations to build or buy:

### Meeting overruns

[A daily stand-up complaint](https://workplace.stackexchange.com/questions/465/how-can-i-encourage-our-team-to-have-shorter-stand-up-meetings)
describes meetings scheduled for twenty minutes lasting thirty to forty, a short
individual contribution, and attempts to discuss the issue or leave. The selected
impact retains the wasted-time context rather than merely “I attend meetings.”

**Possible directions, hypotheses:** a meeting-facilitation service, team process
redesign, or lightweight async updates. A new app is not automatically needed.
**Unknowns:** present-day recurrence, decision maker, organizational constraints,
existing policies and willingness to change/pay. **Next check:** observe one
current team's meetings and ask which coordination needs actually require everyone.
The original post is from 2012 and is only one identified account.

### Privacy in small living spaces

[A video-call privacy complaint](https://workplace.stackexchange.com/questions/167478/dealing-with-coworker-who-requests-video-on-zoom)
describes a small studio, unwanted background visibility and a virtual background
that fails when the speaker moves. The person considers a physical divider.

**Possible directions, hypotheses:** a compact physical privacy product, setup
assistance, or camera-consent/process guidance—not necessarily another video app.
**Unknowns:** current frequency, space/storage constraints, existing remedies and
actual purchase intent. Considering a divider is not explicit willingness to pay;
JEV's payment-passage/unknown-signal disagreement remains a review caution.
**Next check:** inspect current setups with consenting adult users and ask what
they have tried or bought. The original account is from 2020.

### Restaurant scheduling constraints

[Kitchen scheduling friction](https://www.reddit.com/r/restaurant/comments/1o0x32u/whats_the_best_solution_to_automate_kitchen_staff/)
and [employee availability constraints](https://www.reddit.com/r/Restaurant_Managers/comments/1ex0qqd/on_a_scale_of_110_for_frustrating_do_you_find/)
suggest last-minute changes, conflicting preferences and back-and-forth messages.

**Possible directions, hypotheses:** an availability-collection process or
scheduling service before assuming a new automated scheduler is necessary.
**Important limitation:** only mixed search snippets were available. One selected
workaround was a builder's product pitch, not clearly the complainant's own action.
These are discovery leads, not two established independent complainants.
**Next check:** obtain permitted complete first-hand accounts and identify the
specific last-minute constraint that existing scheduling tools fail to handle.

### Social participation is retained, not excluded for lacking payment

[An HN discussion of approaching strangers](https://news.ycombinator.com/item?id=26945075)
contains an account of awkwardness during attempts to connect. Other social
results concern being disregarded, declining offered help and uncomfortable
friendship interactions. They are real research themes even when no commercial
spending is stated; they are not automatically a common “make friends app” problem.

**Possible direction, hypothesis:** small, recurring, interest-based adult social
activities with an easier introduction process. **Next check:** identify a specific
adult population, its unsuccessful attempts and why current activities do not fit.
Do not assume an interpersonal advice request is product-addressable.

## Remaining failures and boundaries

- The highest-priority social result was a published anonymous advice letter
  involving a minor and distress. It is not a verified independent complainant
  or an appropriate automatic commercial-target lead. No diagnosis, clinical
  remedy, contact, targeting or purchase prediction follows from its score.
- Some passages still select a coping action rather than the root failure, or
  hypothetical intentions rather than an attempted workaround.
- A home-cooking recipe failure entered the restaurant sample as an adjacent
  consumer problem. Restaurant-operator evidence needs better collection filters.
- Snippets can blend speakers. We now prevent them from establishing identified
  complainants, but their workaround/impact interpretations remain tentative.
- Conservative lexical grouping left all candidates separate. It avoids forced
  invoice-family merges, but does not prove that recurring problems are absent.
- No automated solution research was purchased for these unreviewed workflows.
  Current prices, product shortcomings, implementation feasibility, customer
  reachability and buying demand remain unverified.

## Engineering fixes and verification

The first pilot exposed a scope-isolation bug: importing a different topic caused
prior corpus inputs to be evaluated under the new scope. Current inputs are now
evaluated separately; grouping still uses the accumulated corpus. Five unnecessary
JEV calls before the interruption are included in total cost, not hidden as useful
evaluation. Failed batches did not mark sources successfully evaluated.

A live Choice answer reported p0 with probability .34 while p1 had .35. Universal
parsing now preserves the reported choice with a consistency-review flag for a
small discrepancy; material mismatches and malformed distributions still fail.
This is response handling, not a rewritten model answer or confidence-as-proof.
Resumption subtracted previous spending/attempts from the same approved ceiling.

158 tests pass locally, including cross-domain mocked contracts, exact selections,
scope isolation, snippets/attribution, payment candidates, error handling, ranking
and earlier functionality. Fixture tests prove mechanisms, not live accuracy.
Old rubric/question and evidence-rule files are unchanged.

Raw local artifacts: `reports/general-pilot/protocol.json`, `*-inputs.json`,
`summary.json`, `opportunities.{md,json}` and `pilot.db`. They are ignored by Git.

```sh
python main.py hunt --topic 'meeting people and making friends' \
  --evaluation-rubric general-v4 --queries 6 --max-sources 24 --audit-yield
python main.py import-csv collected.csv --scope 'restaurant operations' \
  --evaluation-rubric general-v4 --audit-yield
python -m problem_hunter.benchmark questions --rubric general-v4
```

The scope can be any theme; these examples are not a fixed sector catalog.
`scripts/run_general_pilot.py` reproduces the bounded collection/integration
procedure. A cached replay is not new acquisition or an independent test.

## Next decision

This is now producing more interpretable cross-domain leads, but not yet reliable
recurring-opportunity research. Next: human-review a few briefs, refine collection
for the actual affected population, annotate speaker/root-cause boundaries and
construct a fresh multi-domain grouping/ranking holdout. Use small development
sets and a separate human-reviewed holdout; do not tune frozen v4 against these
outputs and then claim improved accuracy on the same examples.

Keep universal triage opt-in until that evidence exists. Do not scale searches,
add blanket reasoning-model calls or treat the remaining budget as a spending goal.
