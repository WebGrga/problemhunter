# Architecture and delivery milestones

Problem Hunter is a Python CLI with one processing path:

1. `discovery` uses Brave and HN; `extraction` retrieves permitted public pages;
   `importing` maps scraped CSV columns into the same `Source` records.
2. `pipeline` normalizes and deduplicates the current and persisted corpus.
3. `intelligence` asks JEV typed questions in bounded batches and retains raw
   answers, model identifiers, literal excerpts, and usage. Optional synthesis
   extracts a clearer statement and groups semantic equivalents.
4. `grouping` separates observations from identifiable complainants;
   `research` searches existing alternatives and distinguishes source excerpts,
   model interpretations, and hypotheses.
5. `scoring` computes evidence-supported points and separate evidence coverage.
6. `storage` persists sources, problems, opportunities, cached responses and API
   accounting; `reports` exports a portable, traceable corpus subset.

Shared dataclasses live in `models.py`. Every integration uses `HTTP.request` so
timeouts, bounded concurrency, per-provider rate limits, retry limits, request
ceilings, caching and accounting apply consistently. Web retrieval uses validated
public DNS addresses pinned for socket connections, with original TLS SNI and
Host preserved. Redirects are explicit and rechecked against robots policy.

SQLite writes are transactional. Reevaluation replaces problems for evaluated
sources; regrouping prunes stale groups and carries forward prior bookmarks and
research using overlapping problem identities. Evaluation fingerprints include
content, mode/model, synthesis configuration, and rubric version. Rejected inputs
are also marked evaluated so repeated runs do not consume unnecessary calls.

## Milestones

- Core vertical slice: source collection → JEV → SQLite → ranked reports.
- Recurrence and research: grouping, independent counts, source-grounded solution
  candidates, weighted scoring, and optional deeper synthesis.
- Additional inputs: URL inspection and mapped CSV import use the same pipeline.
- Reliability: mock API contracts, integration/CLI tests, retrieval restrictions,
  quotas, usage accounting, sample execution, and CI configuration.

The feature branch delivers these as one integrated, reviewable MVP. No dashboard
or browser extension is included. `Extractor.fetch` and `Pipeline.process` are
reusable entry points for a future browser extension service.

## Deliberate limits

The default grouping method uses normalized vocabulary and conservative token
similarity. Enable the optional LLM for broader paraphrases; its partition must
contain only supplied problem IDs exactly once. This is not a calibrated clustering
model and requires review on your industry's corpus. One main problem is extracted
per source. HTML content can aggregate several authors; only original attributed
post metadata counts as an identifiable complainant. Imports without original URLs
retain row provenance but have weaker traceability.

Scores do not estimate total market size. Missing reachability and implementation
evidence earn zero; this MVP does not manufacture feasibility or sales-channel
data. Solution research is capped at two searches and six candidates per group.
Without synthesis it produces conservative research candidates; with synthesis,
literal functional quotes can ground a model interpretation of product relevance.
Users still need to verify current pricing, offerings and customer complaints.
