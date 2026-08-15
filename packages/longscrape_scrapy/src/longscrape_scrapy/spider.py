from __future__ import annotations

import inspect
from collections.abc import AsyncIterator, Iterable
from typing import Any

import scrapy
import scrapy.signals
from longscrape_core import DocumentStore, InputDocument, InputUrl, Job
from scrapy.crawler import Crawler
from scrapy.http import Response

from longscrape_scrapy.http import LongscrapeRequest, LongscrapeResponse
from longscrape_scrapy.runtime import resolve


class JobSpider(scrapy.Spider):
    """A Scrapy-compatible spider that optionally receives a core job."""

    job: Job | None

    def __init__(
        self,
        *args: Any,
        job: Job | None = None,
        document_store: DocumentStore | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.job = job
        self.document_store = document_store
        self.initial_url = self._initial_url(job)
        self.urls: list[str] = []
        if self.initial_url is not None:
            self._track_url(self.initial_url)

    @classmethod
    def from_crawler(cls, crawler: Crawler, *args: Any, **kwargs: Any) -> "JobSpider":
        spider = super().from_crawler(crawler, *args, **kwargs)
        store_key = crawler.settings.get("LONGSCRAPE_DOCUMENT_STORE_KEY")
        spider.document_store = resolve(store_key) if store_key else None
        crawler.signals.connect(
            spider._track_request, signal=scrapy.signals.request_scheduled
        )
        crawler.signals.connect(
            spider._track_response, signal=scrapy.signals.response_received
        )
        return spider

    async def start(self) -> AsyncIterator[Any]:
        if self.job is None:
            self.logger.warning(
                "No longscrape job was supplied; %s has no queued start input.",
                self.name,
            )
            return
        if isinstance(self.job.input, InputDocument):
            if self.document_store is None:
                raise ValueError("InputDocument jobs require LONGSCRAPE_DOCUMENT_STORE")
            document = await self.document_store.get(self.job.input.document_ref)
            if document is None:
                raise LookupError(f"Document not found: {self.job.input.document_ref}")
            request = LongscrapeRequest.from_document(
                self.job, document, callback=self.parse
            )
            self._track_request(request)
            response = LongscrapeResponse.from_document(document, request=request)
            self._track_response(response)
            async for value in self._callback_output(request.callback, response):
                yield value
            return
        async for value in self.start_job():
            yield value

    async def start_job(self) -> AsyncIterator[Any]:
        """Yield the initial Scrapy requests for an orchestrated job."""
        if False:
            yield None

    @staticmethod
    def _initial_url(job: Job | None) -> str | None:
        if job is None:
            return None
        if isinstance(job.input, InputUrl):
            return job.input.url
        return None

    def _track_url(self, url: str) -> None:
        if url not in self.urls:
            self.urls.append(url)

    def _track_request(self, request: scrapy.Request, **_: Any) -> None:
        self._track_url(request.url)

    def _track_response(self, response: Response, **_: Any) -> None:
        self._track_url(response.url)

    async def _callback_output(
        self, callback: Any, response: Response
    ) -> AsyncIterator[Any]:
        if callback is None:
            return
        result = callback(response)
        if inspect.isawaitable(result):
            result = await result
        if hasattr(result, "__aiter__"):
            async for value in result:
                yield value
        elif isinstance(result, Iterable) and not isinstance(
            result, (dict, scrapy.Item, scrapy.Request)
        ):
            for value in result:
                yield value
        elif result is not None:
            yield result
