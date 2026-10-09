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

No Brave, TypeSafe or synthesis credentials were present. Their live behavior and
judgment quality have **not** been verified. Their request/response contracts are
covered with HTTP mocks, including the combined search → JEV → SQLite pipeline.
The optional model provider must implement the configured JSON chat protocol.

Run the suite with `python -m pytest -q`. CI is configured for Python 3.10 and 3.12;
remote CI results are separate from the local verification described here.
