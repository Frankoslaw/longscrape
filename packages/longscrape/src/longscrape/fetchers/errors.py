"""HTTP-specific values; independent from generic failure handling."""

from dataclasses import dataclass
from datetime import timedelta


@dataclass(frozen=True)
class HttpStatusError(Exception):
    url: str
    status: int
    retry_after: timedelta | None = None
