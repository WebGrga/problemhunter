"""Conservative recurring-problem grouping with deduplicated support counts."""
import hashlib
import re
from .models import Opportunity

STOPWORDS = set("a an the i we my our it is are was were to of for and or in on with this that have has from by be as at but very every all me us can cannot can't people users problem problems frustrating frustration waste wastes wasted wasting hours hour minutes minute time manually manual".split())
SYNONYMS = {"appointments": "appointment", "bookings": "appointment", "booking": "appointment", "scheduling": "appointment", "schedule": "appointment", "spreadsheets": "spreadsheet", "manually": "manual", "hours": "hour", "customers": "customer", "clients": "customer", "invoices": "invoice"}


def tokens(text):
    return {SYNONYMS.get(w, w) for w in re.findall(r"[a-z]+", text.lower()) if w not in STOPWORDS}


def support_counts(sources):
    """Anonymous posts are separate reports; unknown identities never add users."""
    unique = {}
    for s in sources:
        fingerprint = hashlib.sha256(re.sub(r"\s+", " ", s.content.lower()).strip().encode()).hexdigest()
        unique.setdefault(fingerprint, s)
    # A named author posting twice is one independent complainant. Same-name
    # attribution is conservative across a platform; identities across sites
    # are not presumed equal.
    authors = {(s.source, s.author.casefold()) for s in unique.values() if s.author}
    return len(unique), len(authors)


def _opportunity(problems, sources):
    ids = sorted({p.id for p in problems})
    source_ids = sorted({p.source_id for p in problems})
    support = [s for s in sources if s.id in source_ids]
    independent, complainants = support_counts(support)
    # Attribution alone does not establish that a journalist or thread owner
    # experienced the complaint. Only first-hand, literal evidence qualifies.
    firsthand_ids = {p.source_id for p in problems if p.judgments.get('first_hand', 0) >= .6
                     and isinstance(p.evidence.get('first_hand'), str)
                     and p.evidence['first_hand'].strip()
                     and any(s.id == p.source_id and p.evidence['first_hand'] in s.content for s in support)}
    _, complainants = support_counts([s for s in support if s.id in firsthand_ids])
    first = problems[0]
    return Opportunity(id=hashlib.sha256("|".join(ids).encode()).hexdigest()[:24], title=first.statement[:120], description=first.statement,
                       category=first.category, problem_ids=ids, source_ids=source_ids,
                       independent_sources=independent, independent_complainants=complainants,
                       unknowns=(["Complainant identities are missing for some reports."] if any(not s.author for s in support) else []))


def group_problems(problems, sources):
    groups = []
    seen = set()
    for problem in problems:
        key = (problem.source_id, problem.statement.casefold())
        if key in seen:
            continue
        seen.add(key)
        terms = tokens(problem.statement)
        match = None
        for group in groups:
            representative = group[0]
            other = tokens(representative.statement)
            overlap = len(terms & other) / max(1, len(terms | other))
            family = problem.judgments.get('triage', {}).get('problem_family')
            other_family = representative.judgments.get('triage', {}).get('problem_family')
            if family or other_family:
                if family == other_family and family is not None and representative.category == problem.category:
                    match = group
                    break
                # Experimental workflow families must not merge with another family.
                continue
            if representative.category == problem.category and (problem.statement.casefold() == representative.statement.casefold() or overlap >= 0.55 and len(terms & other) >= 2):
                match = group
                break
        if match is None:
            groups.append([problem])
        else:
            match.append(problem)
    return [_opportunity(group, sources) for group in groups]


async def semantic_group(problems, sources, llm):
    """Optional semantic grouping; exact partition validation rejects fabricated ids."""
    if not llm or not problems:
        return group_problems(problems, sources)
    result = await llm.ask("Group equivalent experienced problems, not merely related industries. Return groups as a list of lists of problem ids. Include every supplied id exactly once. Preserve distinct root problems.", [{"id": p.id, "statement": p.statement, "category": p.category} for p in problems])
    groups = result.get("groups")
    if not isinstance(groups, list) or any(not isinstance(g, list) or not g for g in groups):
        raise ValueError("Invalid semantic grouping response")
    flat = [item for group in groups for item in group]
    expected = {p.id for p in problems}
    if any(not isinstance(item, str) for item in flat) or len(flat) != len(expected) or set(flat) != expected:
        raise ValueError("Semantic grouping must partition the supplied problem ids exactly")
    lookup = {p.id: p for p in problems}
    return [_opportunity([lookup[i] for i in group], sources) for group in groups]
