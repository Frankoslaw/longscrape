from dataclasses import dataclass
from enum import Enum

from longscrape.core import JsonValue, Record


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
