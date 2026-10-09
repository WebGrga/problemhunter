import httpx
import gzip
import pytest

from problem_hunter.http import HTTP, BudgetExceeded
from problem_hunter.storage import Store


@pytest.mark.asyncio
async def test_compressed_responses_are_decoded_once_and_cached():
    def handler(request):
        return httpx.Response(200, headers={'Content-Encoding': 'gzip', 'Content-Type': 'text/plain'},
                              content=gzip.compress(b'compressed page'))
    with Store(':memory:') as store:
        async with HTTP(store, rate=0, transport=httpx.MockTransport(handler)) as client:
            assert (await client.request('GET', 'https://example.com')).text == 'compressed page'
            assert (await client.request('GET', 'https://example.com')).text == 'compressed page'


@pytest.mark.asyncio
async def test_retry_cache_usage_and_request_limit():
    calls = []
    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(429, headers={'Retry-After': '0'})
        return httpx.Response(200, json={'answers': {}, 'usage': {'input_tokens': 100}})
    with Store(':memory:') as store:
        async with HTTP(store, rate=0, max_requests=2, prices={'jev': .042}, transport=httpx.MockTransport(handler)) as client:
            result = await client.request('POST', 'https://api.typesafe.ai/v1/systemone', provider='jev', json={'state': 'fixture'})
            assert result.status_code == 200
            await client.request('POST', 'https://api.typesafe.ai/v1/systemone', provider='jev', json={'state': 'fixture'})
            assert len(calls) == 2
            with pytest.raises(BudgetExceeded):
                await client.request('GET', 'https://example.com/new')
        usage = store.usage_summary()
        assert usage['cache_hits'] == 1
        assert usage['providers']['jev']['network_requests'] == 2


@pytest.mark.asyncio
async def test_unpriced_provider_cannot_bypass_cost_ceiling():
    with Store(':memory:') as store:
        async with HTTP(store, rate=0, max_cost=1, transport=httpx.MockTransport(lambda r: httpx.Response(200))) as client:
            with pytest.raises(BudgetExceeded, match='price'):
                await client.request('GET', 'https://example.com', provider='brave')


@pytest.mark.asyncio
async def test_web_404_is_available_for_robots_and_redirects_do_not_follow():
    seen = []
    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(404 if request.url.path == '/robots.txt' else 302,
                              headers={'Location': 'http://127.0.0.1/private'})
    with Store(':memory:') as store:
        async with HTTP(store, rate=0, transport=httpx.MockTransport(handler)) as client:
            assert (await client.request('GET', 'https://example.com/robots.txt')).status_code == 404
            assert (await client.request('GET', 'https://example.com/')).status_code == 302
    assert len(seen) == 2


@pytest.mark.asyncio
async def test_error_response_is_not_cached():
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(401)
    with Store(':memory:') as store:
        async with HTTP(store, rate=0, transport=httpx.MockTransport(handler)) as client:
            for _ in range(2):
                with pytest.raises(httpx.HTTPStatusError):
                    await client.request('GET', 'https://example.com', provider='brave')
    assert len(calls) == 2
