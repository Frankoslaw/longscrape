from __future__ import annotations

from collections.abc import AsyncIterator

import scrapy
from longscrape_core import InputDocument, InputQuery, InputUrl
from scrapy.http import Response

from longscrape_scrapy.http import LongscrapeRequest, LongscrapeResponse
from longscrape_scrapy.items import LongscrapeDocumentItem, LongscrapeRecordItem
from longscrape_scrapy.spider import JobSpider


class UrlCrawler(JobSpider):
    """Fetch an ``InputUrl`` job and emit its document as a Scrapy item."""

    name = "url"

    async def start_job(self) -> AsyncIterator[scrapy.Request]:
        if self.job is None or not isinstance(self.job.input, InputUrl):
            raise TypeError("UrlCrawler requires an InputUrl job")
        yield LongscrapeRequest(self.job.input.url, callback=self.parse, job=self.job)

    def parse(self, response: Response) -> LongscrapeDocumentItem:
        return LongscrapeDocumentItem.from_document(
            LongscrapeResponse.from_response(response).document
        )


class IdentityCrawler(JobSpider):
    """Emit a document or query job as one native Scrapy item."""

    name = "identity"

    def parse(self, response: Response) -> LongscrapeDocumentItem:
        """Return an in-memory document job through ``start()``."""
        document = (
            response.document
            if isinstance(response, LongscrapeResponse)
            else LongscrapeResponse.from_response(response).document
        )
        document_ref = (
            self.job.input.document_ref
            if self.job is not None and isinstance(self.job.input, InputDocument)
            else None
        )
        return LongscrapeDocumentItem.from_document(document, document_ref=document_ref)

    async def start_job(self) -> AsyncIterator[scrapy.Item]:
        if self.job is None:
            raise TypeError("IdentityCrawler requires a job")
        if isinstance(self.job.input, InputDocument):
            if self.document_store is None:
                raise ValueError("InputDocument jobs require LONGSCRAPE_DOCUMENT_STORE")
            document = await self.document_store.get(self.job.input.document_ref)
            if document is None:
                raise LookupError(f"Document not found: {self.job.input.document_ref}")
            yield LongscrapeDocumentItem.from_document(
                document, document_ref=self.job.input.document_ref
            )
            return
        if isinstance(self.job.input, InputQuery):
            yield LongscrapeRecordItem(
                kind=getattr(self, "record_kind", None) or self.name,
                source_url=f"longscrape://job/{self.job.id}",
                data=dict(self.job.input.value),
                metadata={
                    "producer": f"scrapy:{self.name}",
                    "job_id": str(self.job.id),
                },
            )
            return
        raise TypeError("IdentityCrawler requires an InputDocument or InputQuery job")
