from __future__ import annotations

import hashlib
import json
from typing import Any

from longscrape_core.errors import InvalidSerializedValue


def canonical_json(value: Any) -> str:
    """Serialize a JSON-compatible value deterministically."""
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise InvalidSerializedValue("Value must be JSON serializable.") from exc


def fingerprint(value: Any) -> str:
    """Return a stable SHA-256 fingerprint for a JSON-compatible value."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def load_json_object(value: str) -> dict[str, Any]:
    """Parse a JSON object, rejecting arrays and scalar values."""
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise InvalidSerializedValue("Value must contain valid JSON.") from exc

    if not isinstance(payload, dict):
        raise InvalidSerializedValue("Value must contain a JSON object.")

    return payload
