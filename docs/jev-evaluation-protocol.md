# JEV rubric comparison: frozen evaluation protocol

## Objective

Test whether concrete Score questions rank invoice-administration complaints more
usefully than the current production rubric, without adding a reasoning model to
each record. This is a test of **investigation priority**, not market viability,
predicted willingness to pay, or commercial validation.

## Reference records and review

Collect 30–50 complete, attributed public comments about freelancer or small-business
invoice administration, including invoice issuance, customer payment collection and
incoming expense-invoice gathering for accountants. General bookkeeping and time
tracking without a specific invoice burden are adjacent. Include concrete burdens,
minor grievances, advice, resolved experiences,
promotional material and irrelevant keyword matches. Retain the complete comment,
original URL, source, date, author and collection query. Do not fabricate examples
or treat combined search snippets as attributed comments. Long comments can be
excluded by a documented length limit, but retained text must not be truncated.

This is a purposively selected test set, not a representative market sample. Its
label proportions cannot estimate demand or population prevalence. Hacker News
is convenient for accessible full text but has a substantial technical-audience
bias; conclusions need replication in actual customer communities.

An assistant engineer reviews records before seeing model outputs and assigns:

- Relevance: relevant invoice workflow, adjacent context, or irrelevant.
- Investigation priority 0: promotion, nonproblem, irrelevant, or a satisfied
  low-burden workflow with no experienced problem.
- Priority 1: minor/vague grievance or informational statement.
- Priority 2: concrete experienced burden that warrants an interview.
- Priority 3: consequential recurring workflow with supporting behaviors such as
  workarounds, attempts to change, or spending.

Each annotation includes a reason and a literal excerpt where applicable. These
are **assistant-engineer judgments**, not independent human ground truth. A
separate human review is required before treating agreement as calibrated accuracy.
The Commander reviews the selections and label reasons before the live comparison.

Historical costly workarounds, buying behavior, and concrete past losses may be
interview-worthy evidence. They must not be rejected merely because the speaker
found a workaround. Annotate ongoing/historical/satisfied/advice/promotion status
separately. Historical evidence does not establish unmet need today; this comparison
judges whether the account is useful to investigate, not whether its author is a
currently dissatisfied prospective buyer.

Assign a deterministic, stratified development/holdout split before evaluation.
Freeze the reference file and rubric hashes in the output. Do not change labels or
rubric after viewing holdout results. Any later revision requires a new version and
fresh holdout examples.

## Comparisons

Baseline: the current production Evaluator followed by singleton grouping and
opportunity scoring on the same full comments. Rejected records remain in the
comparison with zero priority. This isolates rubric/scoring changes; it does not
benchmark discovery or semantic grouping, and singleton recurrence is not market
frequency. Production author attribution is available equally to both approaches.

Revised rubric, version 1:

- Noul: genuine experienced problem and first-hand report.
- Choice: invoice-workflow relevance and report kind.
- Score: pain severity, workaround burden and motivation to replace, with concrete
  ordered descriptions and a separate known/unknown Choice for each dimension.
- Choice: payment evidence type, explicitly distinguishing unknown from refusal,
  spending on workarounds, explicit buying intent and paid solutions.

Ask all revised questions together against one comment per state. Independent
documents remain isolated. Unknown dimensions are excluded from the weighted
mean; coverage is reported separately. Pain, workaround burden and replacement
motivation have weights 45, 35 and 20. Supported normalized Scores determine a
0–100 investigation-priority index; it is not a probability or validated opportunity
score. Require direct relevance, an experienced-problem classification and genuine
  probability >=0.6 for ranked candidates. Experienced accounts can include
  concrete historical workflow burdens and costly workarounds; general advice and
  ungrounded hypothetical needs do not qualify. Candidates supported on at least two
dimensions rank before those supported on one. Exact ties use stable record IDs.

Payment evidence is displayed separately. Frustration can support investigation
but does not become proof of future purchase. Unknown payment evidence must not
be represented as a refusal to pay.

## Evaluation and resources

Report precision@10, useful recall@10 and nDCG@10 against the frozen annotations,
for all records and the holdout separately. Define useful as priority >=2 and
directly relevant. Retain both top-ten lists, false positives and missed useful
records, dimension-level Scores, confidence, raw responses and source links.

Use cached requests, a bounded request ceiling and explicit JEV price assumptions.
Record token usage and estimated cost. No reasoning-model calls are necessary for
this experiment. A fair cost comparison must separate model evaluation from source
collection and must not count cached responses as new paid requests.

Interpret improvements as preliminary agreement with this reviewer on this sample.
Inspect errors and coverage before recommending production adoption. Software
tests establish implementation correctness, not model quality.
