"""Official Brave/HN discovery and conservative evidence deduplication."""
import asyncio
import hashlib
import html
import logging
import re
import unicodedata
from datetime import date, datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .models import Source

logger = logging.getLogger(__name__)
PATTERNS = [
    '"frustrating"', '"I struggle"', '"takes hours"', '"manually"',
    '"workaround"', '"too expensive"', '"wish there was"', '"missing feature"',
    '"pay someone"', '"waste of time"', '"customer complaints"', '"hate"',
    '"spreadsheet" "tracking"', '"repetitive"', '"cannot find"', '"unreliable"',
    '"how do you manage"', '"need help"', '"costing money"', '"pain point"',
    '"alternative" "expensive"', '"every day" "problem"', '"still using paper"',
    '"scheduling" "difficult"', '"would pay"', '"labor intensive"',
    '"billing" "mistakes"', '"lost customers"', '"no solution"', '"time consuming"',
]


def generate_queries(topic, count=25):
    if not topic or not topic.strip():
        raise ValueError("Topic must not be empty")
    if not 1 <= count <= 30:
        raise ValueError("Query count must be between 1 and 30")
    return [f'{topic.strip()} {pattern}' for pattern in PATTERNS[:count]]


def normalize_url(url):
    parts = urlsplit(url.strip())
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        raise ValueError("Source URL must be an absolute HTTP(S) URL")
    if parts.username or parts.password:
        raise ValueError("URLs containing credentials are not supported")
    hostname = parts.hostname.lower()
    host = f'[{hostname}]' if ':' in hostname else hostname
    port = parts.port
    if port and not (parts.scheme.lower() == "http" and port == 80 or parts.scheme.lower() == "https" and port == 443):
        host += f':{port}'
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}]
    return urlunsplit((parts.scheme.lower(), host, parts.path or "/", urlencode(sorted(query)), ""))


def content_signature(content):
    """Punctuation/case edits to a repost are not independent observations.

    Semantic similarity alone is deliberately insufficient to classify a report
    as copied: independent people often describe the same recurring complaint.
    """
    normalized = unicodedata.normalize("NFKC", content).casefold()
    return " ".join(re.findall(r"\w+", normalized))


def deduplicate(sources, existing=None):
    """Return a deduplicated corpus, optionally including prior persisted sources.

    Passing prior sources detects copies across runs; retained objects accumulate
    duplicate_urls, which must be persisted again to keep all evidence links.
    """
    result, urls, contents = [], {}, {}
    prior_objects = {id(source) for source in (existing or [])}
    for source in [*(existing or []), *sources]:
        if source.url:
            try:
                canonical = normalize_url(source.url)
            except ValueError:
                logger.warning("Skipping source with invalid URL")
                continue
        else:
            canonical = ""
        normalized = content_signature(source.content)
        content_hash = hashlib.sha256(normalized.encode()).hexdigest()
        identity = canonical or f'content:{content_hash}:author:{source.author or ""}'
        source.id = hashlib.sha256(identity.encode()).hexdigest()
        # Short/common snippets cannot establish that two independent reports are copies.
        copied = contents.get(content_hash) if len(normalized) >= 80 else None
        existing = urls.get(identity) or copied
        if existing:
            same_identity = identity in urls
            existing.metadata.setdefault("duplicate_urls", [])
            if source.url != existing.url and source.url not in existing.metadata["duplicate_urls"]:
                existing.metadata["duplicate_urls"].append(source.url)
            if ((source.content_kind == "full_text" and existing.content_kind != "full_text")
                    or (same_identity and id(existing) in prior_objects and source.content_kind == existing.content_kind
                        and (source.content != existing.content or source.title != existing.title or source.author != existing.author))):
                existing.content, existing.content_kind = source.content, source.content_kind
                existing.title = source.title or existing.title
                existing.author = existing.author or source.author
                existing.published_at = existing.published_at or source.published_at
                existing.metadata.update({k: v for k, v in source.metadata.items() if k != 'duplicate_urls'})
            for duplicate_url in source.metadata.get("duplicate_urls", []):
                if duplicate_url != existing.url and duplicate_url not in existing.metadata["duplicate_urls"]:
                    existing.metadata["duplicate_urls"].append(duplicate_url)
            continue
        urls[identity] = source
        contents[content_hash] = source
        result.append(source)
    return result


def clean_html(value):
    return html.unescape(re.sub(r"<[^>]+>", " ", value or "")).strip()


class Discovery:
    def __init__(self, http, brave_key="", concurrency=3):
        self.http, self.brave_key = http, brave_key
        self.semaphore = asyncio.Semaphore(concurrency)
        self.errors = []
        self.search_events = []
        self.hunt_summary = {}

    async def search(self, query, provider="brave", *, since=None, until=None):
        if since:
            date.fromisoformat(since)
        if until:
            date.fromisoformat(until)
        if since and until and since > until:
            raise ValueError('since must not follow until')
        async with self.semaphore:
            if provider == "brave":
                if not self.brave_key:
                    raise ValueError("BRAVE_SEARCH_API_KEY is required for Brave search")
                params = {"q": query, "count": 20, "extra_snippets": "true"}
                if since or until:
                    params['freshness'] = f"{since or '2000-01-01'}to{until or date.today().isoformat()}"
                response = await self.http.request("GET", "https://api.search.brave.com/res/v1/web/search", provider="brave",
                    params=params, headers={"X-Subscription-Token": self.brave_key})
                response.raise_for_status()
                rows = response.json().get("web", {}).get("results", [])
                self.search_events.append({"provider": "brave", "query": query, "raw_results": len(rows)})
                return deduplicate([Source(url=row["url"], title=clean_html(row.get("title", "")),
                    content=clean_html(" ".join([row.get("description", ""), *row.get("extra_snippets", [])])),
                    source=urlsplit(row["url"]).hostname or "web", published_at=row.get("page_age"),
                    content_kind="snippet", metadata={"discovery_provider": "brave", "query": query,
                        'search_reported_at': row.get('page_age'), 'date_provenance': 'search-reported; original publication unverified',
                        'requested_since': since, 'requested_until': until})
                    for row in rows if row.get("url")])
            if provider == "hn":
                params = {"query": query, "tags": "comment", "hitsPerPage": 20}
                filters = []
                if since:
                    filters.append(f"created_at_i>={int(datetime.fromisoformat(since).replace(tzinfo=timezone.utc).timestamp())}")
                if until:
                    filters.append(f"created_at_i<={int(datetime.fromisoformat(until+'T23:59:59').replace(tzinfo=timezone.utc).timestamp())}")
                if filters:
                    params['numericFilters'] = ','.join(filters)
                response = await self.http.request("GET", "https://hn.algolia.com/api/v1/search", provider="hn", params=params)
                response.raise_for_status()
                rows = response.json().get("hits", [])
                self.search_events.append({"provider": "hn", "query": query, "raw_results": len(rows)})
                return deduplicate([Source(url=f'https://news.ycombinator.com/item?id={row["objectID"]}',
                    title=row.get("story_title") or "Hacker News comment", content=clean_html(row.get("comment_text")),
                    source="Hacker News", author=row.get("author"), published_at=row.get("created_at"),
                    metadata={"discovery_provider": "hn", "query": query, "story_id": row.get("story_id"),
                        'original_published_at': row.get('created_at'), 'date_provenance': 'original comment timestamp',
                        'requested_since': since, 'requested_until': until})
                    for row in rows if row.get("objectID") and row.get("comment_text")])
            raise ValueError(f"Unknown search provider: {provider}")

    async def hunt(self, topic, queries=25, max_sources=100, *, since=None, until=None, discussions=False):
        for value in (since, until):
            if value:
                date.fromisoformat(value)
        if since and until and since > until:
            raise ValueError('since must not follow until')
        if max_sources < 1:
            raise ValueError("max_sources must be positive")
        generated = generate_queries(topic, queries)
        if discussions:
            generated = [f'{q} (site:reddit.com OR site:news.ycombinator.com OR inurl:forum OR inurl:community)' for q in generated]
        tasks = [(q, "brave") for q in generated] if self.brave_key else []
        tasks += [(topic, "hn"), (f'{topic} problem', "hn"), (f'{topic} manual', "hn")]
        async def run(query, provider):
            try:
                return await self.search(query, provider, **({'since': since, 'until': until} if since or until else {}))
            except Exception as exc:
                self.errors.append(f"{provider}: {type(exc).__name__}: {exc}")
                logger.warning("Search failed for %s: %s", provider, type(exc).__name__)
                return []
        batches = await asyncio.gather(*(run(q, p) for q, p in tasks))
        # Limit after interleaving providers; a small limit must not discard all
        # attributed discussion comments behind the first Brave result page.
        pools = {provider: deduplicate([source for (query, p), batch in zip(tasks, batches)
                                        if p == provider for source in batch]) for provider in ('brave', 'hn')}
        if discussions:
            for pool in pools.values():
                pool.sort(key=lambda s: not (s.author or re.search(r'reddit\.com|news\.ycombinator\.com|/forum|/community', s.url, re.I)))
        mixed = []
        for index in range(max((len(pool) for pool in pools.values()), default=0)):
            for provider in ('brave', 'hn'):
                if index < len(pools[provider]):
                    mixed.append(pools[provider][index])
        unique = deduplicate(mixed)
        self.hunt_summary = {"provider_candidates": {p: len(pool) for p, pool in pools.items()},
                             "unique_before_limit": len(unique), "retained": min(len(unique), max_sources),
                             "dropped_by_source_limit": max(0, len(unique)-max_sources),
                             "search_events": list(self.search_events), "search_failures": list(self.errors)}
        return unique[:max_sources]
