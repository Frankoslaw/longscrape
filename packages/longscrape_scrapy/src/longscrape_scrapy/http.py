from __future__ import annotations

from typing import Any

import scrapy
from longscrape_core import Document, Job
from scrapy.http import HtmlResponse, Response


class LongscrapeRequest(scrapy.Request):
    """A Scrapy request that retains the longscrape job that started it."""

    def __init__(
        self, url: str, *args: Any, job: Job | None = None, **kwargs: Any
    ) -> None:
        super().__init__(url, *args, **kwargs)
        self.job = job

    @classmethod
    def from_document(
        cls, job: Job, document: Document, **kwargs: Any
    ) -> "LongscrapeRequest":
        """Create the synthetic start request associated with a document job."""
        from longscrape_core import InputDocument

        if not isinstance(job.input, InputDocument):
            raise TypeError(
                "LongscrapeRequest.from_document requires an InputDocument job"
            )
        return cls(document.url, job=job, **kwargs)


class LongscrapeResponse(HtmlResponse):
    """An in-memory Scrapy response backed by a core document."""

    def __init__(self, document: Document, *, request: scrapy.Request) -> None:
        super().__init__(
            url=document.url,
            status=document.status,
            headers=document.headers,
            body=document.content,
            encoding="utf-8",
            request=request,
        )
        self.document = document

    @classmethod
    def from_document(
        cls, document: Document, *, request: scrapy.Request
    ) -> "LongscrapeResponse":
        return cls(document, request=request)

    @classmethod
    def from_response(cls, response: Response) -> "LongscrapeResponse":
        content_type = response.headers.get("Content-Type", b"text/html")
        if isinstance(content_type, list):
            content_type = content_type[0] if content_type else b"text/html"
        content_type_text = (
            content_type.decode() if isinstance(content_type, bytes) else "text/html"
        )
        headers: dict[str, str] = {}
        for key, value in response.headers.items():
            if isinstance(value, list):
                value = value[0] if value else b""
            if isinstance(key, bytes) and isinstance(value, bytes):
                headers[key.decode()] = value.decode()
        return cls(
            Document(
                url=response.url,
                content=response.body,
                content_type=content_type_text,
                status=response.status,
                headers=headers,
            ),
            request=response.request or scrapy.Request(response.url),
        )
