"""One normalization, evaluation, grouping and storage path for every input."""
import logging
import hashlib
import json
from .discovery import deduplicate
from .grouping import group_problems
from .scoring import score_opportunity

log = logging.getLogger(__name__)


class Pipeline:
    def __init__(self, store, evaluator, extractor=None, researcher=None, llm=None):
        self.store = store
        self.evaluator = evaluator
        self.extractor = extractor
        self.researcher = researcher
        self.llm = llm

    async def process(self, sources, enrich=False, research_top=0):
        sources = deduplicate(sources)
        if enrich and self.extractor:
            import asyncio
            semaphore = asyncio.Semaphore(4)

            async def fetch(source):
                async with semaphore:
                    return await self.extractor.enrich(source)
            sources = deduplicate(await asyncio.gather(*(fetch(s) for s in sources)))
        existing = self.store.load_sources()
        sources = deduplicate(sources, existing=existing)
        self.store.save_sources(sources)
        mode = 'offline' if self.evaluator.offline else self.evaluator.model
        synthesis = [getattr(self.llm, 'endpoint', ''), getattr(self.llm, 'model', '')] if self.llm else None
        def signature(source):
            return hashlib.sha256(json.dumps([mode, source.content, source.author, source.source, synthesis, 'rubric-v3-grounded', getattr(self.evaluator, 'rubric_fingerprint', None)]).encode()).hexdigest()
        fresh = [s for s in sources if s.metadata.get('evaluation_signature') != signature(s)]
        log.info("Evaluating %s new or changed sources (%s unchanged)", len(fresh), len(sources)-len(fresh))
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
        for opportunity in opportunities:
            score_opportunity(opportunity, all_problems, all_sources)
        opportunities.sort(key=lambda o: (-o.score, o.id))
        if self.researcher and research_top:
            opportunities = await self.researcher.research(opportunities, top=research_top)
            for opportunity in opportunities:
                score_opportunity(opportunity, all_problems, all_sources)
            opportunities.sort(key=lambda o: (-o.score, o.id))
        self.store.replace_opportunities(opportunities)
        return self.store.load_opportunities()
