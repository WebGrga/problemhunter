import httpx
import pytest

from problem_hunter.extraction import Extractor, validate_public_url
from problem_hunter.models import Source


@pytest.fixture
def public_dns(monkeypatch):
    monkeypatch.setattr("problem_hunter.extraction.socket.getaddrinfo", lambda *args, **kwargs: [(2, 1, 6, "", ("8.8.8.8", 443))])


@pytest.mark.asyncio
async def test_private_and_credentials_rejected(monkeypatch):
    monkeypatch.setattr("problem_hunter.extraction.socket.getaddrinfo", lambda *a, **kw: [(2, 1, 6, "", ("127.0.0.1", 80))])
    for url in ["http://localhost", "https://example.com", "http://user:secret@example.com"]:
        with pytest.raises(ValueError):
            await validate_public_url(url)


@pytest.mark.asyncio
async def test_extract_metadata(public_dns):
    class HTTP:
        async def request(self, method, url, **kwargs):
            body = "User-agent: *\nAllow: /" if url.endswith("robots.txt") else '<title>Problem</title><meta name="author" content="Alice"><meta property="article:published_time" content="2025-01-01"><nav>noise</nav><main>I spend hours scheduling.</main>'
            return httpx.Response(200, text=body, headers={"content-type": "text/html"}, request=httpx.Request(method, url))
    source = await Extractor(HTTP()).fetch("https://example.com/post")
    assert source.content == "I spend hours scheduling."
    assert source.author == "Alice" and source.published_at == "2025-01-01"


@pytest.mark.asyncio
async def test_robots_denial_and_snippet_fallback(public_dns):
    class HTTP:
        async def request(self, method, url, **kwargs):
            assert url.endswith("robots.txt")
            return httpx.Response(200, text="User-agent: *\nDisallow: /", request=httpx.Request(method, url))
    extractor = Extractor(HTTP())
    with pytest.raises(PermissionError):
        await extractor.fetch("https://example.com/post")
    source = await extractor.enrich(Source("https://example.com/post", "", "snippet", content_kind="snippet"))
    assert source.content_kind == "snippet" and "extraction_error" in source.metadata


@pytest.mark.asyncio
async def test_redirect_revalidates_private_target(public_dns):
    class HTTP:
        async def request(self, method, url, **kwargs):
            if url.endswith("robots.txt"):
                return httpx.Response(404, request=httpx.Request(method, url))
            return httpx.Response(302, headers={"location": "http://localhost/secrets"}, request=httpx.Request(method, url))
    with pytest.raises(ValueError, match="Local"):
        await Extractor(HTTP()).fetch("https://example.com/post")


@pytest.mark.asyncio
async def test_robots_network_failure_fails_closed(public_dns):
    class HTTP:
        async def request(self, *args, **kwargs):
            raise httpx.ConnectError("offline")
    with pytest.raises(PermissionError):
        await Extractor(HTTP()).fetch("https://example.com/post")


@pytest.mark.asyncio
async def test_large_download_rejected(public_dns):
    class HTTP:
        async def request(self, method, url, **kwargs):
            if url.endswith("robots.txt"):
                return httpx.Response(404, request=httpx.Request(method, url))
            return httpx.Response(200, content=b"x" * 2_000_001, headers={"content-type": "text/plain"}, request=httpx.Request(method, url))
    with pytest.raises(ValueError, match="2 MB"):
        await Extractor(HTTP()).fetch("https://example.com/post")


@pytest.mark.asyncio
async def test_mixed_public_private_dns_rejected(monkeypatch):
    monkeypatch.setattr("problem_hunter.extraction.socket.getaddrinfo", lambda *a, **kw: [
        (2, 1, 6, "", ("8.8.8.8", 443)), (2, 1, 6, "", ("10.0.0.1", 443))])
    with pytest.raises(ValueError, match="Non-public"):
        await validate_public_url("https://example.com")
