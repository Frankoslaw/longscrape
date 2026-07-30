from longscrape.core.domain.pipeline import ExtractionResult, ScraperTask
from longscrape.core.ports.pipeline import ExtractorPort, FetcherPort, RawEntryStore
from longscrape.core.ports.ratelimit import RateLimiter
from longscrape.logging import get_logger

logger = get_logger(__name__)


class ScraperWorker[T]:
    def __init__(
        self,
        fetcher: FetcherPort,
        extractor: ExtractorPort[T],
        *,
        task_kind: str | None = None,
        rate_limiter: RateLimiter | None = None,
        raw_entry_store: RawEntryStore | None = None,
    ):
        self.fetcher = fetcher
        self.extractor = extractor
        self.base_domain = fetcher.get_base_domain()
        if not self.base_domain:
            raise ValueError("base_domain must not be empty")
        self.task_kind = task_kind
        self.rate_limiter = rate_limiter
        self.raw_entry_store = raw_entry_store

    def is_compatible(self, task: ScraperTask) -> bool:
        return self.task_kind is None or task.kind == self.task_kind

    async def run(self, task: ScraperTask) -> ExtractionResult[T]:
        if not self.is_compatible(task):
            logger.error("task rejected: id=%s kind=%s", task.id, task.kind)
            raise ValueError(f"Worker incompatible with task: {task.kind}")

        logger.info("task started: id=%s kind=%s", task.id, task.kind)
        raw_entry = None
        if self.raw_entry_store is not None:
            try:
                raw_entry = await self.raw_entry_store.get(task.hash)
            except Exception:
                logger.exception(
                    "raw entry lookup failed: id=%s kind=%s", task.id, task.kind
                )
                raise

        if raw_entry is None:
            try:
                if self.rate_limiter is not None:
                    await self.rate_limiter.acquire(self.base_domain)
                logger.debug("fetching task: id=%s", task.id)
                raw_entry = await self.fetcher.fetch(task)
                if self.raw_entry_store is not None:
                    await self.raw_entry_store.put(task.hash, raw_entry)
            except Exception:
                logger.exception("fetch failed: id=%s kind=%s", task.id, task.kind)
                raise
        else:
            logger.info("raw entry cache hit: id=%s kind=%s", task.id, task.kind)

        logger.info(
            "fetch complete: id=%s status=%s url=%s",
            task.id,
            raw_entry.status_code,
            raw_entry.url,
        )
        if not self.extractor.is_compatible(raw_entry):
            logger.error("entry rejected: id=%s url=%s", task.id, raw_entry.url)
            raise ValueError(f"Extractor incompatible with URL: {raw_entry.url}")

        try:
            logger.debug("extracting entry: id=%s url=%s", task.id, raw_entry.url)
            extraction = await self.extractor.extract(task, raw_entry)
        except Exception:
            logger.exception("extraction failed: id=%s url=%s", task.id, raw_entry.url)
            raise

        logger.info(
            "task complete: id=%s items=%d tasks=%d",
            task.id,
            len(extraction.items),
            len(extraction.tasks),
        )
        return extraction
