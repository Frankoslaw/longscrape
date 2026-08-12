from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import scrapy
from longscrape_core import Job


class JobSpider(scrapy.Spider):
    """A Scrapy-compatible spider that optionally receives a core job."""

    job: Job | None

    def __init__(self, *args: Any, job: Job | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.job = job

    async def start(self) -> AsyncIterator[Any]:
        if self.job is None:
            self.logger.warning(
                "No longscrape job was supplied; %s has no queued start input.",
                self.name,
            )
            return
        async for value in self.start_job():
            yield value

    async def start_job(self) -> AsyncIterator[Any]:
        """Yield the initial Scrapy requests for an orchestrated job."""
        if False:
            yield None
