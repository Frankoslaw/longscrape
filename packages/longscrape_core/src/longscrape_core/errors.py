class LongscrapeError(Exception):
    """Base exception for LongScrape contracts."""


class InvalidSerializedValue(LongscrapeError, ValueError):
    """Raised when a JSON payload does not match an expected contract."""
