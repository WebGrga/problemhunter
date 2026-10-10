# V3: simpler questions, grounded evidence, fresh holdout

Recorded before viewing new holdout outputs. V3 questions were frozen before the
Commander saw the new texts. Another assistant engineer labeled the new records
without reading v2/v3 questions or prior JEV results; not human ground truth.

Frozen v3 question file SHA256:
`cf7023e53e970ee84111c6bef7dee75bc2e30c7098d904c13a325fbfa4d01a1c`.
Frozen reference SHA256:
`48e817f8abdb8eb2cb5140131769359f3c81ff4b7b243b27bbb1b666ee60644b`.
Literal evidence rules version `literal-v1`, initial file SHA256:
`1f52f6846a4727c4db66c0cd391342ecd330cbb539005d23f0775019d9cc6fb3`.

Eight typed questions replace v2's eleven: first-hand, relevance, contained
evidence, pain, workaround burden, replacement action, publication-time need
status, and payment evidence. No separate availability questions. Pain includes
short explicit underpayments/missing records; model severity remains inference.
Code retains a supported pain dimension for an experienced account, supports the
other dimensions only when literal keyword-selected passages exist, and excludes
unknown dimensions from the mean. Coverage does not suppress one-dimension leads.

Clear irrelevance/nonproblem/promotion is excluded. Literal experienced loss
conflicting with nonproblem or low pain goes to review. Non-unknown payment
classifications require a literal sentence meeting conservative remedy-payment
rules; otherwise payment becomes unknown and the conflict is flagged. Literal
presence and rule matches are not semantic ground truth or willingness forecasts.
Primary candidates rank before review, then priority score and stable ID. Model
confidence never becomes observed demand; all contradictions remain inspectable.

Compare on the same 40 unseen complete records:

- Experimental v2.
- V1 with only genuine cutoff removed, otherwise unchanged question/scoring gates.
- Eight-question grounded v3.

Three model states per record: 120 requests, a 130-attempt ceiling and $0.05
estimated cost ceiling. Reuse identical cached responses when available; record
per-rubric tokens, cost, model version, snapshots, and full quotes. A separate
cached replay must make zero new requests. Evaluate useful retention, top-ten
precision/recall and graded ranking, plus controls admitted and review volume.
Do not tune questions, weights, labels or literal rules after these outcomes.
Any further revision needs a new version and new data.

This test does not measure real demand, grouping accuracy, contemporary community
prevalence or commercial viability. All questions are historical; unused records
come from the prior candidate pool, not its evaluated reference set. ID and
normalized content overlap is prohibited with both earlier sets. User review of
labels and downstream research remain needed. No default production promotion
is authorized by a software-test pass alone.
