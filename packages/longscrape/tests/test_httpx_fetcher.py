import asyncio

import httpx
from longscrape.fetchers import HttpxFetcher
from longscrape_core import HttpStatusError, InputUrl, Job


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


def test_httpx_fetcher_exposes_rate_limit_delay() -> None:
    async def run() -> None:
        response = httpx.Response(429, headers={"retry-after": "12"})
        transport = httpx.MockTransport(lambda request: response)
        async with httpx.AsyncClient(transport=transport) as client:
            try:
                _ = [
                    document
                    async for document in HttpxFetcher(client).fetch(
                        Job(kind="fetch", input=InputUrl("https://example.com/data"))
                    )
                ]
            except HttpStatusError as error:
                assert error.status == 429
                assert error.retry_after is not None
                assert error.retry_after.total_seconds() == 12
            else:
                raise AssertionError("expected HttpStatusError")

    asyncio.run(run())


def test_httpx_fetcher_exposes_unauthorized_and_forbidden_statuses() -> None:
    async def run(status: int) -> None:
        transport = httpx.MockTransport(lambda request: httpx.Response(status))
        async with httpx.AsyncClient(transport=transport) as client:
            try:
                _ = [
                    document
                    async for document in HttpxFetcher(client).fetch(
                        Job(kind="fetch", input=InputUrl("https://example.com/data"))
                    )
                ]
            except HttpStatusError as error:
                assert error.status == status
            else:
                raise AssertionError("expected HttpStatusError")

    asyncio.run(run(401))
    asyncio.run(run(403))
