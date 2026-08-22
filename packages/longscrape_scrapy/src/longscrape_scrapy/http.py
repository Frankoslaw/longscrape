from __future__ import annotations

import scrapy
from longscrape import Document, Fetcher, Job, PipelineContext
from scrapy.http import HtmlResponse, Response

FETCH_URL = "longscrape://fetch"


class LongscrapeRequest(scrapy.Request):
    """The internal request which maps one longscrape fetch to ``parse``."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(FETCH_URL, *args, dont_filter=True, **kwargs)


class LongscrapeResponse(HtmlResponse):
    pass


class FetcherCardinalityError(RuntimeError):
    pass


async def one_document(
    fetcher: Fetcher, job: Job, context: PipelineContext
) -> Document:
    """Resolve the deliberately narrow Fetcher-to-Scrapy boundary."""
    return await fetcher.fetch(job, context)


def document_to_response(document: Document, request: scrapy.Request) -> Response:
    response_class = (
        HtmlResponse if "html" in document.content_type.lower() else Response
    )
    return response_class(
        url=document.url,
        status=document.status,
        # HTTPX decodes compressed response bodies before creating Document.
        # Do not let Scrapy's HttpCompressionMiddleware attempt to decode the
        # already-decoded body a second time.
        headers={
            key: value
            for key, value in document.headers.items()
            if key.lower() not in {"content-encoding", "content-length"}
        },
        body=document.content,
        request=request,
    )


def response_to_document(response: Response) -> Document:
    headers: dict[str, str] = {
        key if isinstance(key, str) else key.decode("latin-1"): value
        if isinstance(value, str)
        else value.decode("latin-1")
        for key, value in response.headers.to_unicode_dict().items()
    }
    content_type = headers.get("Content-Type", "text/html")
    return Document(
        url=response.url,
        content=response.body,
        content_type=content_type,
        status=response.status,
        headers=headers,
    )


class LongscrapeFetcherMiddleware:
    """Turn the spider-scoped Fetcher into a normal Scrapy response."""

    def __init__(self, crawler) -> None:
        self._crawler = crawler

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)

    async def process_request(self, request: scrapy.Request) -> Response | None:
        if request.url != FETCH_URL:
            return None
        spider = self._crawler.spider
        fetcher = getattr(spider, "fetcher", None)
        job = getattr(spider, "job", None)
        context = getattr(spider, "context", None)
        if fetcher is None or job is None or context is None:
            raise RuntimeError(
                "Longscrape fetch request has no configured job and fetcher"
            )
        return document_to_response(await one_document(fetcher, job, context), request)
