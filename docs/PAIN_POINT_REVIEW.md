# Pain-point review — October 10, 2026

Goal: a universal researcher of experienced problems across personal life,
restaurants, small businesses and larger organizations. Solutions may be services,
physical products, events, process changes, automation or apps. Invoicing was a
test domain, not the product's scope. A painful problem is worth investigating
even when the post says nothing about paying for a remedy.

This review uses stored source text and actual v3 outputs, not new model calls.
The expected behavior below is the Commander's assistant judgment; it is not an
independent human label, calibrated accuracy result or market-demand validation.
Frozen v3 questions, literal rules and benchmark labels remain unchanged.

## Ten representative cases

### 1. A resume was retained as a problem

[HN hiring-thread comment](https://news.ycombinator.com/item?id=48036716)
describes past engineering achievements and a side project. V3 selected
“Looking for: Senior/Staff Backend or Full-Stack Rails roles.” It gave pain zero,
but retained the post as an experienced workaround and primary candidate.

**Error:** classification, excerpt selection and dimension support. Seeking a
job here is not seeking a fix for invoicing pain. Building a product is not by
itself evidence of a burden. A genuine job-search difficulty could be a valid
personal/work problem, but this resume does not describe one.

**Expected:** do not retain an experienced problem without an actual negative
impact passage. No universal keyword ban on employment topics.

### 2. Financial harm was summarized as a vague emotion

[Delayed payment through an undisclosed intermediary](https://freelancing.stackexchange.com/questions/6656/how-to-deal-with-non-respect-of-payment-terms)
describes contractual payment delays and a newly discovered intermediary. The
selected statement and literal-loss field were “I just lost any confidence with
them.” Generic finance/pricing products then appeared in solution research.

**Error:** a keyword match on “lost” does not establish monetary loss. The emotion
is real, but its cause—the payment chain and delayed terms—is the useful context.

**Expected:** preserve the specific failure and its consequences. Emotional and
financial impacts should be distinguishable; relevant remedies need to address
payment terms/intermediary risk, not generic financial software.

### 3. A conditional ledger problem became actual loss

[Second-installment invoice conflict](https://freelancing.stackexchange.com/questions/10816/client-asking-for-new-invoice-for-2nd-installment)
describes incompatible accounting systems preventing the second installment's
processing. A conditional sentence about a replacement invoice appearing unpaid
was saved as literal loss.

**Error:** grounding confuses a projected ledger consequence with observed loss.
The real experienced incompatibility still matters; rejecting the whole complaint
because one consequence is conditional would also be wrong.

**Expected:** retain the workflow failure, label the conditional consequence and
do not invent an amount or realized financial harm.

### 4. Anxiety, pricing and payment tracking merged

The live hunt's invoice-generation group joined:

- [Pricing/service-description uncertainty](https://www.reddit.com/r/Entrepreneur/comments/1psw66y/how_do_you_create_your_invoices_as_a_freelancer/).
- [Anxiety about requesting payment](https://www.reddit.com/r/freelance/comments/2na2qw/how_do_you_deal_with_your_reluctance_to_send_out/).
- [Frustrating spreadsheet payment tracking](https://www.reddit.com/r/freelancing/comments/1suc7pz/do_you_struggle_with_invoices_contracts_and/).

**Error:** shared invoice vocabulary is not root-cause equivalence. These may
suggest pricing guidance, social/emotional support, and tracking/process tools
respectively—not one invoice generator.

**Expected:** separate the unmet goal/constraint. All three were snippets mixing
thread and reply text, so authorship and independent complainant counts were not
established. Full access was unavailable; no access restriction should be bypassed.

### 5. Two unrelated accounting failures merged

[Accountant blocks invoice issuance without a purchase order](https://money.stackexchange.com/questions/107694/accountant-wont-send-an-invoice-without-a-po)
was grouped with [netting bills and invoices in a bank transfer](https://money.stackexchange.com/questions/135722/combine-bill-and-invoice-in-a-single-transaction)
under incoming-invoice document collection.

**Error:** the first is an approval/purchase-order bottleneck; the second is
ledger allocation/reconciliation. Neither establishes that its root problem is
collecting incoming expense documents. The family rules forced a wrong merge.

**Expected:** retain separate workflow constraints. A group with two sources
should not be sold as recurring demand when the sources describe different causes.

### 6. Payment interpretation lowered a valid complaint's rank

[Agency requires umbrella-company invoicing](https://freelancing.stackexchange.com/questions/6861/company-want-me-to-invoice-them-through-an-umbrella-company-and-not-directly-h)
describes withheld payment and a disputed intermediary fee. JEV selected payment
refusal without a matching remedy-refusal rule; the record moved to review.

**Partly successful:** the contradictory payment interpretation remained visible
and did not become a claimed buyer. **Remaining error:** putting every review
candidate below every primary candidate can bury strong experienced harm beneath
an irrelevant resume.

**Expected:** separate pain-investigation priority from payment evidence review.
Neither a customer refusing an invoice nor unwillingness to use one particular
intermediary predicts whether someone would buy another remedy.

### 7. Ordinary setup obscured a specific operational problem

[Prepaid customer balance in GnuCash](https://money.stackexchange.com/questions/93872/invoices-less-payments-in-gnucash)
was summarized as the desired deduction of a prepaid balance. The body explains
that the printed invoice still shows the original total after payments.

**Error:** statement extraction selected intended activity rather than what
actually fails. Money amounts illustrate accounting balances, not remedy spending.

**Expected:** a concrete problem brief about incorrect remaining-balance display,
with product/version behavior and current resolution status still to verify.

### 8. A short question became an uninformative title

[Removing an erroneous GnuCash invoice](https://money.stackexchange.com/questions/162446/gnucash-delete-or-invalidate-invoice)
was summarized as “How can I invalidate or remove it?” The source's title and
preceding context identify the erroneous invoice and small-business setting.

**Error:** a literal excerpt can be faithful but unusable without its referent.

**Expected:** include original context and the actual selected failure passage.
Do not fabricate a severe impact merely to make the opportunity sound stronger.

### 9. A resolved workaround is useful evidence, not current demand

[HN self-hosted invoicing project](https://news.ycombinator.com/item?id=47749457)
describes annoyance with a subscription fee and a tool built to avoid it. V3
selected an unrelated starter-framework sentence as the problem statement.

**Error:** excerpt selection loses the actual motive. A maker's account is not
automatically invalid promotion, but historical workaround effort does not prove
unmet current need or a future paid buyer.

**Expected:** preserve the fee/alternative preference and resolved status. It may
help map alternatives or willingness constraints; do not infer broad demand from
the maker's claim that others probably want it too.

### 10. A mixed advice/account was treated too coarsely

[Billing-service website critique](https://news.ycombinator.com/item?id=2139905)
contains advice but also a first-hand account of trying to assess a billing
provider and finding its target market/functionality unclear.

**Error:** whole-post promotion/advice labels can hide an experienced passage.
Conversely, time spent researching is not automatically time lost.

**Expected:** identify the specific evaluation/discoverability friction, keep its
historical date/status, and distinguish normal research effort from avoidable
confusion. This could suggest a communication/service opportunity, not only an app.

## What these cases justify changing

1. Scope must be runtime data, not invoice wording or a forced finance category.
2. Select exact experienced-failure passages; keep title/context to avoid vague
   “it”, ordinary activity and resume fragments.
3. Treat practical, social and emotional burden as valid research evidence.
   Monetary loss is neither a prerequisite nor a synonym for negative emotion.
4. Keep payment candidates, payment verification and pain priority separate.
5. Do not attribute blended snippets to a named thread owner or force broad
   vocabulary families into claims of independent recurrence.
6. Require a reviewed workflow before spending on solution research.

`general-v4.json` and the opt-in universal evaluator implement the first four
mechanisms and avoid the invoice family rules. Conservative lexical grouping is
still not validated semantic equivalence. Exact source selection verifies literal
presence, not the model's interpretation. These changes need cross-domain evidence
review; fixture tests alone do not prove better research quality.
