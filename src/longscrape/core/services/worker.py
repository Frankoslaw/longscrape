from datetime import UTC, datetime

from longscrape.core.domain.pipeline import (
    CachePolicy,
    ExtractionResult,
    FetchRequest,
    PipelineInput,
    RawEntry,
    RawInput,
)
from longscrape.core.ports.pipeline import ExtractorPort, FetcherPort, RawEntryStore
from longscrape.core.ports.ratelimit import RateLimiter
from longscrape.logging import get_logger

logger = get_logger(__name__)


class RawEntryResolver:
    def __init__(
        self,
        fetcher: FetcherPort,
        *,
        rate_limiter: RateLimiter | None = None,
        rate_limit_key: str | None = None,
        raw_entry_store: RawEntryStore | None = None,
        cache_policy: CachePolicy | None = None,
    ) -> None:
        self.fetcher = fetcher
        self.base_domain = fetcher.get_base_domain()
        if not self.base_domain:
            raise ValueError("base_domain must not be empty")
        self.rate_limiter = rate_limiter
        self.rate_limit_key = rate_limit_key or self.base_domain
        self.raw_entry_store = raw_entry_store
        self.cache_policy = cache_policy or CachePolicy.use()

    def _cache_key(self, request: FetchRequest) -> str:
        return request.hash

    async def resolve(self, request: FetchRequest) -> RawEntry:
        cache_key = self._cache_key(request)
        raw_entry = None
        if self.raw_entry_store is not None and self.cache_policy.read:
            raw_entry = await self.raw_entry_store.get(cache_key)
            if raw_entry is not None and not self._is_fresh(raw_entry):
                raw_entry = None

        if raw_entry is not None:
            logger.info("raw entry cache hit: id=%s kind=%s", request.id, request.kind)
            return raw_entry

        if self.rate_limiter is not None:
            await self.rate_limiter.acquire(self.rate_limit_key)
        logger.debug("fetching request: id=%s", request.id)
        raw_entry = await self.fetcher.fetch(request)
        if self.raw_entry_store is not None and self.cache_policy.write:
            await self.raw_entry_store.put(cache_key, raw_entry)
        return raw_entry

    def _is_fresh(self, raw_entry: RawEntry) -> bool:
        if self.cache_policy.max_age is None:
            return True
        fetched_at = raw_entry.fetched_at
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=UTC)
        return datetime.now(UTC) - fetched_at <= self.cache_policy.max_age


class ExtractionWorker[T]:
    def __init__(
        self, extractor: ExtractorPort[T], *, task_kind: str | None = None
    ) -> None:
        self.extractor = extractor
        self.task_kind = task_kind

    async def run(
        self, input: PipelineInput, raw_entry: RawEntry
    ) -> ExtractionResult[T]:
        if self.task_kind is not None and input.kind != self.task_kind:
            raise ValueError(f"Worker incompatible with input: {input.kind}")
        if not self.extractor.is_compatible(raw_entry):
            raise ValueError(f"Extractor incompatible with URL: {raw_entry.url}")
        return await self.extractor.extract(input, raw_entry)


class ScraperWorker[T]:
    def __init__(
        self,
        fetcher: FetcherPort | None,
        extractor: ExtractorPort[T],
        *,
        task_kind: str | None = None,
        rate_limiter: RateLimiter | None = None,
        rate_limit_key: str | None = None,
        raw_entry_store: RawEntryStore | None = None,
        cache_policy: CachePolicy | None = None,
    ) -> None:
        self.resolver = (
            RawEntryResolver(
                fetcher,
                rate_limiter=rate_limiter,
                rate_limit_key=rate_limit_key,
                raw_entry_store=raw_entry_store,
                cache_policy=cache_policy,
            )
            if fetcher is not None
            else None
        )
        self.extractor = ExtractionWorker(extractor, task_kind=task_kind)

    async def run(self, input: PipelineInput) -> ExtractionResult[T]:
        logger.info("input started: id=%s kind=%s", input.id, input.kind)
        try:
            if isinstance(input, RawInput):
                raw_entry = input.raw_entry
            elif self.resolver is not None:
                raw_entry = await self.resolver.resolve(input)
            else:
                raise ValueError(f"No fetcher configured for input kind: {input.kind}")
            result = await self.extractor.run(input, raw_entry)
        except Exception:
            logger.exception("input failed: id=%s kind=%s", input.id, input.kind)
            raise
        logger.info(
            "input complete: id=%s items=%d inputs=%d",
            input.id,
            len(result.items),
            len(result.tasks),
        )
        return result
