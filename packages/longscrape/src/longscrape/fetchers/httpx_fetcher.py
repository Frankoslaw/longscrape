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


class HttpxFetcher(Fetcher):
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
