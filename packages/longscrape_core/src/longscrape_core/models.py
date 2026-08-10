from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping

from longscrape_core.errors import InvalidSerializedValue
from longscrape_core.serialization import canonical_json, fingerprint, load_json_object


@dataclass(frozen=True)
class CrawlJob:
    kind: str
    query: dict[str, Any]
    context: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.kind.strip():
            raise ValueError("CrawlJob.kind must not be blank.")
        if not isinstance(self.query, dict):
            raise TypeError("CrawlJob.query must be an object.")
        if not isinstance(self.context, dict):
            raise TypeError("CrawlJob.context must be an object.")

        canonical_json(self.as_dict())

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "query": self.query,
            "context": self.context,
        }

    def to_json(self) -> str:
        return canonical_json(self.as_dict())

    def fingerprint(self) -> str:
        return fingerprint(self.as_dict())

    @classmethod
    def from_json(cls, value: str) -> CrawlJob:
        payload = load_json_object(value)

        kind = payload.get("kind")
        query = payload.get("query")
        context = payload.get("context", {})

        if not isinstance(kind, str):
            raise InvalidSerializedValue("CrawlJob.kind must be a string.")
        if not isinstance(query, dict):
            raise InvalidSerializedValue("CrawlJob.query must be an object.")
        if not isinstance(context, dict):
            raise InvalidSerializedValue("CrawlJob.context must be an object.")

        return cls(kind=kind, query=query, context=context)


@dataclass(frozen=True)
class FetchRequest:
    """Framework-neutral description of a document acquisition request."""

    url: str
    method: str = "GET"
    headers: Mapping[str, str] = field(default_factory=dict)
    body: bytes | None = None

    def __post_init__(self) -> None:
        if not self.url.strip():
            raise ValueError("FetchRequest.url must not be blank.")
        if not self.method.strip():
            raise ValueError("FetchRequest.method must not be blank.")


@dataclass(frozen=True)
class CapturedDocument:
    """A fetched or externally captured document ready for extraction."""

    url: str
    content: str
    content_type: str = "text/html"
    status: int = 200
    headers: Mapping[str, str] = field(default_factory=dict)
    captured_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.url.strip():
            raise ValueError("CapturedDocument.url must not be blank.")
        if not self.content_type.strip():
            raise ValueError("CapturedDocument.content_type must not be blank.")


@dataclass(frozen=True)
class SourceRecord:
    """A provider-neutral record emitted by a scraper or capture consumer."""

    id: str
    kind: str
    provider: str
    source_url: str
    data: dict[str, Any]
    captured_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("SourceRecord.id must not be blank.")
        if not self.kind.strip():
            raise ValueError("SourceRecord.kind must not be blank.")
        if not self.provider.strip():
            raise ValueError("SourceRecord.provider must not be blank.")
        if not self.source_url.strip():
            raise ValueError("SourceRecord.source_url must not be blank.")
        if not isinstance(self.data, dict):
            raise TypeError("SourceRecord.data must be an object.")


@dataclass(frozen=True)
class Extraction:
    """Records plus optional follow-up crawl jobs."""

    records: tuple[SourceRecord, ...] = ()
    follow_ups: tuple[CrawlJob, ...] = ()
