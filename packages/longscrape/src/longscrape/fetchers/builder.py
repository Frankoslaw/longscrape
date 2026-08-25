from collections.abc import Callable
from datetime import timedelta

from longscrape.core import Fetcher, FetchInput
from longscrape.fetchers.cache import CachedFetcher
from longscrape.fetchers.handoff import FailureDetector, HandoffFetcher, HandoffResolver
from longscrape.fetchers.rate_limit import RateLimitedFetcher
from longscrape.fetchers.retry import RetryingFetcher
from longscrape.storage import DocumentStore
from longscrape.worker import RecoveryPolicy
from longscrape.worker.rate_limit import LeakyBucketRateLimiter


class FetcherBuilder:
    """Compose the built-in fetcher decorators around an explicit base fetcher."""

    def __init__(self) -> None:
        self._fetcher: Fetcher | None = None

    def base(self, fetcher: Fetcher) -> FetcherBuilder:
        if self._fetcher is not None:
            raise RuntimeError("a base fetcher or decorator is already configured")
        self._fetcher = fetcher
        return self

    def rate_limit(
        self,
        *,
        requests_per_second: float,
        capacity: int = 1,
        key: Callable[[FetchInput], str] | None = None,
    ) -> FetcherBuilder:
        kwargs = {"rate_limit_key": key} if key is not None else {}
        self._fetcher = RateLimitedFetcher(
            self._require_fetcher(),
            LeakyBucketRateLimiter(requests_per_second, capacity),
            **kwargs,
        )
        return self

    def cache(
        self,
        store: DocumentStore,
        *,
        key: Callable[[FetchInput], str] | None = None,
        read: bool = True,
        write: bool = True,
        max_age: timedelta | None = None,
    ) -> FetcherBuilder:
        kwargs = {"cache_key": key} if key is not None else {}
        self._fetcher = CachedFetcher(
            self._fetcher,
            store,
            read=read,
            write=write,
            max_age=max_age,
            **kwargs,
        )
        return self

    def handoff(
        self,
        *,
        detector: FailureDetector,
        handoff_strategy: HandoffResolver,
        policy: RecoveryPolicy | None = None,
        max_recoveries: int = 1,
    ) -> FetcherBuilder:
        self._fetcher = HandoffFetcher(
            self._require_fetcher(),
            policy=policy,
            detector=detector,
            handoff=handoff_strategy,
            max_recoveries=max_recoveries,
        )
        return self

    def retry(
        self,
        *,
        max_retries: int,
        policy: RecoveryPolicy | None = None,
    ) -> FetcherBuilder:
        self._fetcher = RetryingFetcher(
            self._require_fetcher(), policy=policy, max_retries=max_retries
        )
        return self

    def build(self) -> Fetcher:
        return self._require_fetcher()

    def _require_fetcher(self) -> Fetcher:
        if self._fetcher is None:
            raise RuntimeError("a base fetcher is required before this operation")
        return self._fetcher
