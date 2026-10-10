# Usefulness repairs and live verification — October 10, 2026

## Outcome

The known positive-review, buyer/seller and interview-feedback mistakes are rejected
in the revised diagnostic replay. Maker accounts with actual experience remain,
with their existing remedies and resolved status visible. The feedback landscape
now contains five remedies with 25 selected source claims, rather than the original
SurveySparrow record with no established facts. This is a useful extraction and
presentation improvement, not proof of general accuracy or an unsolved opportunity.

New collection still yields predominantly discussion snippets. All 20 retained
groups in the five new source samples require review; none is a primary candidate.
The broader discovery problem is therefore **not solved**. Do not promote this
experimental routing to production or read its priorities as probabilities.

## Changes tied to observed failures

- Collection accepts `--since`, `--until` and `--discussions`. Date filters reach
  both Brave and HN; discussion preference reduces vendor-guide emphasis but does
  not guarantee accessible bodies or relevant actors.
- Extraction chooses the larger main body over small recommendation cards, keeps
  original publication, modification and search dates separately, and prioritizes
  original publication when dates conflict. JSON-LD publication dates are read.
  Extracted bodies under 300 characters remain fragments; API-supplied short HN
  comments retain their original full-comment provenance. Length alone does not
  prove completeness; `body_candidate` is deliberately not a quality guarantee.
- Opt-in `general-v5` reviews the selected failure against the requested actor and
  task. Adjacent matches are excluded. Source-selected actor, task, consequence,
  existing remedy and remaining-constraint excerpts are preserved. Resolved and
  retrospective accounts cannot present a former constraint as established current
  unmet need. Other commenters' suggestions do not become a verified workaround.
  Primary candidates rank before review-required material. General-v4 and production
  definitions are unchanged.
- Research follows up to four reviewed `known_remedies` first, preferring matching
  provider domains. It selects up to three identities per page, then gathers
  evidence for each fixed identity across bounded contextual spans. A separate
  call checks the actual selected quotes for their subject and actual task/constraint
  fit. Empty comparison candidates are omitted; their raw identity judgments remain
  in the saved source records. A partial task match cannot establish full constraint
  satisfaction. No closest remedy or product trial is invented when fit is unknown.

The JEV representation/selection fingerprints and raw responses are persisted.
The representation-question hash is part of evaluation identity so changed review
instructions do not silently reuse an old evaluation signature.

## Diagnostic replay versus new sources

Nine previously inspected sources were replayed as **diagnostics**, not holdout:
one scheduling review, one buyer returns comment, four education accounts and three
freelance accounts. The final replay retains four, all requiring review. Both
freelance maker accounts are marked resolved at publication; two education accounts
remain as retrospective/resolved context. Three obvious wrong candidates are
excluded, along with two weak teacher-founder/quoted-experience accounts.

The first revision still admitted the buyer complaint and wrongly inferred that
Agentation satisfied the compound constraint from its free/open-source claim. Those
results prompted further routing and quote-assessment repairs. Intermediate outputs
were preserved, not presented as successful verification. Replayed material after
inspection is diagnostic material, even when originally newly collected.

| New source sample | New URLs collected | Full bodies/comments | Final retained | Primary candidates |
| --- | ---: | ---: | ---: | ---: |
| Restaurant shift changes | 11 | 1 | 2 | 0 |
| Client website bug feedback | 12 | 2 | 2 | 0 |
| Family caregiving coordination | 12 | 0 | 8 | 0 |
| Contractor change-order approval | 8 | 0 | 2 | 0 |
| Online seller returns/refunds | 8 | 0 | 6 | 0 |
| **Total** | **51** | **3** | **20** | **0** |

All previous pilot URLs were excluded before evaluation. The first three samples
were inspected and then replayed after the routing repair; the final two were new
to that revised routing. Queries and source limits were fixed before collection.
No synthetic data was used in these live probes. Assistant reviews happened after
scores for these samples, so they do not supply independent/blind accuracy metrics.
Provider filters cover January 2025–October 10, 2026; search timestamps alone remain
unverified publication evidence.

Some leads are specific: a seller reports receiving an unpacked, damaged return and
being denied reimbursement; a subcontractor describes resistance to justified change
orders; caregivers describe relatives not helping with responsibilities. These are
investigable leads, not verified current experiences or established independent
recurrence. Significant mistakes remain: a movie-theater shift-swap thread enters
the restaurant sample, and a buyer complaint appears within a seller-oriented
thread. Both require review, but that does not make them useful in-scope evidence.

## Freelance feedback comparison

This was a reviewed **diagnostic** problem from the original run. The brief names
FasterFixes, Marker.io, BugHerd and Agentation because the original complaint names
them. New searches/retrieval investigated those existing remedies and a process
alternative. The task is contextual client website feedback for coding agents;
the constraint combines open source, client access through a shared link without
an extension, and retrieval of technical context through MCP.

The final report retains FasterFixes, Marker.io, BugHerd, Agentation and MarkUp.io.
The first four have partial task fit; MarkUp.io's fit remains unknown. There are 25
selected function/pricing/setup/limitations/constraint claims, with citations and
model provenance. Customer complaints and adoption remain unestablished. Overall
disposition is still insufficient information, with FasterFixes the closest partial
match to investigate. Partial evidence must not become "all requirements satisfied."

Manual checks separately confirmed that
[FasterFixes](https://www.faster-fixes.com/) describes an open-source website widget,
client annotations and technical context delivered through MCP, with a free plan.
These are provider claims, not observed product behavior. Its own maker account
already describes implementing that remedy; building a new generic feedback tool
is not justified by this evidence. A concrete next check is whether real nontechnical
clients can use the shared review link and whether a coding agent retrieves enough
context to reproduce an actual reported issue.

[Marker.io's official pricing page](https://marker.io/pricing) describes screenshot
annotations, environment details and widget installation. Pricing context matters:
the page displays $39/month billed annually and $59/month alongside it. The model's
selected "starts at $39" quote omits that billing context; the report is a source
claim requiring plan review, not a verified all-in price. Similarly,
[BugHerd's pricing page](https://bugherd.com/pricing) supplies contextual website
feedback and plan information, but this run does not establish open-source/MCP fit.
Agentation information comes from a dated third-party review, not current official
documentation; independence and current applicability remain unverified.

The original and revised comparison use different query plans, explicit remedy
seeds and constraint wording. The 0-to-25 claim change is an observed report-quality
comparison, not a controlled model-accuracy benchmark. A stronger extraction count
does not itself establish correct interpretation. In particular, multi-product
page headings can mention one tool while describing an alternative; the final
subject check removed two such misattributed function claims in this run.

## Verification, cost and next priority

195 local tests pass. New tests exercise publication/search conflicts, incomplete
cards, main-body selection, pre-request date validation, actor/task exclusion,
speaker-linked workarounds, late pricing, multiple fixed subjects and the rule that
partial task fit cannot establish full satisfaction. Mock tests check behavior,
not semantic accuracy. Live artifacts are local under
`reports/fresh-e2e-2026-10-10/improvement*/`; the final comparison is
`improvement-revised/feedback-comparison-final.md` and `.json`.

Cumulative estimated application API spend, including the initial eight-field test
and all development probes: **$0.325502696 against the same approved $1 cap**.
Increment after the initial $0.199462758 test: **$0.126039938**. Remaining cap:
**$0.674497304**. Every retry reused the shared ledger; none reset the budget.
Manual browser spot checks are separate from that application's provider ledger.

The next priority is obtaining permitted, complete original experiences, rather
than increasing the number of snippets or adding more scoring questions. The
current HN source is readable but often poorly matched to nontechnical fields;
Reddit-oriented discovery finds richer leads but often cannot retrieve their
original bodies. A source/workflow should demonstrate useful complete-body yield
before a larger collection run. Keep the comparison improvements, and require
manual review of its cited facts and exact remaining constraint.
