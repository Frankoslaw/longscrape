from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime

import httpx
from longscrape_core import (
    Document,
    Fetcher,
    HttpStatusError,
    InputUrl,
    Job,
    PipelineContext,
)


class HttpxFetcher(Fetcher):
    def __init__(self, http: httpx.AsyncClient):
        self._http = http

    async def fetch(
        self, job: Job, context: PipelineContext | None = None
    ) -> Document:
        if not isinstance(job.input, InputUrl):
            raise TypeError("HttpxFetcher requires an InputUrl input")

        response = await self._http.get(job.input.url)
        if response.status_code >= 400:
            raise HttpStatusError(
                url=str(response.url),
                status=response.status_code,
                retry_after=(
                    _retry_after(response) if response.status_code == 429 else None
                ),
            )

        # noinspection PyTypeChecker
        return Document(
            url=str(response.url),
            content=response.content,
            content_type=response.headers.get("content-type", "text/html"),
            headers=dict(response.headers),
            status=response.status_code,
        )


def _retry_after(response: httpx.Response) -> timedelta | None:
    value = response.headers.get("retry-after")
    if value is None:
        return None
    try:
        seconds = float(value)
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
        except TypeError, ValueError:
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=UTC)
        seconds = (retry_at - datetime.now(UTC)).total_seconds()
    return timedelta(seconds=max(seconds, 0))
