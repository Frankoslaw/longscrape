import asyncio

import httpx
from longscrape.fetchers import HttpxFetcher
from longscrape_core import InputUrl, Job


def test_httpx_fetcher_preserves_content_type() -> None:
    async def run() -> None:
        response = httpx.Response(
            200,
            headers={"content-type": "application/json; charset=utf-8"},
            content=b'{"ok": true}',
        )
        transport = httpx.MockTransport(lambda request: response)
        async with httpx.AsyncClient(transport=transport) as client:
            documents = [
                document
                async for document in HttpxFetcher(client).fetch(
                    Job(kind="fetch", input=InputUrl("https://example.com/data"))
                )
            ]

        assert documents[0].content_type == "application/json; charset=utf-8"

    asyncio.run(run())
