# Fresh live usefulness review — October 10, 2026

## Verdict

Problem Hunter runs, but this test does **not** demonstrate a useful autonomous
problem-research product. It finds some concrete experiences and preserves
evidence, but collection is noisy, priority scores admit the wrong material, and
solution comparisons fail to extract information needed to make a decision.
Do not interpret a priority of 73/100 as a 73% chance of a good opportunity.

The best lead was a freelance developer's specific complaint about vague client
feedback and phone photos of screens. It explicitly concerns coding agents and
already has a self-built remedy, FasterFixes. That is useful context, not proof
of an unsolved business opportunity. The automated landscape then selected
SurveySparrow from a directory, with no established task fit. This is a concrete
failure to save the reader research time.

## What was actually run

Application commit: `f1008977030300eb1ac298046837bcaf56cbdc40`, on `main`.
PR #2 was merged after passing Python 3.10/3.12 CI. Local main is synchronized;
only main remains locally and remotely after the authorized branch cleanup.
A full-history backup bundle is local under `reports/backups/`.

Eight workflow scopes were fixed before scoring. Each used the existing live
Brave/Hacker News discovery, URL enrichment, general-v4 JEV evaluation, SQLite
grouping/scoring and report exporter. Four eligible leads also used the existing
live Researcher with an explicit reviewed brief and five remedy types. Four
fields stopped because they had no eligible retained problem; those are failures
of the end-to-end yield, not completed solution comparisons.

No old corpus, synthetic posts, offline judgments or prior HTTP cache was used.
The test used new per-field databases and one shared cost ledger. Raw search
responses, source content, model questions/answers, briefs and reports are saved.
One freshly retrieved restaurant URL overlapped the previous pilot and was
excluded before scoring. One education page had a 2019 publication URL despite a
recent search date and was likewise excluded. The remaining 59 sources were
evaluated without changing the application rubric or scoring weights.

**Freshness qualification:** the test harness supplied search filters for
January 1, 2025–October 10, 2026. The application does not yet expose these filters.
A recent page/search date does not establish a recent experience: retrospective
stories remained in the results. Remedy searches deliberately had no date filter,
because an older physical/process remedy may still work. Applicability must be
checked; one retrieved tenant guide dates to 2009. Fresh collection therefore
does not mean every result describes a new or still-unresolved problem.

Assistant source judgments were recorded before model scores were inspected.
They are qualitative assessments of reviewed text, not independent human ground
truth or a calibrated accuracy benchmark. Broad pages were reviewed through
visible text and relevant passages, not a claim that every sentence was audited.
Source-by-source evaluation isolated failures while keeping application behavior;
there were no evaluation exceptions. Research extraction failures were retained,
including robots denials, a 403 response and unavailable text. No access controls
were bypassed to improve the automated results.

## Field results

| Field / workflow | Collected | Marked full text | Retained groups | Assessment |
| --- | ---: | ---: | ---: | --- |
| Restaurants / staff scheduling | 7 | 5 | 1 | Vendor-heavy. Only retained passage praises software preventing schedule errors; not evidence of an unmet problem. No eligible research brief. |
| Construction / change orders | 8 | 7 | 0 | Mostly guides, recruitment and general commentary. No usable retained problem; no landscape. |
| Ecommerce / seller returns | 8 | 8 | 1 | Buyer USB-PD defect/returns account incorrectly admitted to seller scope. No eligible landscape. |
| Education / lesson planning and administration | 8 | 7 | 5 | Highest scores favor retrospective planning burdens. Practical substitute handoff/access lead exists, but only as a mixed-speaker snippet. Landscape names Sub Manager with every comparison field unknown. |
| Family caregiving / coordination | 6 | 6 | 0 | Guides and a product launch, not strong direct caregiver coordination accounts. No retained problem; no landscape. |
| Adult friendships / local activities | 8 | 5 | 3 | Plausible frustration and flaking leads, all retained sources are snippets with uncertain attribution. Landscape yields no named remedy. |
| Freelance creative work / client feedback | 8 | 6 | 4 | Strongest concrete AI-era website-feedback account; author already built FasterFixes. Another maker built Notedis. Interview rejection feedback is wrongly admitted. Landscape names SurveySparrow but establishes no fit. |
| Housing / apartment noise | 8 | 7 | 2 | Concrete noise/vibration snippet plus an older resolved neighbor experience. Landscape names Green Glue and Direct Approach, but establishes neither task nor constraint fit. |
| **Total** | **61** | **51** | **16** | **Four research attempts; no useful completed comparison.** |

Of the 61 collected sources, the prospective review marked four as concrete
first-person in-scope accounts (two education, two freelance). These include
existing or resolved approaches. This count is a description of this small
bounded sample, not a general precision estimate. Snippets and secondary accounts
may still be useful leads, but cannot establish independent current experiences.

The 51 full-text labels overstate extraction quality: a creative page contained
only an 82-character unrelated course card; a caregiving page only 110 characters
of a clipped preview; a restaurant page only 247 characters of an article card.
Successfully extracting some HTML text is not the same as retrieving the article.

## Are the ratings useful?

Sometimes they surface the right passage: the FasterFixes account ranks first in
freelance feedback at 73.08. But they also place a retrospective planning article
at 65.95 and a retrospective teacher-founder account at 64.75, above a practical
handoff lead at 49.75 and a teacher interruption account at 47.97. The buyer's
device return complaint scores 49.54 in the seller workflow. A positive scheduling
software review still becomes a candidate at 18.49.

Scores are weighted model judgments, not calibrated estimates of usefulness.
Literal quote matching helps prevent fabricated excerpts, but does not establish
that a quote expresses an unresolved problem, belongs to the intended speaker,
or concerns the requested actor/task. In snippet results, suggested remedies from
other commenters sometimes appear as the complainant's own workaround. Review
flags disclose uncertainty, but uncertain material still receives prominent ranks.
The app needs better representation and routing before more score tuning.

## Does solution research save time?

The four attempts retrieved 16 candidate pages and produced four named remedies
in total. Across those four named records there are **zero grounded function,
pricing, setup, customer-complaint, adoption or constraint claims**, and only one
limits claim, from the old tenant guide. All task-fit fields are unknown and all
four dispositions are insufficient information. This is conservative about
unsupported conclusions, but insufficiently informative for the user's goal.

Specific failure mechanisms visible in the saved results and code:

- Search takes roughly one page per remedy-type query, so weak or adjacent pages
  consume the small budget. The creative search returns a freelance job-marketplace
  guide and a general feedback directory. It does not follow up the named remedies
  already present in the original complaint.
- Only one remedy is selected from a page. Names and excerpts are independently
  selected; excerpts naming a different remedy are correctly discarded, leaving
  otherwise recognizable candidates with empty comparisons.
- Name candidates come from a bounded capitalization heuristic; evidence is
  limited to the first 48 sentences within 16,000 characters. Navigation and
  general introductory prose can occupy the useful window.
- Services/practices can disappear when model type is unknown. The MangoApps
  handoff page was retrieved fully and had selected excerpts, but yielded no
  remedy record. A housing provider page selected Green Glue yet retained no claims.
- Generic next checks instruct the reader to trial the closest remedy even when
  the report establishes no closest remedy.

Manual checks are separate from the automated output. The retrieved
[MangoApps handoff template](https://www.mangoapps.com/templates/forms/substitute-teacher-classroom-handoff-and-emergency-procedures-form)
describes capturing schedules, materials, classroom setup and lesson information.
That is relevant to organizing a handoff, though it does not prove smartboard
access codes or resource permissions are solved. The automated comparison misses
this useful distinction.

The retrieved but robots-denied
[Webvizio provider article](https://webvizio.com/blog/best-tools-web-development-agencies-use-to-manage-client-feedback/)
describes contextual website feedback and AI debugging; its page also links to
coding-agent/MCP functionality. These are provider claims requiring a trial, not
verified behavior or independent adoption. They show why current AI-era remedies
need explicit investigation. Manual browser retrieval is not credited as an
automated pipeline success, and provider comparisons of competitors are not
treated as verified competitor facts.

## Cost and limits

Approved cap: new shared **US$1**. Estimated recorded spend: **US$0.199462758**.

| Stage | Estimated cost |
| --- | ---: |
| Fresh collection | $0.080000000 |
| Evaluation | $0.010297602 |
| Solution research | $0.109165156 |

36 Brave network requests at $0.005 each; 70 JEV requests totaling 463,399 input
tokens at $0.042/million input tokens, output priced free. 24 HN requests and 79
web retrieval requests had zero configured provider cost. Two research web cache
hits were internal to this new run, not reuse of an old corpus. These are list-price
estimates, not a reconciled invoice. Manual browser spot checks are separate from
the application's API ledger. No further paid calls are needed for this review.

Eight broad workflows and at most eight sources each provide a diagnostic test,
not exhaustive industry coverage. No customer contact, recurrence validation,
actual product trials or business viability assessment was performed.

## Next development steps, in order

1. **Improve evidence acquisition and recency.** Prefer permitted original
   discussions with a clear actor and task; separate snippets, vendor explanations
   and first-person accounts. Reject article cards as complete bodies. Record
   original publication separately from modified/search dates and separate the
   date of an experience from publication. Before scoring, require enough reviewed
   current source material to make the field meaningful; report low yield openly.
2. **Fix problem routing and representation.** Preserve actor, task, failure,
   consequence, attempted remedy, current status and speaker-bound excerpts.
   Use this run's positive-review, buyer/seller, recruitment-feedback and historical
   examples as regression cases. Do not blindly remove maker posts: they can contain
   actual useful experience, but their existing remedy must be explicit.
3. **Make a small solution comparison useful.** Start with the concrete freelance
   feedback case. Follow the original named remedies to permitted official
   documentation and pricing, retain several offerings from comparison pages,
   and select evidence for each established identity. Show the exact known fit
   and unknown constraint, including AI-agent integration and non-build remedies.
   Inspect results on this diagnostic corpus, then run a separate fresh sample
   before claiming improvement. Do not use the same examples as an unseen test.

Acceptance should be a few readable, source-backed comparisons that save research
time, with no obvious wrong-actor or positive-review candidates in their shortlist.
More features or a larger crawl are not justified by these results. The immediate
question is whether these repairs improve useful yield and reduce manual correction.

Local audit artifacts: `reports/fresh-e2e-2026-10-10/` contains the frozen protocol,
prospective-review.json, research-selection.json, per-field collected/evaluated/
researched JSON and Markdown, per-field databases, the shared ledger and usage.json.
Raw third-party content stays local and ignored; this review contains findings only.
