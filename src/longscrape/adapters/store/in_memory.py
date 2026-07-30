from longscrape.core.domain.pipeline import RawEntry


class InMemoryRawEntryStore:
    """Process-local raw entry store suitable as the default cache."""

    def __init__(self) -> None:
        self._entries: dict[str, RawEntry] = {}

    async def get(self, task_hash: str) -> RawEntry | None:
        return self._entries.get(task_hash)

    async def put(self, task_hash: str, raw_entry: RawEntry) -> None:
        self._entries[task_hash] = raw_entry
