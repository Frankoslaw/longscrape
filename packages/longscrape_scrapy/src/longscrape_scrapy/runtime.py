"""Process-local registry for runtime objects unsafe to place in Scrapy settings."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

_VALUES: dict[str, Any] = {}


def register(value: Any) -> str:
    key = str(uuid4())
    _VALUES[key] = value
    return key


def resolve(key: str) -> Any:
    try:
        return _VALUES[key]
    except KeyError as error:
        raise RuntimeError(f"Longscrape runtime object not found: {key}") from error


def discard(key: str) -> None:
    _VALUES.pop(key, None)
