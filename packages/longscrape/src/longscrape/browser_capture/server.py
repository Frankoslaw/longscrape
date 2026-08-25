from collections.abc import AsyncIterable, Callable
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from longscrape.core import Record


class BrowserCapture(BaseModel):
    kind: str
    url: str
    content: str
    content_type: str = "text/html"
    context: dict[str, Any] = Field(default_factory=dict)


class BrowserCaptureServer:
    def __init__(
        self, handle_capture: Callable[[BrowserCapture], AsyncIterable[Record]]
    ) -> None:
        self._handle_capture = handle_capture
        self.app = FastAPI()
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["POST"],
            allow_headers=["Content-Type"],
        )
        self.app.post("/v1/captures")(self.capture)

    async def capture(self, capture: BrowserCapture) -> dict[str, int | str]:
        count = 0
        async for _ in self._handle_capture(capture):
            count += 1
        return {"status": "ok", "records": count}
