from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, TypeAlias
from uuid import UUID, uuid4

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


@dataclass(frozen=True)
class InputUrl:
    url: str

    def __post_init__(self) -> None:
        if not self.url.strip():
            raise ValueError("InputUrl.url must not be blank")


@dataclass(frozen=True)
class InputQuery:
    value: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.value, dict):
            raise TypeError("InputQuery.value must be an object")


@dataclass(frozen=True)
class Document:
    """Source content that can be passed directly to an extractor."""

    url: str
    content: bytes
    content_type: str = "text/html"
    status: int = 200
    headers: dict[str, str] = field(default_factory=dict)
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.url.strip():
            raise ValueError("Document.url must not be blank")
        if not self.content_type.strip():
            raise ValueError("Document.content_type must not be blank")

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")


@dataclass(frozen=True)
class InputDocument:
    """A job whose source content is already available in memory."""

    document: Document


type JobInput = InputUrl | InputQuery | InputDocument


@dataclass(frozen=True)
class Job:
    """An initial unit of work supplied to an application-owned loop."""

    kind: str
    input: JobInput
    context: dict[str, JsonValue] = field(default_factory=dict)
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not self.kind.strip():
            raise ValueError("Job.kind must not be blank")


@dataclass(frozen=True)
class Record:
    """Structured data emitted by an extractor or transformer."""

    kind: str
    data: dict[str, Any]
    source_url: str
    document: Document | None = None
    metadata: dict[str, JsonValue] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.kind.strip():
            raise ValueError("Record.kind must not be blank")
        if not self.source_url.strip():
            raise ValueError("Record.source_url must not be blank")
