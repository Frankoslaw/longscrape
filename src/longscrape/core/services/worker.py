from datetime import UTC, datetime

from longscrape.core.domain.pipeline import (
    CachePolicy,
    ExtractionResult,
    RawEntry,
    ScraperTask,
)
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
        rate_limit_key: str | None = None,
        raw_entry_store: RawEntryStore | None = None,
        cache_policy: CachePolicy | None = None,
    ):
        self.fetcher = fetcher
        self.extractor = extractor
        self.base_domain = fetcher.get_base_domain()
        if not self.base_domain:
            raise ValueError("base_domain must not be empty")
        self.task_kind = task_kind
        self.rate_limiter = rate_limiter
        self.rate_limit_key = rate_limit_key or self.base_domain
        self.raw_entry_store = raw_entry_store
        self.cache_policy = cache_policy or CachePolicy.use()

    def is_compatible(self, task: ScraperTask) -> bool:
        return self.task_kind is None or task.kind == self.task_kind

    async def run(self, task: ScraperTask) -> ExtractionResult[T]:
        if not self.is_compatible(task):
            logger.error("task rejected: id=%s kind=%s", task.id, task.kind)
            raise ValueError(f"Worker incompatible with task: {task.kind}")

        logger.info("task started: id=%s kind=%s", task.id, task.kind)
        cache_key = task.cache_key
        assert cache_key is not None  # ScraperTask establishes this invariant.
        raw_entry = None
        if self.raw_entry_store is not None and self.cache_policy.read:
            try:
                raw_entry = await self.raw_entry_store.get(cache_key)
                if raw_entry is not None and not self._is_cache_entry_fresh(raw_entry):
                    raw_entry = None
            except Exception:
                logger.exception(
                    "raw entry lookup failed: id=%s kind=%s", task.id, task.kind
                )
                raise

        if raw_entry is None:
            try:
                if self.rate_limiter is not None:
                    await self.rate_limiter.acquire(self.rate_limit_key)
                logger.debug("fetching task: id=%s", task.id)
                raw_entry = await self.fetcher.fetch(task)
                if self.raw_entry_store is not None and self.cache_policy.write:
                    await self.raw_entry_store.put(cache_key, raw_entry)
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

    def _is_cache_entry_fresh(self, raw_entry: RawEntry) -> bool:
        if self.cache_policy.max_age is None:
            return True
        fetched_at = raw_entry.fetched_at
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=UTC)
        return datetime.now(UTC) - fetched_at <= self.cache_policy.max_age
