import hashlib
import json
import uuid
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class ScraperTask:
    id: UUID = field(default_factory=lambda: uuid.uuid4())

    kind: str = "default"
    query: Any = None

    def spawn(self, **overrides: Any) -> ScraperTask:
        if "id" in overrides:
            raise ValueError("A spawned task always receives a new id")
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
