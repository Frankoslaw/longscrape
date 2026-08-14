from __future__ import annotations

from datetime import datetime
from typing import Any

import scrapy
from longscrape_core import Document, Record


class LongscrapeDocumentItem(scrapy.Item):
    """Scrapy representation of a core document and its pending record data."""

    document = scrapy.Field()
    data = scrapy.Field()

    @classmethod
    def from_document(
        cls, document: Document, *, data: dict[str, Any] | None = None
    ) -> "LongscrapeDocumentItem":
        return cls(document=document, data=data or {})

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
            document=document,
            data=data,
            metadata=metadata,
        )


class LongscrapeRecordItem(scrapy.Item):
    """Scrapy representation of a core record at a pipeline boundary."""

    kind = scrapy.Field()
    source_url = scrapy.Field()
    data = scrapy.Field()
    document = scrapy.Field()
    metadata = scrapy.Field()
    created_at = scrapy.Field()

    @classmethod
    def from_record(cls, record: Record) -> "LongscrapeRecordItem":
        return cls(
            kind=record.kind,
            source_url=record.source_url,
            data=record.data,
            document=record.document,
            metadata=record.metadata,
            created_at=record.created_at,
        )

    def to_record(self) -> Record:
        document = self.get("document")
        if document is not None and not isinstance(document, Document):
            raise TypeError("LongscrapeRecordItem.document must be a Document or None")
        values: dict[str, Any] = {
            "kind": self["kind"],
            "source_url": self["source_url"],
            "data": self.get("data", {}),
            "document": document,
            "metadata": self.get("metadata", {}),
        }
        created_at = self.get("created_at")
        if created_at is not None:
            if not isinstance(created_at, datetime):
                raise TypeError("LongscrapeRecordItem.created_at must be a datetime")
            values["created_at"] = created_at
        return Record(**values)
