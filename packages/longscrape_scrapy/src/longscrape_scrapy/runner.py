from __future__ import annotations

import warnings
from collections.abc import Mapping
from typing import Any

from longscrape_core import Job, PipelineContext
from scrapy.crawler import AsyncCrawlerProcess
from scrapy.settings import Settings
from scrapy.utils.project import get_project_settings

from longscrape_scrapy.spider import LongscrapeSpider


class ScrapyJobRunner:
    """Run one durable longscrape job through one project-aware crawler."""

    def __init__(self, settings: Settings | Mapping[str, Any]) -> None:
        self._settings = Settings(settings)
        if self._settings.getbool("TWISTED_REACTOR_ENABLED"):
            warnings.warn(
                "Longscrape Scrapy jobs require TWISTED_REACTOR_ENABLED=False; "
                "the runner is disabling it. Reactor-dependent Scrapy features "
                "and third-party integrations, including the Telnet console and "
                "some download handlers, may be unavailable.",
                RuntimeWarning,
                stacklevel=2,
            )
        self._settings.set("TWISTED_REACTOR_ENABLED", False, priority="cmdline")
        downloader_middlewares = dict(self._settings.getdict("DOWNLOADER_MIDDLEWARES"))
        downloader_middlewares.setdefault(
            "longscrape_scrapy.http.LongscrapeFetcherMiddleware", 50
        )
        self._settings.set(
            "DOWNLOADER_MIDDLEWARES", downloader_middlewares, priority="cmdline"
        )

    @classmethod
    def from_scrapy_project(cls) -> "ScrapyJobRunner":
        """Load the active Scrapy project's settings and extend them safely."""
        return cls(get_project_settings())

    async def run(
        self,
        spider: type[LongscrapeSpider],
        job: Job,
        context: PipelineContext,
    ) -> None:
        process = AsyncCrawlerProcess(self._settings, install_root_handler=False)
        await process.crawl(
            spider,
            longscrape_job=job,
            longscrape_context=context,
        )
