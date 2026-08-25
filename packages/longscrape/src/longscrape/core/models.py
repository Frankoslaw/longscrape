from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType

from longscrape.utils import JsonInput, freeze_json_object


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
