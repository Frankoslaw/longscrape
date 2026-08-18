from __future__ import annotations

import hashlib
import json
import uuid
from base64 import b64encode
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType

from longscrape_core._json import (
    FrozenJsonValue,
    JsonValue,
    _freeze_json,
    _thaw_json,
)


@dataclass(frozen=True)
class InputUrl:
    url: str


@dataclass(frozen=True)
class InputQuery:
    query: Mapping[str, FrozenJsonValue]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "query",
            MappingProxyType(
                {key: _freeze_json(value) for key, value in self.query.items()}
            ),
        )


@dataclass(frozen=True)
class InputDocument:
    document: Document


type JobInput = InputUrl | InputQuery | InputDocument


@dataclass(frozen=True)
class JobRequest:
    kind: str
    input: JobInput
    metadata: Mapping[str, FrozenJsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "metadata",
            MappingProxyType(
                {key: _freeze_json(value) for key, value in self.metadata.items()}
            ),
        )


@dataclass(frozen=True)
class Job:
    kind: str
    input: JobInput
    metadata: Mapping[str, FrozenJsonValue] = field(default_factory=dict)
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    parent_id: uuid.UUID | None = None
    root_id: uuid.UUID | None = None

    @classmethod
    def spawn_job(cls, request: JobRequest) -> "Job":
        return cls(kind=request.kind, input=request.input, metadata=request.metadata)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "metadata",
            MappingProxyType(
                {key: _freeze_json(value) for key, value in self.metadata.items()}
            ),
        )
        if self.root_id is None:
            object.__setattr__(self, "root_id", self.id)

    def spawn_child(self, request: JobRequest) -> "Job":
        return type(self)(
            kind=request.kind,
            input=request.input,
            metadata=request.metadata,
            parent_id=self.id,
            root_id=self.root_id,
        )

    @property
    def hash(self) -> str:
        payload = json.dumps(
            {"kind": self.kind, "input": _job_input_payload(self.input)},
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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


def _job_input_payload(input: JobInput) -> dict[str, object]:
    if isinstance(input, InputUrl):
        return {"type": "url", "url": input.url}
    if isinstance(input, InputQuery):
        return {"type": "query", "query": _thaw_json(input.query)}
    document = input.document
    return {
        "type": "document",
        "document": {
            "url": document.url,
            "content": b64encode(document.content).decode("ascii"),
            "content_type": document.content_type,
            "status": document.status,
            "headers": dict(document.headers),
            "fetched_at": document.fetched_at.isoformat(),
        },
    }


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
