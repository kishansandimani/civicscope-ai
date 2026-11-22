"""SSRF-safe HTTP fetching: every URL and every redirect hop is validated before a request is made."""
import asyncio
from typing import Callable
from urllib.parse import urljoin

import httpx

from app.services.fetch_types import FetchResult
from app.utils.url_safety import UnsafeURL, validate_public_url

USER_AGENT = "CivicScopeBot/0.1 (+public-information auditor; respectful, low-rate)"


class Fetcher:
    def __init__(self, timeout: float = 12.0, max_bytes: int = 5_000_000, max_redirects: int = 5,
                 validator: Callable[[str], str] = validate_public_url):
        self.timeout, self.max_bytes, self.max_redirects, self.validator = timeout, max_bytes, max_redirects, validator

    async def _request(self, method: str, url: str, read_body: bool) -> FetchResult:
        current, hops = url, 0
        async with httpx.AsyncClient(follow_redirects=False, timeout=self.timeout,
                                     headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/pdf,*/*;q=0.5"}) as client:
            while True:
                try:
                    current = await asyncio.to_thread(self.validator, current)
                except UnsafeURL as e:
                    return FetchResult(url, current, None, error=f"blocked: {e}", redirects=hops)
                try:
                    async with client.stream(method, current) as r:
                        if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
                            hops += 1
                            if hops > self.max_redirects:
                                return FetchResult(url, current, None, error="too many redirects", redirects=hops)
                            current = urljoin(current, r.headers["location"])
                            continue
                        body = b""
                        if read_body and method == "GET":
                            async for chunk in r.aiter_bytes():
                                body += chunk
                                if len(body) > self.max_bytes:
                                    body = body[: self.max_bytes]
                                    break
                        return FetchResult(url, current, r.status_code, r.headers.get("content-type", ""), body, None, hops)
                except httpx.TimeoutException:
                    return FetchResult(url, current, None, error="timeout", redirects=hops)
                except httpx.HTTPError:
                    return FetchResult(url, current, None, error="connection failed", redirects=hops)

    async def fetch(self, url: str) -> FetchResult:
        return await self._request("GET", url, read_body=True)

    async def check(self, url: str) -> FetchResult:
        """Lightweight link check: HEAD first; some servers reject HEAD, so retry with GET (body discarded)."""
        r = await self._request("HEAD", url, read_body=False)
        if r.status in (400, 403, 405, 501) or (r.status is None and r.error == "connection failed"):
            r2 = await self._request("GET", url, read_body=False)
            if r2.status is not None:
                return r2
        return r
