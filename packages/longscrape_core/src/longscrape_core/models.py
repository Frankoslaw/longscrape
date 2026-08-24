from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from types import MappingProxyType

from longscrape_core._json import JsonInput, JsonValue, freeze_json_object


@dataclass(frozen=True)
class InputUrl:
    url: str


@dataclass(frozen=True)
class InputQuery:
    query: Mapping[str, JsonInput]

    def __post_init__(self) -> None:
        object.__setattr__(self, "query", freeze_json_object(self.query))


type FetchInput = InputUrl | InputQuery


@dataclass(frozen=True)
class DocumentRef:
    """Opaque capability for one immutable document revision."""

    store: str
    value: str


@dataclass(frozen=True)
class RecordRef:
    """Opaque capability for one stored record."""

    store: str
    value: str


class CollisionPolicy(Enum):
    NEW = "new"
    OVERWRITE = "overwrite"
    MERGE = "merge"


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
class Record[T]:
    kind: str
    data: T
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def hash(self) -> str:
        payload = json.dumps(
            {"kind": self.kind, "data": self.data},
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def merge_records(
    existing: Record[dict[str, JsonValue]], incoming: Record[dict[str, JsonValue]]
) -> Record[dict[str, JsonValue]]:
    if existing.kind != incoming.kind:
        raise ValueError("cannot merge records with different kinds")
    data = dict(existing.data)
    for key, value in incoming.data.items():
        if data.get(key) is None:
            data[key] = value
    return Record(existing.kind, data, created_at=incoming.created_at)
