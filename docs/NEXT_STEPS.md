# Next steps — universal pain-point research

Saved October 9, updated October 10, 2026. Product scope is universal: personal,
social, restaurant, small-business and larger-organization problems; remedies may
be products, services, process changes, events, automation or software. Invoice
experiments are development probes, not the long-term scope.

October 10: the user resumed reviews/implementation and approved a fresh
cross-domain pilot with a shared US$0.15 estimated API-cost ceiling. The ten-case
review is in `PAIN_POINT_REVIEW.md`. General-v4 is a separate opt-in prototype;
old experiment files remain frozen. The six stages below remain the work queue.

## Where we are

- Working CLI, SQLite, all three input methods, readable rubrics, reports and
  request/cost accounting. 144 tests pass; CI passes on Python 3.10 and 3.12.
- Branch: `feat/problem-hunter-mvp`; [PR #1](https://github.com/WebGrga/problemhunter/pull/1)
  is open and unmerged. Latest implementation commit: `1d1e475`.
- V3 retained 17/17 assistant-labeled useful examples versus v2's 16/17, but
  ranked them worse (nDCG@10 0.867 versus 0.952). Production remains unchanged.
- Live discovery: 82 raw results → 24 retained sources → 16 full bodies →
  seven triage-retained posts → zero recurring groups across identified users.
  A résumé and promotional/tool material reached the shortlist.
- Reference replay produced three recurring identified-author groups, but broad
  workflow families can merge different root causes. Existing-solution research
  remains partial; no current product weaknesses or buying demand were validated.
- New tests cost approximately $0.1054 total at configured list prices. Raw
  artifacts and credentials remain local and ignored.

Read `jev-v3-results.md` for evidence and limitations. Local artifacts:
`reports/end-to-end-v3/hunt.{md,json,yield.json}`, `csv.{md,json,yield.json}`,
and `reports/jev-benchmark-v3/comparison.json`. The hunt yield file describes a
cached export replay; original acquisition costs are documented separately.

## 1. Inspect failures before changing questions

Review about ten representative cases together: obvious false positives, strong
real complaints, low-ranked promising complaints, payment contradictions, and
groups that combined different root causes. Use complete stored text, not only
the generated complaint summary. Include the résumé, promotion, invoice shortfall,
customer refusal to pay, and purchase-order/accounting workflow examples.

For each, record:

- Who experiences the problem, which task they are doing, and what goes wrong.
- The literal evidence of burden, existing workaround and unresolved constraint.
- Whether the problem is relevant, first-hand and current **at publication**.
- What the expected routing and relative priority should be, and why.
- Whether the error comes from collection, statement extraction, JEV judgment,
  grounding, grouping, or ranking.

Deliverable: a small human-reviewed error log and a prioritized failure list.
Old benchmark texts may inform design now, but cannot serve as a fresh test of
the next revision. Do not edit frozen v1/v2/v3 questions or labels.

## 2. Improve acquisition and measure useful yield

Keep one narrow pilot workflow first; outgoing invoice creation, collecting
payment, and gathering incoming expense documents are different problems.
Do not generalize an invoice-specific experiment to every industry yet.

Use Brave to locate relevant discussions, then retrieve permitted original text.
Compare that with an official community API and a separately collected,
attributed CSV sample from a permitted source. CSV is an input format, not a
scraping/access permission. The previous CSV replay was not a scraper benchmark.

Collect a modest fresh pilot, initially around 40–60 complete posts across at
least two relevant communities. Preserve source/thread URLs, author identities,
dates, retrieval provenance, and licensing where supplied. Audit deduplication
before interpreting recurrence. Retain snippet-only leads separately: they must
not masquerade as complete, independently attributed complaints.

Measure acquisition cost and yield using human-reviewed relevant, first-hand
complaints—not simply the count the model accepted. Keep acquisition cost
separate from evaluation/research and distinguish original calls from cache hits.
Avoid broad paid searches when access restrictions consistently prevent useful
retrieval. Respect robots, terms, authentication and rate limits.

Deliverable: a source-quality/cost comparison and a reusable fresh evidence set.
Agree a small hard request/dollar ceiling before the next paid pilot; no new
calls are needed just to inspect the existing failures.

## 3. Fix problem representation and root-cause grouping

Represent each retained complaint with actor, affected task, failure, consequence,
current workaround, and unmet constraint, backed by exact excerpts. A sentence
such as “I lost confidence” is not a useful standalone problem description.

Separate root causes within the same workflow. For example, generating an
invoice, handling partial payments, correcting records, getting a purchase order,
and chasing late payment should not merge merely because all mention invoices.
Mark broad-family matches as tentative rather than established equivalence.

Review a small labeled set of pairs that should/should not group. Preserve
independent authors, distinct reports and repost links separately. Anonymous
posts can support a problem but cannot establish identified independent users.

Deliverable: clearer evidence-backed titles and a grouping test set, with no
obvious unrelated-root-cause merges in the reviewed examples.

## 4. Design and test v4 without overstating payment intent

Only after Steps 1–3 identify the actual errors, copy v3 into a new readable v4
file and freeze the question/routing changes before testing unseen records.

Candidate improvements to investigate, not assumed wins:

- Ask about the affected workflow explicitly so job-seeking, provider promotion,
  hypothetical needs and ordinary activity do not become experienced complaints.
- Distinguish meaningful frustration, concrete operational burden and serious
  loss; do not require a quantified dollar amount to retain a good lead.
- Count replacement action only when it concerns a remedy for this problem,
  not an unrelated action such as seeking employment.
- Revisit whether every primary record should outrank every review record.
  An unsupported payment classification should not automatically bury an
  otherwise severe, well-supported complaint. Keep the review flag visible.
- Keep actual remedy spending, stated buying intent, refusal, and unknown
  separate. Frustration is a potential research signal, not observed willingness
  to pay. If reporting inferred commercial promise, label it as inference and
  keep it separate from direct payment evidence.

Use a separate fresh, preferably human-reviewed holdout. Compare v4 against v2,
v3 and a simple baseline on exactly the same texts. Track useful retention,
off-topic admissions, top-ten quality, graded ranking, review load and cost.
Look at error examples as well as aggregate metrics. Small samples do not
establish general accuracy or market demand; report uncertainty and limitations.

Deliverable: a versioned experiment with snapshots, raw answers, costs and a
clear keep/reject decision. No automatic production promotion after tests pass.

## 5. Make solution research useful and bounded

Research a few reviewed problem groups whose affected workflow is clear.
Skip vague titles and avoid sending entire unrelated pages repeatedly.

Prefer direct product/service documentation and public pricing for functionality;
use independently attributed customer discussions for experienced weaknesses.
Check that an offering performs the actual task, not merely that it shares
industry words. Distinguish quoted provider claims from verified behavior and
current pricing. Keep unavailable information explicitly unknown.

Propose a specific improvement hypothesis for each group: which manual step or
unmet constraint it addresses, why current workarounds may fail, and what evidence
would disprove the idea. Do not present a generic “automate it” sentence as research.

If structural extraction or group synthesis remains the bottleneck, test an
optional stronger model only on a small shortlist. Compare incremental report
quality and cost with the JEV-only path before expanding it. Do not send every
raw post to a reasoning model or add repeated JEV calls without a measured benefit.

Deliverable: a few traceable opportunity briefs with actual relevant alternatives,
honest unknowns, a specific proposed fix, and a concrete validation question.

## 6. Run a fresh end-to-end pilot and set a stop/go decision

Run the revised collection → extraction → evaluation → grouping → research →
report pipeline with a fixed budget. Inspect the shortlist manually. At minimum,
the small reviewed shortlist should contain no obvious résumé/promotion-only
false positives, no clear unrelated-root-cause merges, and no unsupported payment
claims. Treat these as review criteria, not claims that automated accuracy is 100%.

A useful next deliverable is a handful of genuinely investigable problem briefs,
not a report filled to an arbitrary top-20 quota. Each should explain the affected
customer, concrete failure, supporting independent reports, existing remedies,
missing evidence, and the next interview or workflow observation to perform.

If acquisition still provides insufficient evidence, improve or change the
permitted source/workflow before tuning scores again. If the briefs are useful,
move to customer validation: confirm present-day recurrence, actual losses,
existing budgets and what users would change or buy. Do not contact anyone or
claim commercial validation automatically.

## Tomorrow's first working session

1. Open the live hunt and reference/CSV reports with their underlying source text.
2. Review ten cases and write the error log together.
3. Choose one precise workflow and the fresh-source collection plan.
4. Implement the highest-impact collection/representation fix with regression
   tests, then plan the budgeted fresh v4 experiment.

No dashboard, browser extension, large-scale crawl, automatic PR merge, extra
model provider setup or large paid run is needed at this stage.
