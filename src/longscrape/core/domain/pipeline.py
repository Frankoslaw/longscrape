from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class ScraperTask:
    id: UUID = field(default_factory=lambda: uuid.uuid4(), kw_only=True)

    kind: str = "default"
    query: Any = None
    # TODO: This api requires improvement (for the future)
    cache_key: str | None = None
    _cache_key_explicit: bool = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Use the task identity for caching unless the caller supplies a key."""
        object.__setattr__(self, "_cache_key_explicit", self.cache_key is not None)
        if self.cache_key is None:
            object.__setattr__(self, "cache_key", self.hash)
        elif not self.cache_key:
            raise ValueError("cache_key must not be empty")

    def spawn(self, **overrides: Any) -> ScraperTask:
        if "id" in overrides:
            raise ValueError("A spawned task always receives a new id")
        # Derived keys follow changed task data; an explicitly supplied key is an
        # intentional cache-sharing choice and is inherited by child tasks.
        if not self._cache_key_explicit:
            overrides.setdefault("cache_key", None)
        return replace(self, id=uuid.uuid4(), **overrides)

    @property
    def hash(self) -> str:
        hash_payload = {"kind": self.kind, "query": self.query}

        encoded_payload = json.dumps(hash_payload, sort_keys=True, default=str).encode(
            "utf-8"
        )
        return hashlib.sha256(encoded_payload).hexdigest()


@dataclass(frozen=True)
class RawEntry:
    url: str
    content: str
    content_type: str = "text/html"
    status_code: int = 200

    id: UUID = field(default_factory=lambda: uuid.uuid4())
    task_hash: str | None = None

    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class RichEntry[T]:
    url: str
    data: T

    scraped_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class ExtractionResult[T]:
    items: list[RichEntry[T]]
    tasks: list[ScraperTask]


@dataclass(frozen=True)
class CachePolicy:
    """Controls whether a worker reads and writes its raw-entry cache."""

    read: bool = True
    write: bool = True
    max_age: timedelta | None = None

    @classmethod
    def use(cls) -> CachePolicy:
        return cls()

    @classmethod
    def refresh(cls) -> CachePolicy:
        """Fetch again, then replace the cached entry."""
        return cls(read=False, write=True)

    @classmethod
    def bypass(cls) -> CachePolicy:
        """Fetch without reading or changing the cache."""
        return cls(read=False, write=False)

    @classmethod
    def ttl(cls, **timedelta_kwargs: float) -> CachePolicy:
        """Reuse entries only while their fetch time is within the given TTL."""
        max_age = timedelta(**timedelta_kwargs)
        if max_age <= timedelta():
            raise ValueError("cache TTL must be greater than zero")
        return cls(max_age=max_age)
