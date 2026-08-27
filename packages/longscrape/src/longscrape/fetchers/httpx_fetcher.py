import httpx

from longscrape.models import Document, InputUrl
from longscrape.protocols import Fetcher


class HttpxFetcher(Fetcher[InputUrl]):
    def __init__(self, client: httpx.AsyncClient):
        self._client = client

    async def fetch(self, fetch_input: InputUrl) -> Document:
        response = await self._client.get(fetch_input.url)
        response.raise_for_status()

        return Document(
            url=str(response.url),
            content=response.content,
            content_type=response.headers.get("content-type", "text/html"),
        )
