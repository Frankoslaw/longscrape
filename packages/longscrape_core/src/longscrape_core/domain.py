from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TypeAlias

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


@dataclass(frozen=True)
class InputUrl:
    url: str


@dataclass(frozen=True)
class InputQuery:
    query: dict[str, JsonValue]


@dataclass(frozen=True)
class InputDocument:
    document: Document


type JobInput = InputUrl | InputQuery | InputDocument


@dataclass(frozen=True)
class JobRequest:
    kind: str
    input: JobInput
    context: dict[str, JsonValue] = field(default_factory=dict)


@dataclass(frozen=True)
class Job:
    kind: str
    input: JobInput
    context: dict[str, JsonValue] = field(default_factory=dict)
    id: uuid.UUID = field(default_factory=uuid.uuid4)


@dataclass(frozen=True)
class Document:
    kind: str
    url: str
    content: bytes
    content_type: str = "text/html"
    status: int = 200
    headers: dict[str, str] = field(default_factory=dict)
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class Record:
    kind: str
    data: dict[str, JsonValue]
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
