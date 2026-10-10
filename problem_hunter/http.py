"""Bounded, cached HTTP requests with per-provider quotas and sanitized accounting."""
import asyncio
import hashlib
import json
import logging
import time
import socket
import ipaddress
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

import httpx

log = logging.getLogger(__name__)


class BudgetExceeded(RuntimeError):
    pass


class HTTP:
    def __init__(self, store, concurrency=4, max_requests=200, rate=1.0,
                 max_cost=None, prices=None, transport=None, retries=2):
        self.store = store
        self.semaphore = asyncio.Semaphore(concurrency)
        self.max_requests = max_requests
        self.rate = rate
        self.max_cost = max_cost
        self.prices = prices or {}
        self.retries = retries
        self.requests = 0
        self.cost = 0.0
        self.phase = None
        self.locks = {}
        self.last = {}
        self.custom_transport = transport is not None
        self.client = httpx.AsyncClient(timeout=25, follow_redirects=False, transport=transport,
                                       trust_env=False,
                                       headers={"User-Agent": "ProblemHunter/0.1 (+research CLI)"})

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.client.aclose()

    async def request(self, method, url, provider="web", params=None, json=None, headers=None):
        phase = self.phase or ("evaluation" if provider == "jev" else "research" if provider == "llm" else "collection")
        # Cache identity includes a hash of credentials to isolate accounts, never raw keys.
        credential_scope = hashlib.sha256(str(sorted((headers or {}).items())).encode()).hexdigest()
        key = hashlib.sha256(__import__('json').dumps(
            [method, url, params, json, credential_scope], sort_keys=True).encode()).hexdigest()
        cached = self.store.cache_get(key)
        if cached:
            self.store.log_request(provider, url.split('?')[0], cached['status'], cached=True, phase=phase)
            return httpx.Response(cached['status'], headers=cached['headers'], content=cached['body'],
                                  request=httpx.Request(method, url))
        async with self.semaphore:
            for attempt in range(self.retries + 1):
                lock = self.locks.setdefault(provider, asyncio.Lock())
                async with lock:
                    delay = max(0, self.last.get(provider, 0) + self.rate - time.monotonic())
                    if delay:
                        await asyncio.sleep(delay)
                    if self.requests >= self.max_requests:
                        raise BudgetExceeded("Request limit reached; increase --max-requests to continue.")
                    price = self.prices.get(provider)
                    if self.max_cost is not None and price is None and provider in {'brave', 'jev', 'llm'}:
                        raise BudgetExceeded(f"No configured price for {provider}; cannot enforce a cost budget.")
                    reserve = (price or 0) if provider != 'jev' else (price or 0) * 100000 / 1000000
                    if self.max_cost is not None and self.cost + reserve > self.max_cost:
                        raise BudgetExceeded("Estimated cost budget reached.")
                    self.requests += 1
                    self.cost += reserve
                    self.last[provider] = time.monotonic()
                log.info("Request %s #%s", provider, self.requests)
                try:
                    wire_url, wire_headers, extensions = url, dict(headers or {}), {}
                    if provider == 'web' and not self.custom_transport:
                        # Connect to the checked address, avoiding a second DNS resolution
                        # between public-host validation and the socket connection.
                        parsed = httpx.URL(url)
                        addresses = await asyncio.to_thread(socket.getaddrinfo, parsed.host, parsed.port or
                                                            (443 if parsed.scheme == 'https' else 80),
                                                            type=socket.SOCK_STREAM)
                        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
                            raise ValueError('Non-public network destination prohibited')
                        wire_url = parsed.copy_with(host=addresses[0][4][0])
                        wire_headers['Host'] = parsed.netloc.decode()
                        extensions['sni_hostname'] = parsed.host
                    async with self.client.stream(method, wire_url, params=params, json=json, headers=wire_headers,
                                                  extensions=extensions) as response:
                        chunks = []
                        size = 0
                        async for chunk in response.aiter_bytes():
                            size += len(chunk)
                            if size > 2_000_000:
                                raise ValueError("Response exceeds 2 MB retrieval limit")
                            chunks.append(chunk)
                        body = b''.join(chunks)
                        decoded_headers = dict(response.headers)
                        # aiter_bytes already decompresses the payload. Replaying
                        # its encoding header would attempt decompression twice.
                        for header in ('content-encoding', 'content-length', 'transfer-encoding'):
                            decoded_headers.pop(header, None)
                        result = httpx.Response(response.status_code, headers=decoded_headers,
                                                content=body, request=response.request)
                    usage = None
                    if provider in {'jev', 'llm'} and result.is_success:
                        try:
                            payload = result.json()
                            usage = payload.get('usage') if isinstance(payload, dict) else None
                        except ValueError:
                            pass
                    cost = reserve
                    if provider == 'jev' and usage and price is not None:
                        cost = usage.get('input_tokens', 0) * price / 1000000
                        self.cost += cost - reserve
                    self.store.log_request(provider, url.split('?')[0], result.status_code, usage=usage,
                                           cost=cost if price is not None else 0 if provider not in {'brave', 'jev', 'llm'} else None, phase=phase)
                    if result.status_code in {429, 500, 502, 503, 504, 529} and attempt < self.retries:
                        retry = result.headers.get('retry-after', '')
                        try:
                            delay = float(retry)
                        except ValueError:
                            try:
                                delay = (parsedate_to_datetime(retry) - datetime.now(timezone.utc)).total_seconds()
                            except (ValueError, TypeError):
                                delay = 2 ** attempt
                        await asyncio.sleep(min(30, max(0, delay)))
                        continue
                    if provider != 'web':
                        result.raise_for_status()
                    if result.is_success or (provider == 'web' and result.status_code == 404):
                        self.store.cache_set(key, {'status': result.status_code,
                                              'headers': dict(result.headers), 'body': result.text})
                    return result
                except httpx.TransportError:
                    self.store.log_request(provider, url.split('?')[0], 0,
                                           cost=reserve if price is not None else 0 if provider not in {'brave', 'jev', 'llm'} else None, phase=phase)
                    if attempt == self.retries:
                        raise
                    await asyncio.sleep(2 ** attempt)
        raise RuntimeError("Request did not complete")
