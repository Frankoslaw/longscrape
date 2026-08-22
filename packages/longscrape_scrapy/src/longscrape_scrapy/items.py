"""Scrapy item adapters that preserve core record provenance off-payload."""

from datetime import datetime
from typing import Any

from longscrape import JsonValue, Record


class LongscrapeItem(dict[str, JsonValue]):
    """A normal exporter-safe mapping with non-serialized record metadata."""

    __slots__ = ("record_kind", "record_created_at", "record_key")

    record_kind: str
    record_created_at: datetime
    record_key: str | None


def item_from_record(record: Record[Any]) -> LongscrapeItem:
    if not isinstance(record.data, dict):
        raise TypeError("Scrapy records must have a dictionary data shape")
    item = LongscrapeItem(record.data)
    item.record_kind = record.kind
    item.record_created_at = record.created_at
    item.record_key = record.key
    return item


def record_from_item(item: Any, *, token_only: bool) -> Record[Any] | None:
    if isinstance(item, LongscrapeItem):
        return Record(
            item.record_kind, dict(item), item.record_key, item.record_created_at
        )
    if token_only:
        return None
    return Record("scrapy.item", dict(item))
