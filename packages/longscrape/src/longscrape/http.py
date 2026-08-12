from __future__ import annotations

from typing import Any

import httpx
from longscrape_core import Document, InputUrl, Job


class HttpxFetcher:
    """Fetch :class:`InputUrl` jobs with an injected or owned HTTPX client."""

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        *,
        raise_for_status: bool = True,
        **client_kwargs: Any,
    ) -> None:
        self._client = client
        self._owns_client = client is None
        self._client_kwargs = client_kwargs
        self._raise_for_status = raise_for_status

    async def start(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient(
                follow_redirects=True, **self._client_kwargs
            )

    async def stop(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "HttpxFetcher":
        await self.start()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.stop()

    async def fetch(self, job: Job) -> Document:
        if not isinstance(job.input, InputUrl):
            raise TypeError("HttpxFetcher requires Job.input to be InputUrl")
        await self.start()
        if self._client is None:
            raise RuntimeError("HTTPX client failed to start")
        response = await self._client.get(job.input.url)
        if self._raise_for_status:
            response.raise_for_status()
        return Document(
            url=str(response.url),
            content=response.content,
            content_type=response.headers.get("content-type", "text/html"),
            status=response.status_code,
            headers=dict(response.headers),
        )
