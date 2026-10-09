# Verification record

Development verification on Python 3.12:

- Automated unit, mocked API contract, pipeline integration and CLI tests pass.
- The fictional restaurant CSV demo retains three distinct reports, groups them
  into two opportunities, and preserves the duplicate original URL. A repeated
  import evaluates zero unchanged sources.
- Live Hacker News Algolia search (`restaurant manual`, one request) returned
  20 normalized comments with author and publication date information.
- Live `inspect-url https://example.com --offline` retrieved robots (404) and
  HTML, persisted one extracted source and exported empty opportunity reports.
  An informational example page correctly produced no qualifying complaint.
- A live extraction smoke test exposed a double-decompression bug. The transport
  now strips encoding headers after streaming decoded bytes; its regression
  test covers both initial and cached responses.

Initial development had no API credentials. Subsequent live verification used
local ignored `.env` credentials for Brave and TypeSafe, as described below.
Optional LLM synthesis remains unverified; that provider must implement the
configured JSON chat protocol.

## Credentialed examples (October 9, 2026)

- JEV authenticated successfully and returned `jev-1.13.0`, typed Noul/Score/Choice
  answers and token usage for the fictional three-source CSV demonstration.
- A bounded restaurant-reservations hunt exercised Brave, HN, permitted page
  extraction, JEV, SQLite, reporting and one group's solution searches. With
  balanced sources it used 29 network requests: five Brave, three HN, thirteen
  web retrievals and eight JEV evaluations. All opportunities remained weak;
  broad industry articles did not establish independent customer demand.
- A bounded freelancer-invoicing hunt processed eight sources. After tightening
  the genuine-problem rubric it retained two weak complaint leads: frustration
  with spreadsheet payment tracking and missing/unsent invoices. A developer
  résumé was rejected. Both leads lacked verified loss, payment intent and
  independently attributable recurring support, so their lower-bound scores
  were zero. This is insufficient validation, not proof the problems lack value.
- Reddit blocked full retrieval via robots; retained search snippets are labeled
  as snippets with their extraction limitations. No access restrictions were bypassed.

Live tests revealed important fixes:

1. Independent documents in a shared JEV state leaked evidence: a nonpayment
   inventory fixture received payment probability 0.95; isolating its state
   reduced that probability to 0.02. All seven questions are still batched, but
   the default now sends one source per state with explicit named references.
2. Small source limits formerly kept the first Brave page and dropped all HN
   comments. Source selection now interleaves the two providers before limiting.
3. Plain mentions of working hours no longer become loss excerpts; complaint
   statements favor explicit negative impacts over ordinary activity or achievements.
4. Model metadata is no longer incorrectly rendered as an unverified evidence quote.

Runtime API usage is retained in local SQLite databases. Provider prices were not
configured, so dollar totals remain unknown rather than claiming the calls were free.
Credentials and raw live reports/databases are ignored by Git; no keys are committed.
These small runs verify integration behavior, not model calibration or market demand.

Run the suite with `python -m pytest -q`. CI is configured for Python 3.10 and 3.12;
remote CI results are separate from the local verification described here.
