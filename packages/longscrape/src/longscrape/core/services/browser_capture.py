import inspect
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any, cast

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from longscrape.core.domain.pipeline import RawEntry, RawInput, RichEntry
from longscrape.core.services.crawler import Crawler, LifecycleResource
from longscrape.core.services.worker import ScraperWorker


class BrowserCapture(BaseModel):
    kind: str
    query: Any = Field(default_factory=dict)
    url: str
    content: str
    content_type: str = "text/html"


class BrowserCaptureServer:
    def __init__(
        self,
        workers: Mapping[str, ScraperWorker[Any]] | None = None,
        *,
        path: str = "/captures",
        concurrency: int = 1,
        resources: Sequence[LifecycleResource] = (),
        allow_origins: Sequence[str] = ("*",),
        on_items: Callable[[list[RichEntry[Any]]], Awaitable[None] | None]
        | None = None,
    ) -> None:
        if not path.startswith("/"):
            raise ValueError("path must start with '/'")
        if concurrency < 1:
            raise ValueError("concurrency must be at least one")
        self.workers = dict(workers or {})
        self.concurrency = concurrency
        self.resources = tuple(resources)
        self.on_items = on_items
        self.app = FastAPI()
        self.app.add_middleware(
            cast(Any, CORSMiddleware),
            allow_origins=list(allow_origins),
            allow_methods=["POST"],
            allow_headers=["Content-Type"],
        )
        self.app.post(path)(self.capture)

    def register(self, kind: str, worker: ScraperWorker[Any]) -> None:
        if not kind:
            raise ValueError("kind must not be empty")
        self.workers[kind] = worker

    async def capture(self, capture: BrowserCapture) -> dict[str, int | str]:
        if capture.kind not in self.workers:
            raise HTTPException(
                status_code=404,
                detail=f"No worker registered for capture kind: {capture.kind}",
            )
        input = RawInput(
            kind=capture.kind,
            query=capture.query,
            raw_entry=RawEntry(
                url=capture.url,
                content=capture.content,
                content_type=capture.content_type,
                kind=capture.kind,
                query=capture.query,
            ),
        )
        async with Crawler(
            self.workers,
            concurrency=self.concurrency,
            resources=self.resources,
        ) as crawler:
            items = await crawler.run_inputs(input)
        if self.on_items is not None:
            result = self.on_items(items)
            if inspect.isawaitable(result):
                await result
        return {"status": "ok", "items": len(items)}
