"""One normalization, evaluation, grouping and storage path for every input."""
import logging
import hashlib
import json
from .discovery import deduplicate, content_signature
from .grouping import group_problems
from .scoring import score_opportunity
from .reports import _rank_key

log = logging.getLogger(__name__)


class Pipeline:
    def __init__(self, store, evaluator, extractor=None, researcher=None, llm=None):
        self.store = store
        self.evaluator = evaluator
        self.extractor = extractor
        self.researcher = researcher
        self.llm = llm

    async def process(self, sources, enrich=False, research_top=0):
        http = getattr(self.evaluator, 'http', None)
        if http is not None:
            http.phase = 'collection'
        sources = deduplicate(sources)
        if enrich and self.extractor:
            import asyncio
            semaphore = asyncio.Semaphore(4)

            async def fetch(source):
                async with semaphore:
                    return await self.extractor.enrich(source)
            sources = deduplicate(await asyncio.gather(*(fetch(s) for s in sources)))
        incoming_urls = {s.url for s in sources if s.url}
        incoming_content = {content_signature(s.content) for s in sources}
        existing = self.store.load_sources()
        sources = deduplicate(sources, existing=existing)
        self.store.save_sources(sources)
        mode = 'offline' if self.evaluator.offline else self.evaluator.model
        synthesis = [getattr(self.llm, 'endpoint', ''), getattr(self.llm, 'model', '')] if self.llm else None
        def signature(source):
            return hashlib.sha256(json.dumps([mode, source.title, source.content, source.content_kind, source.author, source.source, synthesis, 'rubric-v3-grounded', getattr(self.evaluator, 'rubric_fingerprint', None)]).encode()).hexdigest()
        current = [s for s in sources if s.url in incoming_urls
                   or set(s.metadata.get('duplicate_urls', [])) & incoming_urls
                   or content_signature(s.content) in incoming_content]
        # Recompute grouping over the corpus, but never reclassify unrelated prior
        # inputs under a different topic simply because they share this database.
        fresh = [s for s in current if s.metadata.get('evaluation_signature') != signature(s)]
        log.info("Evaluating %s new or changed sources (%s unchanged)", len(fresh), len(sources)-len(fresh))
        if http is not None:
            http.phase = 'evaluation'
        problems = await self.evaluator.evaluate(fresh)
        self.store.replace_problems([s.id for s in fresh], problems)
        for source in fresh:
            source.metadata['evaluation_signature'] = signature(source)
            source.metadata['evaluation_status'] = 'evaluated'
            source.metadata['evaluation_mode'] = mode
        self.store.save_sources(sources)
        # Recompute over the corpus so separate imports contribute to recurring groups.
        all_sources = self.store.load_sources()
        all_problems = self.store.load_problems()
        if self.llm:
            from .grouping import semantic_group
            opportunities = await semantic_group(all_problems, all_sources, self.llm)
        else:
            opportunities = group_problems(all_problems, all_sources)
        prior = self.store.load_opportunities()
        used = set()
        # Carry stable identities when growing evidence changes a grouping hash.
        for opportunity in opportunities:
            matches = [old for old in prior if old.id not in used and set(old.problem_ids) & set(opportunity.problem_ids)]
            if matches:
                old = max(matches, key=lambda p: len(set(p.problem_ids) & set(opportunity.problem_ids)))
                used.add(old.id)
                opportunity.id = old.id
                opportunity.bookmarked = old.bookmarked
                opportunity.solutions = old.solutions
                opportunity.potential_fixes = old.potential_fixes
                opportunity.research_status = old.research_status
                opportunity.research_brief = old.research_brief
                opportunity.solution_landscape = old.solution_landscape
                if old.solution_landscape and set(old.problem_ids) != set(opportunity.problem_ids):
                    opportunity.solution_landscape = {}
                    opportunity.solutions = []
                    opportunity.research_status = 'brief_needs_review'
                    opportunity.unknowns.append('Supporting problem group changed; review the saved brief before trusting prior solution research.')
        for opportunity in opportunities:
            score_opportunity(opportunity, all_problems, all_sources)
        opportunities.sort(key=_rank_key)
        if self.researcher and research_top:
            if http is not None:
                http.phase = 'research'
            opportunities = await self.researcher.research(opportunities, top=research_top)
            for opportunity in opportunities:
                score_opportunity(opportunity, all_problems, all_sources)
            opportunities.sort(key=_rank_key)
        self.store.replace_opportunities(opportunities)
        return self.store.load_opportunities()
