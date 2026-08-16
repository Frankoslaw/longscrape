from __future__ import annotations

import hashlib
import json
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
    # TODO: context should probably not be a property of the job itself as the
    # fact that its even mutable currently is a error and some better mechanism
    # to pass context between stages in functional matter would be preferable
    context: dict[str, JsonValue] = field(default_factory=dict)
    id: uuid.UUID = field(default_factory=uuid.uuid4)

    @property
    def hash(self) -> str:
        payload = json.dumps(
            {"kind": self.kind, "input": self.input},
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    # TODO: add parent/spawn utility functionality which tracks both last parent
    # and root of the job tree


@dataclass(frozen=True)
class Document:
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

    @property
    def hash(self) -> str:
        payload = json.dumps(
            {"kind": self.kind, "data": self.data},
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
