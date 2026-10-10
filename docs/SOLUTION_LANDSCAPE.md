# Solution-landscape research

Brief-based `research` compares named remedies rather than treating search-result
titles as product identities. The current v2 implementation is described under
**October 10 usefulness repairs** below. It uses separate identity, fixed-subject
evidence and quote-assessment calls. The original v1 description below is retained
for history; it is not the current request budget or validation claim.

## Reading the comparison

- Names are selected from bounded literal body-text spans. Article titles remain
  source titles. Software, services, physical products, named practices and
  community approaches use the same representation.
- Function, pricing, limits, setup, customer complaints, adoption and constraint
  fit retain exact excerpts and the source URL, retrieval/publication dates,
  author where supplied, metadata and model-inferred source role. Quotes must
  explicitly name the selected remedy; detached competitor claims are excluded.
- Provider and third-party evidence stay separately attributed. Customer
  complaints require a model-selected customer role and literal first-person
  language. This is an attribution check, not independently established truth.
- Provider sources consolidate only by the same normalized name, remedy type
  and hostname. Third-party sources attach only when exactly one matching
  provider candidate exists. Conflicting provider-domain identities remain
  separate; same-name grouping is still a candidate identity requiring review.
- Public prices preserve plan, currency, units and dates as quoted. They are
  source claims; current applicability, regional availability, taxes and behavior
  remain unverified. Setup and switching costs remain unknown unless described.
- Adoption distinguishes provider-claimed usage, independently reported usage,
  review counts and downloads. Review/download counts are proxies, not active
  users. Every adoption excerpt needs a literal numeric count, matching metric
  and appropriate model-classified provenance. No market share is calculated.

## Research dispositions

`apparently_well_served` requires an explicit same-task function claim and an
excerpt the model interprets as satisfying the precise remaining constraint.
`plausible_residual_gap` requires a same-task claim plus a literal limitation the
model connects to that constraint. `insufficient_information` covers missing
constraint evidence, absent named remedies and conflicting satisfaction/blocker
claims about the same candidate. These are research inferences, not viability
predictions. Unsearched alternatives may solve an apparent residual gap.

The report identifies the closest source-supported candidate, cites its function
and constraint evidence, preserves the exact constraint to check, notes whether
a non-build remedy may suffice, and recommends a contextual trial. Missing buying
demand or identified recurrence does not gate this comparison.

Changing the brief clears old comparison data. If later grouping changes the
supporting problem IDs, old landscape results are invalidated and the saved brief
is marked for review. Standalone research does not reevaluate or regroup evidence.
Old databases load the new optional field without a schema migration.

## Verification and practical limits

186 local tests pass. New mocked examples use fictitious remedies for restaurant
scheduling, shorter workplace stand-ups and small-home video-call privacy. Tests
cover consolidation, pricing/customer provenance, review-count handling,
nonsoftware remedies, residual constraints, ambiguous identity, contradictory
evidence, malformed responses, snippets, missing keys and brief invalidation.
These tests demonstrate implementation behavior, not semantic accuracy or actual
offering quality. No fresh paid API calls were made for this development milestone.

The search remains deliberately bounded and incomplete: one named remedy per
page, six distinct pages, up to 16,000 body characters, 64 name candidates and
48 sentence candidates per page. Names outside the span patterns or excerpts
using pronouns instead of explicit remedy names can be missed. Redirected/subdomain
provider identities and aliases are not automatically reconciled. Source roles,
same-task fit and constraint interpretations require review. Exact quotes establish
literal presence, not factual correctness. Without JEV, retrieved pages remain
unverified candidates and the comparison says insufficient information.

Next development priority: targeted source follow-up per named candidate, more
complete alias/provider identity handling, and a reviewed cached/live pilot under
the existing shared cost accounting. Do not reset the approved pilot budget.
# October 10 usefulness repairs

Brief-based research now uses `solution-landscape-v2`: identity selection (up to
three names per page), fixed-subject evidence selection, then assessment of the
actual selected quotes. Claims with unestablished subject attribution are removed.
Quotes may use a provider's "we"/plan wording only with a literal named subject
anchor on a model-classified single-remedy provider page; classification remains
an inference. Known remedies from a reviewed brief are searched first, preferring
matching provider domains. Contextual spans extend across a bounded 24,000-character
body rather than only the first 48 sentences. Every call and quote remains saved.

Partial task fit is separate from complete task fit and cannot establish that the
constraint is satisfied. A compound constraint requires all parts, and no closest
remedy is invented when fit remains unknown. Explicit brief names are not verified
identities by themselves. Six pages remain the default bound; named follow-up is
bounded to ten. More requests per page mean the cost ceiling matters.

Legacy v1 evidence parser/tests remain available for regression comparison. The
historical description below refers to that first implementation. See the fresh
usefulness reviews for live results; passing mock tests do not establish accuracy.
