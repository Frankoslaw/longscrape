from collections.abc import Mapping
from typing import Any

import httpx


class HttpxManager:
    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        *,
        headers: Mapping[str, str] | None = None,
        timeout: float | None = 30.0,
    ):
        self._client = client
        self._owns_client = client is None
        self._headers = headers
        self._timeout = timeout

    async def start(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient(
                follow_redirects=True,
                headers=self._headers,
                timeout=self._timeout,
            )

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        if self._client is None:
            raise RuntimeError("HTTP client is not initialized. Call start() first.")
        return await self._client.request(method, url, **kwargs)

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("GET", url, **kwargs)

    async def stop(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None
