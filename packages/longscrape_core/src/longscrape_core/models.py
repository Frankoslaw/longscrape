"""Small immutable values shared by every longscrape use case."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Generic, TypeVar
from uuid import UUID, uuid4

from longscrape_core._json import JsonInput, freeze_json_object


@dataclass(frozen=True)
class InputUrl:
    url: str

    def __post_init__(self) -> None:
        if not self.url:
            raise ValueError("input URL must not be empty")


@dataclass(frozen=True)
class InputQuery:
    query: Mapping[str, JsonInput]

    def __post_init__(self) -> None:
        object.__setattr__(self, "query", freeze_json_object(self.query))


@dataclass(frozen=True)
class DocumentRef:
    """Serializable reference to a document retained by an archive."""

    store: str
    value: str

    def __post_init__(self) -> None:
        if not self.store:
            raise ValueError("document reference store must not be empty")
        if not self.value:
            raise ValueError("document reference value must not be empty")


@dataclass(frozen=True)
class Document:
    url: str
    content: bytes
    content_type: str = "text/html"
    status: int = 200
    headers: Mapping[str, str] = field(default_factory=dict)
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        object.__setattr__(self, "headers", MappingProxyType(dict(self.headers)))


@dataclass(frozen=True)
class InputDocument:
    """Job input for a document retained by an archive."""

    ref: DocumentRef


type JobInput = InputUrl | InputQuery | InputDocument


@dataclass(frozen=True)
class Job:
    """One unit of scraping intent, usable with or without a runtime."""

    kind: str
    input: JobInput
    metadata: Mapping[str, JsonInput] = field(default_factory=dict)
    id: UUID = field(default_factory=uuid4)
    parent_id: UUID | None = None
    root_id: UUID | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.kind:
            raise ValueError("job kind must not be empty")
        if self.root_id is None:
            object.__setattr__(self, "root_id", self.id)
        object.__setattr__(self, "metadata", freeze_json_object(self.metadata))

    def child(self, kind: str, input: JobInput, **metadata: JsonInput) -> "Job":
        """Create a child job while preserving root lineage."""
        return Job(kind, input, metadata, parent_id=self.id, root_id=self.root_id)


T = TypeVar("T")


@dataclass(frozen=True)
class Record(Generic[T]):
    """One extracted value; ``key`` is its optional stable store identity."""

    kind: str
    data: T
    key: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.kind:
            raise ValueError("record kind must not be empty")
        if self.key == "":
            raise ValueError("record key must not be empty")
