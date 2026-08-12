from __future__ import annotations

import asyncio
import logging

import scrapy.signals
from longscrape_core import Job, JobQueue, RecordStore, Transformer
from scrapy.crawler import AsyncCrawlerRunner, Crawler
from scrapy.settings import Settings
from scrapy.utils.project import get_project_settings

from longscrape_scrapy.spider import JobSpider

logger = logging.getLogger(__name__)

_LONGSCRAPE_PIPELINE = "longscrape_scrapy.pipeline.LongscrapePipeline"


class CrawlService:
    def __init__(
        self,
        queue: JobQueue,
        runner: AsyncCrawlerRunner,
        *,
        concurrency: int = 1,
        idle_delay: float = 1.0,
    ) -> None:
        if concurrency < 1:
            raise ValueError("concurrency must be at least one")
        if idle_delay <= 0:
            raise ValueError("idle_delay must be greater than zero")

        self.queue = queue
        self.runner = runner
        self.concurrency = concurrency
        self.idle_delay = idle_delay
        self._stopping = asyncio.Event()

    @classmethod
    def from_project(
        cls,
        queue: JobQueue,
        *,
        settings: Settings | None = None,
        record_store: RecordStore | None = None,
        transformers: list[Transformer] | None = None,
        concurrency: int = 1,
        idle_delay: float = 1.0,
    ) -> "CrawlService":
        project_settings = (
            settings.copy() if settings is not None else get_project_settings()
        )

        project_settings.set("TWISTED_REACTOR_ENABLED", False, priority="cmdline")

        if record_store is not None:
            pipelines = project_settings.getdict("ITEM_PIPELINES")
            pipelines.setdefault(_LONGSCRAPE_PIPELINE, 300)
            project_settings.set("ITEM_PIPELINES", pipelines, priority="cmdline")
            project_settings.set(
                "LONGSCRAPE_RECORD_STORE", record_store, priority="cmdline"
            )
            project_settings.set(
                "LONGSCRAPE_TRANSFORMERS", transformers or [], priority="cmdline"
            )

        runner = AsyncCrawlerRunner(project_settings)

        return cls(
            queue,
            runner,
            concurrency=concurrency,
            idle_delay=idle_delay,
        )

    async def run_once(self, kind: str) -> bool:
        job = await self.queue.dequeue(kind)
        if job is None:
            return False

        try:
            await self.run_job(job)
            await self.queue.mark_completed(job)
        except Exception as exc:
            logger.exception("Job execution failed: %s", job)
            await self.queue.mark_failed(job, error=exc)

        return True

    async def run_job(self, job: Job) -> None:
        crawler = self.runner.create_crawler(job.kind)
        self._validate_job_spider(crawler, job)

        spider_errors: list[Exception] = []

        def _handle_spider_error(failure, response, spider):
            # Extract the underlying Python exception from Twisted's Failure wrapper
            exc = failure.value if hasattr(failure, "value") else failure
            spider_errors.append(exc)

        crawler.signals.connect(
            _handle_spider_error, signal=scrapy.signals.spider_error
        )

        await self.runner.crawl(crawler, job=job)

        if spider_errors:
            raise spider_errors[0]

        finish_reason = (
            crawler.stats.get_value("finish_reason") if crawler.stats else None
        )
        if finish_reason and finish_reason != "finished":
            raise RuntimeError(f"Spider aborted with finish_reason: {finish_reason!r}")

    def _validate_job_spider(self, crawler: Crawler, job: Job) -> None:
        if not issubclass(crawler.spidercls, JobSpider):
            raise TypeError(
                f"Spider for kind {job.kind!r} ({crawler.spidercls.__name__}) "
                "must inherit longscrape_scrapy.JobSpider"
            )

    async def serve(self, kinds: tuple[str, ...]) -> None:
        if not kinds:
            raise ValueError("kinds must not be empty")
        try:
            async with asyncio.TaskGroup() as group:
                for _ in range(self.concurrency):
                    group.create_task(self._worker(kinds))
        except asyncio.CancelledError:
            await self.shutdown()
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        if self._stopping.is_set():
            return
        self._stopping.set()

        await self.runner.stop()

    async def _worker(self, kinds: tuple[str, ...]) -> None:
        while not self._stopping.is_set():
            ran_job = False
            for kind in kinds:
                ran_job = await self.run_once(kind) or ran_job
            if not ran_job:
                await asyncio.sleep(self.idle_delay)
