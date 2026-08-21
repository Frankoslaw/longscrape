from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from longscrape_core import Record

TOKEN_FIELD = "_longscrape_token"


@dataclass(frozen=True)
class _RecordToken:
    kind: str
    created_at: datetime


def item_from_record(record: Record[Any]) -> dict[str, Any]:
    """Expose record data as an ordinary Scrapy item with opaque provenance."""
    if not isinstance(record.data, dict):
        raise TypeError("Scrapy records must have a dictionary data shape")
    return {
        **record.data,
        TOKEN_FIELD: _RecordToken(record.kind, record.created_at),
    }


def record_from_item(item: Any, *, token_only: bool) -> Record[Any] | None:
    """Adapt an item at a longscrape pipeline boundary."""
    values = dict(item)
    token = values.pop(TOKEN_FIELD, None)
    if token is None:
        if token_only:
            return None
        return Record("scrapy.item", values)
    if not isinstance(token, _RecordToken):
        if token_only:
            return None
        return Record("scrapy.item", values)
    return Record(token.kind, values, created_at=token.created_at)
