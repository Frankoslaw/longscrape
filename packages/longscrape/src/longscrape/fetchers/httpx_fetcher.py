from collections.abc import AsyncIterator

import httpx
from longscrape_core import (
    Document,
    Fetcher,
    FetchFailure,
    FetchFailureKind,
    InputUrl,
    Job,
    PipelineContext,
    RetryableFetchFailure,
)


class HttpxFetcher(Fetcher):
    def __init__(self, http: httpx.AsyncClient):
        self._http = http

    async def fetch(
        self, job: Job, context: PipelineContext | None = None
    ) -> AsyncIterator[Document]:
        if not isinstance(job.input, InputUrl):
            raise FetchFailure(
                FetchFailureKind.INVALID_INPUT,
                "HttpxFetcher requires an InputUrl input",
            )

        try:
            response = await self._http.get(job.input.url)
        except httpx.TimeoutException as error:
            raise RetryableFetchFailure(
                FetchFailureKind.TIMEOUT,
                str(error),
                url=job.input.url,
                cause=error,
            ) from error
        except httpx.RequestError as error:
            raise RetryableFetchFailure(
                FetchFailureKind.NETWORK,
                str(error),
                url=job.input.url,
                cause=error,
            ) from error

        if response.status_code >= 500:
            raise RetryableFetchFailure(
                FetchFailureKind.HTTP_STATUS,
                f"HTTP request failed with status {response.status_code}",
                url=str(response.url),
                status=response.status_code,
            )
        if response.status_code >= 400:
            raise FetchFailure(
                FetchFailureKind.HTTP_STATUS,
                f"HTTP request failed with status {response.status_code}",
                url=str(response.url),
                status=response.status_code,
            )

        # noinspection PyTypeChecker
        yield Document(
            url=str(response.url),
            content=response.content,
            content_type=response.headers.get("content-type", "text/html"),
            headers=dict(response.headers),
            status=response.status_code,
        )
