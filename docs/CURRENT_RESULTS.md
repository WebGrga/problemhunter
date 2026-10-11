# Current usefulness review — October 11, 2026

**The app runs, but reliable autonomous opportunity discovery is not demonstrated.**
The new mobile-detailing test produced no validated business opportunity and no
completed existing-remedy comparison. Cleanup makes maintenance smaller; it does
not improve these usefulness results by itself.

## Fresh unchanged test

Business: small mobile car-detailing operators handling appointments, cancellations,
no-shows and weather disruptions. The command in the README ran against application
commit `689706e`, with general-v5 and its representation questions unchanged.
There were no stored problem sources/opportunities in the shared ledger beforehand.
Collection searched publications from January 1, 2025 through October 11, 2026.
Four Brave queries and three HN searches ran; the maximum was 20 retained sources
and $0.15 incremental estimated cost. This is a small bounded sample, not industry
coverage or a benchmark accuracy estimate.

| Stage | Actual outcome |
| --- | --- |
| Collection | 4 sources: 3 Reddit snippets, 1 attributed HN comment |
| Full-body enrichment | All 3 Reddit fetches blocked by robots policy; none completed |
| Evaluation | 7 live JEV requests; 1 retained, review-required lead |
| Independent recurrence | 0 corroborated groups; 0 identified complainants for the lead |
| Ranking | Double bookings: investigation priority 61/100; commercial evidence lower bound 0/100 |
| Solution research | `needs_workflow_definition`; no comparison or research API requests |
| Estimated incremental cost | $0.021169028; 14 network requests, 1 cached robots-policy response |

The source review matters more than the ranking:

- [Booking discussion](https://www.reddit.com/r/AutoDetailing/comments/1l1nw54/detailers_how_are_you_guys_managing_bookings/):
  the retained snippet describes double bookings, but mixes a BookingPress
  recommendation with a maker describing an app for a friend. Speaker attribution,
  current unresolved burden and what the existing remedies fail to do are unknown.
  The representation reuses the overbooking sentence for actor, task, consequence
  and constraint. Literal text selection alone has not produced a useful problem
  definition. Treat it as an ambiguous lead, not a confirmed opportunity.
- [Equipment discussion](https://www.reddit.com/r/AutoDetailing/comments/1l8fwuz/mobile_detailing_huge_mistake_pov/):
  equipment/growing pains and having obtained a trailer/spares; not a demonstrated
  current appointment-management problem. Rejected.
- [Detailer workload discussion](https://www.reddit.com/r/AutoDetailing/comments/1odrrg0/i_feel_like_a_terrible_car_detailer/):
  dealership cleaning quality versus speed, mixed with commenters' advice; different
  actor/task from the mobile-business scheduling scope. Rejected.
- [HN car-wash comment](https://news.ycombinator.com/item?id=47031942):
  mentions arranging a mobile appointment, with no experienced failure. Rejected.

The rejected material was appropriately excluded in this sample. The remaining
61/100 score is not proof of usefulness: it comes from one ambiguous snippet.
The zero commercial score reflects missing evidence, not proof of no market.
Recent search filters do not establish present-day need or account for AI remedies.

## What runs automatically

One command handles search, fetch attempts, evaluation, grouping, scoring and
exports. Only topic, scope, dates and limits changed for this business. No custom
industry questions, code changes or hand-picked replacement dataset were used.

The full research process is not autonomous. General solution research requires a
manually reviewed affected-person/task/outcome/constraint brief. This test exposed
that gap even with `--research-top 3`. I did not invent a remaining constraint or
retune the questions to force a better result. Original-source review and checking
whether the need still exists also require human work today.

Raw outputs: `reports/mobile-detailing-2026-10-11/results.{md,json,yield.json}`.
Stored source bodies and model responses: the shared ledger database.

## Earlier evidence, kept in proportion

The previous eight-field fresh run collected 61 sources, evaluated 59 and retained
16 groups. Four solution-research attempts gave insufficient information.
After the previous implementation repairs, five fresh samples still produced no
primary candidates. One manually prepared client-feedback comparison found five
remedies and 25 source claims, but complete constraint fit, verified customer
complaints and adoption remained unknown. This supports using the app as an
assisted research prototype, not trusting its rankings as business recommendations.

Earlier raw fresh evidence is byte-verified in
`reports/archives/fresh-audit-2026-10-10.tar.gz`. The final client-feedback comparison
remains separately readable in `reports/client-feedback-2026-10-10/`.

## Cleanup and remaining work

Removed historical invoice benchmark/evaluator code, v1–v3 invoice definitions,
five one-off collection/replay scripts and their obsolete tests. Retained the
current pipeline and tests protecting provenance, costs, persistence, scope,
quotes and comparisons. Historical tracked material remains in Git history.
Repeated documents were replaced by four concise documents plus the README.
Old invoice/demo reports were deleted; fresh raw audits were compressed and
verified before the loose copies were removed. The cost ledger was preserved.

Documentation and reports are not automatically included in JEV requests. Their
main overhead was maintenance, duplicate storage and unnecessarily large reading
context. Removing them cannot fix sparse acquisition or semantic mistakes.
The next useful improvement is attributable original complaint evidence and
correct unresolved-problem interpretation, followed by evaluated automation of
the workflow brief. See `NEXT_STEPS.md`; no additional feature expansion is justified.
