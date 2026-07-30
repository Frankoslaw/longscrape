from longscrape.core.domain.pipeline import RawEntry


class InMemoryRawEntryStore:
    """Process-local raw entry store suitable as the default cache."""

    def __init__(self) -> None:
        self._entries: dict[str, RawEntry] = {}

    async def get(self, cache_key: str) -> RawEntry | None:
        return self._entries.get(cache_key)

    async def put(self, cache_key: str, raw_entry: RawEntry) -> None:
        self._entries[cache_key] = raw_entry
