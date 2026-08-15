from __future__ import annotations

from datetime import datetime
from typing import Any

import scrapy
from longscrape_core import Document, DocumentRef, Record


class LongscrapeDocumentItem(scrapy.Item):
    """Scrapy representation of a core document and its pending record data."""

    document = scrapy.Field()
    document_ref = scrapy.Field()
    data = scrapy.Field()

    @classmethod
    def from_document(
        cls,
        document: Document,
        *,
        document_ref: DocumentRef | None = None,
        data: dict[str, Any] | None = None,
    ) -> "LongscrapeDocumentItem":
        return cls(document=document, document_ref=document_ref, data=data or {})

    def to_record(self, *, kind: str, metadata: dict[str, Any]) -> Record:
        document = self["document"]
        if not isinstance(document, Document):
            raise TypeError("LongscrapeDocumentItem.document must be a Document")
        data = self.get("data", {})
        if not isinstance(data, dict):
            raise TypeError("LongscrapeDocumentItem.data must be a dictionary")
        return Record(
            kind=kind,
            source_url=document.url,
            document_ref=self.get("document_ref"),
            data=data,
            metadata=metadata,
        )


class LongscrapeRecordItem(scrapy.Item):
    """Scrapy representation of a core record at a pipeline boundary."""

    kind = scrapy.Field()
    source_url = scrapy.Field()
    data = scrapy.Field()
    document_ref = scrapy.Field()
    metadata = scrapy.Field()
    created_at = scrapy.Field()

    @classmethod
    def from_record(cls, record: Record) -> "LongscrapeRecordItem":
        return cls(
            kind=record.kind,
            source_url=record.source_url,
            data=record.data,
            document_ref=record.document_ref,
            metadata=record.metadata,
            created_at=record.created_at,
        )

    def to_record(self) -> Record:
        document_ref = self.get("document_ref")
        if document_ref is not None and not isinstance(document_ref, DocumentRef):
            raise TypeError(
                "LongscrapeRecordItem.document_ref must be a DocumentRef or None"
            )
        values: dict[str, Any] = {
            "kind": self["kind"],
            "source_url": self["source_url"],
            "data": self.get("data", {}),
            "document_ref": document_ref,
            "metadata": self.get("metadata", {}),
        }
        created_at = self.get("created_at")
        if created_at is not None:
            if not isinstance(created_at, datetime):
                raise TypeError("LongscrapeRecordItem.created_at must be a datetime")
            values["created_at"] = created_at
        return Record(**values)
