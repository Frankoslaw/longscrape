from longscrape.adapters.httpx.httpx import HttpxManager
from longscrape.core.domain.pipeline import RawEntry, ScraperTask


class HttpxFetcher:
    """Fetch URL tasks through :class:`HttpxManager`."""

    def __init__(
        self,
        http: HttpxManager,
        base_domain: str,
        *,
        raise_for_status: bool = True,
    ) -> None:
        if not base_domain:
            raise ValueError("base_domain must not be empty")
        self._http = http
        self._base_domain = base_domain
        self._raise_for_status = raise_for_status

    def get_base_domain(self) -> str:
        return self._base_domain

    async def fetch(self, task: ScraperTask) -> RawEntry:
        if not isinstance(task.query, str):
            raise TypeError("HttpxFetcher requires a URL string query")
        response = await self._http.get(task.query)
        if self._raise_for_status:
            response.raise_for_status()
        return RawEntry(
            url=str(response.url),
            content=response.text,
            content_type=response.headers.get("content-type", "text/html"),
            status_code=response.status_code,
        )
