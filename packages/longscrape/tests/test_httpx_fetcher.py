import asyncio

import httpx
import pytest
from longscrape import Context, HttpStatusError, InputUrl
from longscrape.fetchers.httpx_fetcher import HttpxFetcher


def test_httpx_fetcher_raises_core_error() -> None:
    async def run() -> None:
        transport = httpx.MockTransport(
            lambda request: httpx.Response(404, request=request)
        )
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(HttpStatusError):
                await HttpxFetcher(client).fetch(
                    InputUrl("https://example.com"), Context()
                )

    asyncio.run(run())
