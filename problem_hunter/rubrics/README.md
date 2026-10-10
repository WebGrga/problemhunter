# Read and edit the JEV questions

The JSON files here are the actual definitions loaded by Python—not a separate
documentation copy.

| File | Used by |
|---|---|
| `production.json` | Normal `hunt`, `inspect-url`, and `import-csv` evaluation |
| `v1.json` | First experimental invoice investigation-priority rubric |
| `v2.json` | New contained-evidence/soft-review experiment |
| `v3.json` | Eight-question, literal-grounded invoice triage; opt-in CLI and benchmark |
| `general-v4.json` | Domain-neutral opt-in CLI; runtime scope and exact passage selection |

Each question has its actual `type`, `instructions`, and, for Score or Choice,
`criteria`. Score list positions are levels 0, 1, 2, etc.; fractional results are
probability-weighted rubric indices, not probabilities of business success.
Experimental `weights` and `routing` are also visible here. Payment intent is
separate from priority: unknown is neither refusal nor a predicted buyer.

For a formatted, local-only view:

```sh
python -m problem_hunter.benchmark questions --rubric v2
python -m problem_hunter.benchmark questions --rubric v3
python -m problem_hunter.benchmark questions --rubric general-v4
python -m problem_hunter.benchmark questions --rubric v1
python -m problem_hunter.benchmark questions --rubric production
```

To test edits, copy an experiment file to a new JSON file, give it a new `version`,
edit instructions/criteria/weights and pass its path:

```sh
python -m problem_hunter.benchmark questions --rubric path/to/my-rubric.json
python -m problem_hunter.benchmark compare path/to/reference.json \
  --rubric path/to/my-rubric.json --reference-rubric v1 \
  --db reports/my-experiment.db --output reports/my-experiment \
  --max-requests 90 --max-cost 0.05
```

Keep question IDs, Choice option IDs and routing mode intact; the loader rejects
incompatible definitions before making API calls. Score questions support 2–10
described levels; the experimental scorer normalizes by the actual level count.
Weights must remain positive and total 100.
Changes to weights alone do not change the model request, so cached judgments
can be reused. New question wording changes request cache identity.

Definitions are snapshotted once at run start; editing a file during a run does
not alter that run's experimental requests. Reports save exact baseline/revised
definitions and their SHA256 hashes, making past tests auditable after edits.
Production requests add an isolation prefix pointing at `record_N.content`.
Production rubric fingerprints are stored with each retained problem and included
in pipeline evaluation signatures, so edits trigger reevaluation on the next run.
Changing production question wording does **not** replace production score rules.

General-v4 uses twelve questions in one request per source. Three Choice templates
are populated with actual passage IDs (plus none), not fabricated text. Raw
evidence saves the rendered questions, passage map and selections. `--scope`
supplies the URL/CSV research topic; hunts use `--topic`. An omitted URL/CSV scope
is unrestricted. It uses the universal evaluator, not the invoice benchmark
comparator; general-v4 accuracy has not been established. Create a new version
and fresh dataset for future question tuning.

Do not edit frozen v1/v2/v3 after reviewing their results. Use a new version and fresh
reference records. The current experiment is invoice-specific; changing topic
requires editing its relevance question and constructing a matching labeled set.
