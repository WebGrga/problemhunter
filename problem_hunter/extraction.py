"""Bounded public-page extraction with fail-closed robots policy."""
import asyncio
from dataclasses import replace
import ipaddress
import json
import socket
import time
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup

from .discovery import deduplicate, normalize_url
from .models import Source

USER_AGENT = "ProblemHunter"
MAX_BYTES = 2_000_000


def page_dates(soup):
    """Preserve original publication separately from modification/search dates."""
    def meta(*keys):
        for key in keys:
            tag = soup.find('meta', attrs={'property': key}) or soup.find('meta', attrs={'name': key})
            if tag and tag.get('content'):
                return tag['content']
    published = meta('article:published_time', 'datePublished', 'date')
    modified = meta('article:modified_time', 'dateModified')
    def objects(value):
        if isinstance(value, dict):
            yield value
            for child in value.values():
                yield from objects(child)
        elif isinstance(value, list):
            for child in value:
                yield from objects(child)
    for tag in soup.find_all('script', attrs={'type': 'application/ld+json'}):
        try:
            for item in objects(json.loads(tag.string or tag.get_text())):
                published = published or item.get('datePublished')
                modified = modified or item.get('dateModified')
        except (ValueError, TypeError):
            continue
    return published if isinstance(published, str) else None, modified if isinstance(modified, str) else None


async def validate_public_url(url):
    normalized = normalize_url(url)
    parts = urlsplit(normalized)
    if parts.port not in {None, 80, 443}:
        raise ValueError("Only HTTP(S) default ports are permitted")
    host = parts.hostname
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
        raise ValueError("Local hosts are prohibited")
    try:
        addresses = await asyncio.to_thread(socket.getaddrinfo, host, parts.port or (443 if parts.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ValueError("Cannot resolve host safely") from exc
    if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
        raise ValueError("Non-public IP addresses are prohibited")
    return normalized


class Extractor:
    def __init__(self, http):
        self.http = http
        self.robots = {}
        self._locks = {}
        self._page_locks = {}
        self._last_request = {}

    async def _request(self, url):
        await validate_public_url(url)
        response = await self.http.request("GET", url, provider="web", headers={"User-Agent": USER_AGENT})
        if len(response.content) > MAX_BYTES:
            raise ValueError("Page exceeds 2 MB limit")
        return response

    async def _allowed(self, url):
        parts = urlsplit(url)
        origin = urlunsplit((parts.scheme, parts.netloc, "", "", ""))
        lock = self._locks.setdefault(origin, asyncio.Lock())
        async with lock:
            if origin not in self.robots:
                try:
                    response = await self._request(origin + "/robots.txt")
                    if response.status_code == 404:
                        self.robots[origin] = True
                    elif response.status_code == 200:
                        parser = RobotFileParser()
                        parser.parse(response.text.splitlines())
                        self.robots[origin] = parser
                    else:
                        self.robots[origin] = False
                except Exception:
                    self.robots[origin] = False
        policy = self.robots[origin]
        return policy if isinstance(policy, bool) else policy.can_fetch(USER_AGENT, url)

    async def _page_request(self, url):
        parts = urlsplit(url)
        origin = urlunsplit((parts.scheme, parts.netloc, "", "", ""))
        policy = self.robots[origin]
        delay = 1.0
        if not isinstance(policy, bool):
            delay = max(delay, policy.crawl_delay(USER_AGENT) or policy.crawl_delay("*") or 0)
            rate = policy.request_rate(USER_AGENT) or policy.request_rate("*")
            if rate and rate.requests:
                delay = max(delay, rate.seconds / rate.requests)
        # Avoid tying up workers indefinitely on sites requiring very long waits.
        if delay > 60:
            raise PermissionError("Site crawl delay exceeds extraction budget")
        lock = self._page_locks.setdefault(origin, asyncio.Lock())
        async with lock:
            remaining = self._last_request.get(origin, 0) + delay - time.monotonic()
            if remaining > 0:
                await asyncio.sleep(remaining)
            try:
                return await self._request(url)
            finally:
                self._last_request[origin] = time.monotonic()

    async def fetch(self, url):
        original_url = url
        current = await validate_public_url(url)
        for _ in range(6):
            if not await self._allowed(current):
                raise PermissionError("Robots policy denies access or could not be verified")
            response = await self._page_request(current)
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                if not location:
                    raise ValueError("Redirect has no destination")
                current = await validate_public_url(urljoin(current, location))
                continue
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").split(";")[0].lower()
            if content_type not in {"text/html", "application/xhtml+xml", "text/plain"}:
                raise ValueError("Unsupported page content type")
            if content_type == "text/plain":
                title, content, author, published = urlsplit(current).hostname, response.text, None, None
                modified = None
            else:
                soup = BeautifulSoup(response.text, "html.parser")
                title = soup.title.get_text(" ", strip=True) if soup.title else urlsplit(current).hostname
                author_tag = soup.find("meta", attrs={"name": "author"})
                author = author_tag.get("content") if author_tag else None
                published, modified = page_dates(soup)
                if not published:
                    time_tag = soup.find("time", attrs={"datetime": True, 'itemprop': 'datePublished'})
                    published = time_tag.get("datetime") if time_tag else None
                for element in soup(["script", "style", "nav", "header", "footer", "aside", "noscript", "form"]):
                    element.decompose()
                # Recommendation cards often use <article>; prefer the actual
                # main content when it contains substantially more material.
                articles = soup.find_all('article')
                article = max(articles, key=lambda e: len(e.get_text()), default=None)
                main = soup.find('main')
                body = main if main is not None and (article is None or len(main.get_text()) > 2 * len(article.get_text())) else article
                body = body if body is not None else main if main is not None else soup.body or soup
                content = body.get_text(" ", strip=True)
            content = " ".join(content.split())
            if not content:
                raise ValueError("Page has no extractable content")
            source = Source(url=original_url, title=title or current, content=content[:100_000],
                source=urlsplit(current).hostname or "web", author=author, published_at=published,
                content_kind='snippet' if len(content) < 300 else 'full_text',
                metadata={"retrieved_url": current, "extraction": "public page", "truncated": len(content) > 100_000,
                    'original_published_at': published, 'modified_at': modified,
                    'date_provenance': 'page publication metadata' if published else 'unknown',
                    'extraction_quality': 'short_fragment' if len(content) < 300 else 'body_candidate',
                    **({'evidence_limit': 'Extracted page fragment under 300 characters; completeness unverified'} if len(content) < 300 else {})})
            return deduplicate([source])[0]
        raise ValueError("Too many redirects")

    async def enrich(self, source):
        if source.content_kind == "full_text" or not source.url:
            return source
        try:
            fetched = await self.fetch(source.url)
            metadata = {**source.metadata, **fetched.metadata, 'search_reported_at': source.metadata.get('search_reported_at', source.published_at)}
            if fetched.published_at and source.published_at and fetched.published_at[:10] != source.published_at[:10]:
                metadata['date_conflict'] = 'Original publication differs from search-reported date'
            return replace(source, content=fetched.content if fetched.content_kind == 'full_text' else source.content,
                content_kind=fetched.content_kind, author=source.author or fetched.author,
                published_at=fetched.published_at or source.published_at, metadata=metadata)
        except Exception as exc:
            return replace(source, metadata={**source.metadata, "extraction_error": f"{type(exc).__name__}: {exc}",
                "evidence_limit": "Search snippet only; full discussion unavailable"})
