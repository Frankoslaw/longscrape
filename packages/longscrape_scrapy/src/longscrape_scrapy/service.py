from __future__ import annotations

import asyncio

from longscrape_core import CrawlJob, JobQueue, RecordSink
from scrapy.crawler import AsyncCrawlerProcess, AsyncCrawlerRunner, Crawler
from scrapy.settings import Settings
from scrapy.utils.project import get_project_settings

from longscrape_scrapy.spider import JobSpider

_RECORD_SINK_PIPELINE = "longscrape_scrapy.pipeline.RecordSinkPipeline"


class CrawlService:
    """A queue scheduler that runs complete Scrapy project crawls.

    Jobs are resolved by ``CrawlJob.kind`` through the project's spider loader,
    exactly as with ``scrapy crawl``. Each crawler is built from project
    settings, retaining Scrapy's middleware, extensions, pipelines and feeds.
    """

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
        record_sink: RecordSink | None = None,
        concurrency: int = 1,
        idle_delay: float = 1.0,
    ) -> "CrawlService":
        """Create a service with the settings used by ``scrapy crawl``.

        Set ``SCRAPY_SETTINGS_MODULE`` before this call when ``settings`` is
        omitted. A supplied core sink adds this package's pipeline without
        replacing the project's existing pipeline configuration.
        """
        project_settings = (
            settings.copy() if settings is not None else get_project_settings()
        )
        if record_sink is not None:
            pipelines = project_settings.getdict("ITEM_PIPELINES")
            pipelines.setdefault(_RECORD_SINK_PIPELINE, 300)
            project_settings.set("ITEM_PIPELINES", pipelines, priority="cmdline")
            project_settings.set(
                "LONGSCRAPE_RECORD_SINK", record_sink, priority="cmdline"
            )
        # AsyncCrawlerRunner deliberately leaves reactor setup to its caller.
        # ``scrapy crawl`` uses CrawlerProcess.start(), which installs the
        # configured DNS resolver and sizes the reactor thread pool. Reuse the
        # process initializer here, but keep the application's asyncio loop.
        process = AsyncCrawlerProcess(project_settings)
        if process.settings.getbool("TWISTED_REACTOR_ENABLED"):
            process._setup_reactor(install_signal_handlers=False)  # noqa: SLF001
            # ``reactor.run()`` cannot be used because asyncio already owns
            # this thread. Starting the reactor is still required: it starts
            # Twisted's resolver and thread-pool lifecycle while the
            # AsyncioSelectorReactor delegates actual polling to asyncio.
            from twisted.internet import reactor

            if not reactor.running:
                reactor.startRunning(installSignalHandlers=False)
        return cls(
            queue,
            process,
            concurrency=concurrency,
            idle_delay=idle_delay,
        )

    async def run_once(self) -> bool:
        job = await self.queue.dequeue()
        if job is None:
            return False
        await self.run_job(job)
        return True

    async def run_job(self, job: CrawlJob) -> None:
        crawler = self.runner.create_crawler(job.kind)
        self._validate_job_spider(crawler, job)
        await self.runner.crawl(crawler, job=job)

    def _validate_job_spider(self, crawler: Crawler, job: CrawlJob) -> None:
        if not issubclass(crawler.spidercls, JobSpider):
            message = (
                f"Spider for job kind {job.kind!r} must inherit "
                "longscrape_scrapy.JobSpider"
            )
            raise TypeError(message)

    async def serve(self) -> None:
        """Poll with a fixed number of consumers running complete crawls."""
        try:
            async with asyncio.TaskGroup() as group:
                for _ in range(self.concurrency):
                    group.create_task(self._serve_one())
        except asyncio.CancelledError:
            # ``asyncio.run`` translates Ctrl+C into cancellation of the main
            # task. Stop all Scrapy crawlers before returning control to it.
            await self.shutdown()
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """Stop accepting jobs and gracefully close every active crawler."""
        if self._stopping.is_set():
            return
        self._stopping.set()
        await self.runner.stop()
        await self.runner.join()

    async def _serve_one(self) -> None:
        while not self._stopping.is_set():
            if not await self.run_once():
                await asyncio.sleep(self.idle_delay)
