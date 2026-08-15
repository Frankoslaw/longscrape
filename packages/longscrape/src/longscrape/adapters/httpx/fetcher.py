from typing import AsyncIterable

import httpx
from longscrape_core import (
    DISCARD_SUBMITTER,
    Document,
    Fetcher,
    InputUrl,
    Job,
    JobSubmitter,
)

from longscrape.adapters.httpx.httpx import HttpxManager
from longscrape.core.domain.pipeline import RawEntry, ScraperTask


class NewHttpxFetcher(Fetcher):
    def __init__(self, http: httpx.AsyncClient):
        self._http = http

    async def fetch(
        self, job: Job, submitter: JobSubmitter = DISCARD_SUBMITTER
    ) -> AsyncIterable[Document]:
        if not isinstance(job.input, InputUrl):
            raise TypeError("NewHttpxFetcher requires an InputUrl input")

        response = await self._http.get(job.input.url)
        if response.status_code != 200:
            raise RuntimeError(
                f"HTTP request failed with status {response.status_code}"
            )

        # noinspection PyTypeChecker
        yield Document(
            url=str(response.url),
            content=response.content,
            headers=dict(response.headers),
            status=response.status_code,
        )


class HttpxFetcher:
    """Fetch URL tasks through :class:`HttpxManager`."""

    def __init__(
        self,
        http: HttpxManager,
        base_domain: str,
        *,
        raise_for_status: bool = True,
    ) -> None:
        if not base_domain:
            raise ValueError("base_domain must not be empty")
        self._http = http
        self._base_domain = base_domain
        self._raise_for_status = raise_for_status

    def get_base_domain(self) -> str:
        return self._base_domain

    async def fetch(self, task: ScraperTask) -> RawEntry:
        if not isinstance(task.query, str):
            raise TypeError("HttpxFetcher requires a URL string query")
        response = await self._http.get(task.query)
        if self._raise_for_status:
            response.raise_for_status()
        return RawEntry(
            url=str(response.url),
            content=response.text,
            content_type=response.headers.get("content-type", "text/html"),
            status_code=response.status_code,
        )
