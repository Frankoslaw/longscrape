from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as error:
        raise TypeError(
            "query must be JSON-serializable to use the default cache"
        ) from error


@dataclass(frozen=True)
class FetchRequest:
    id: UUID = field(default_factory=lambda: uuid.uuid4(), kw_only=True)

    kind: str = "default"
    query: Any = None

    def spawn(self, **overrides: Any) -> FetchRequest:
        if "id" in overrides:
            raise ValueError("A spawned request always receives a new id")
        return replace(self, id=uuid.uuid4(), **overrides)

    @property
    def hash(self) -> str:
        encoded_payload = _canonical_json(
            {"kind": self.kind, "query": self.query}
        ).encode("utf-8")
        return hashlib.sha256(encoded_payload).hexdigest()


# Compatibility name for existing fetcher and extractor implementations.
ScraperTask = FetchRequest


@dataclass(frozen=True)
class RawEntry:
    url: str
    content: str | bytes
    content_type: str = "text/html"
    status_code: int = 200

    id: UUID = field(default_factory=lambda: uuid.uuid4())
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    # Preserve the input context with the source so it can be extracted again
    # after being loaded from a raw-entry store.
    kind: str = "default"
    query: Any = None

    @property
    def text(self) -> str:
        """Return content as text, decoding byte responses as UTF-8."""
        if isinstance(self.content, bytes):
            return self.content.decode("utf-8", errors="replace")
        return self.content


@dataclass(frozen=True)
class RawInput:
    raw_entry: RawEntry
    id: UUID = field(default_factory=lambda: uuid.uuid4(), kw_only=True)

    kind: str = "default"
    query: Any = None

    def spawn(self, **overrides: Any) -> RawInput:
        if "id" in overrides:
            raise ValueError("A spawned input always receives a new id")
        return replace(self, id=uuid.uuid4(), **overrides)

    @classmethod
    def from_raw_entry(cls, raw_entry: RawEntry) -> RawInput:
        """Create an input that restores the context saved with an entry."""
        return cls(raw_entry=raw_entry, kind=raw_entry.kind, query=raw_entry.query)


type PipelineInput = FetchRequest | RawInput


@dataclass(frozen=True)
class RichEntry[T]:
    url: str
    data: T

    scraped_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class ExtractionResult[T]:
    items: list[RichEntry[T]]
    tasks: Sequence[PipelineInput]

    @property
    def inputs(self) -> Sequence[PipelineInput]:
        return self.tasks


@dataclass(frozen=True)
class CachePolicy:
    read: bool = True
    write: bool = True
    max_age: timedelta | None = None

    @classmethod
    def use(cls) -> CachePolicy:
        return cls()

    @classmethod
    def refresh(cls) -> CachePolicy:
        return cls(read=False, write=True)

    @classmethod
    def bypass(cls) -> CachePolicy:
        return cls(read=False, write=False)

    @classmethod
    def ttl(cls, **timedelta_kwargs: float) -> CachePolicy:
        max_age = timedelta(**timedelta_kwargs)
        if max_age <= timedelta():
            raise ValueError("cache TTL must be greater than zero")
        return cls(max_age=max_age)
