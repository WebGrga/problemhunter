import httpx
import pytest

from problem_hunter.discovery import Discovery, deduplicate, generate_queries, normalize_url
from problem_hunter.models import Source


def test_queries_and_urls():
    assert len(generate_queries("restaurants", 30)) == 30
    with pytest.raises(ValueError):
        generate_queries("", 25)
    assert normalize_url("HTTPS://EXAMPLE.com:443/a?utm_source=x&b=2#a") == "https://example.com/a?b=2"


def test_dedup_preserves_copy_links_and_independent_short_reports():
    sources = [Source("https://a.com", "A", "pain " * 30), Source("https://b.com", "B", "pain " * 30)]
    result = deduplicate(sources)
    assert len(result) == 1
    assert result[0].metadata["duplicate_urls"] == ["https://b.com"]
    assert len(deduplicate([Source("https://a.com", "", "slow"), Source("https://b.com", "", "slow")])) == 2
    assert result[0].id == deduplicate([sources[0]])[0].id


def test_cross_run_punctuation_repost_and_metadata():
    text = "I waste three hours each day manually assigning appointments and tracking customer bookings in paper records."
    prior = deduplicate([Source("https://a.com/post", "", text)])[0]
    copied = Source("https://b.com/post", "", text.upper().replace(" ", "  ").replace(".", "!!!"))
    corpus = deduplicate([copied], existing=[prior])
    assert len(corpus) == 1
    assert corpus[0].metadata["duplicate_urls"] == ["https://b.com/post"]


@pytest.mark.asyncio
async def test_brave_and_hn_normalization():
    class HTTP:
        async def request(self, method, url, **kwargs):
            if kwargs["provider"] == "brave":
                assert kwargs["headers"]["X-Subscription-Token"] == "key"
                data = {"web": {"results": [{"url": "https://example.com", "title": "Complaint", "description": "Too slow", "page_age": "2025-01-01"}]}}
            else:
                data = {"hits": [{"objectID": "123", "comment_text": "<p>I waste hours</p>", "author": "alice", "created_at": "2025-01-02", "story_id": 9}]}
            return httpx.Response(200, json=data, request=httpx.Request(method, url))
    discovery = Discovery(HTTP(), "key")
    brave = (await discovery.search("restaurants"))[0]
    assert brave.content_kind == "snippet" and brave.published_at == "2025-01-01"
    hn = (await discovery.search("restaurants", "hn"))[0]
    assert hn.author == "alice" and hn.content == "I waste hours"


@pytest.mark.asyncio
async def test_hunt_partial_failures():
    class HTTP:
        async def request(self, *args, **kwargs):
            raise httpx.ConnectError("offline")
    discovery = Discovery(HTTP())
    assert await discovery.hunt("restaurants", 1) == []
    assert len(discovery.errors) == 3
