from __future__ import annotations

from collections.abc import AsyncIterator
from functools import wraps
from typing import Any

import scrapy
from longscrape import Extractor, Fetcher, Job, PipelineContext
from scrapy.http import Response

from longscrape_scrapy.http import LongscrapeRequest, response_to_document
from longscrape_scrapy.items import item_from_record


def job_only(method):
    """Run a spider async-generator method only for a routed longscrape job."""

    @wraps(method)
    async def wrapped(self: "LongscrapeSpider", *args: Any, **kwargs: Any):
        if self.job is None:
            self.logger.warning(
                "%s requires a longscrape job; skipping %s",
                self.name,
                method.__name__,
            )
            return
        async for output in method(self, *args, **kwargs):
            yield output

    return wrapped


class LongscrapeSpider(scrapy.Spider):
    """A normal spider with optional registered longscrape stages.

    Set ``fetcher`` and ``extractor`` as class attributes or in ``__init__``.
    The runner injects the job and context once; the default ``start`` and
    ``parse`` then adapt those stages to Scrapy.  Subclasses may override
    either method normally when they need custom Scrapy behaviour.
    """

    fetcher: Fetcher | None = None
    extractor: Extractor[Any] | None = None

    def __init__(
        self,
        *args: Any,
        longscrape_job: Job | None = None,
        longscrape_context: PipelineContext | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.job = longscrape_job
        self.context = longscrape_context

    async def start(self) -> AsyncIterator[Any]:
        if self.fetcher is None:
            async for result in super().start():
                yield result
            return
        if self.job is None or self.context is None:
            self.logger.warning("Longscrape fetcher requires a runner-injected job")
            return
        yield LongscrapeRequest(callback=self.parse)

    async def parse(self, response: Response) -> AsyncIterator[dict[str, Any]]:
        if self.extractor is None:
            return
        if self.job is None or self.context is None:
            self.logger.warning("Longscrape extractor requires a runner-injected job")
            return
        document = response_to_document(response)

        async for record in self.extractor.extract(document, self.job, self.context):
            yield item_from_record(record)
