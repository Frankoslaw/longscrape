from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, HTTPException
from longscrape_core import Document, InputDocument, Job
from pydantic import BaseModel, Field

from longscrape.scraper import UnknownCaptureKind


class BrowserCapture(BaseModel):
    kind: str
    url: str
    content: str
    content_type: str = "text/html"
    query: dict[str, Any] = Field(default_factory=dict)


def create_capture_app(
    process: Callable[[Job], Awaitable[int]],
    *,
    path: str = "/captures",
) -> FastAPI:
    """Create a minimal browser-extension capture receiver.

    ``process`` owns extraction, transformation, storage, and any routing by
    job kind. It returns the number of produced records.
    """
    if not path.startswith("/"):
        raise ValueError("path must start with '/'")
    app = FastAPI()

    @app.post(path)
    async def capture(payload: BrowserCapture) -> dict[str, int | str]:
        if not payload.kind.strip():
            raise HTTPException(status_code=422, detail="kind must not be blank")
        job = Job(
            kind=payload.kind,
            input=InputDocument(
                Document(
                    url=payload.url,
                    content=payload.content.encode(),
                    content_type=payload.content_type,
                    metadata={"captured_by": "browser-extension"},
                )
            ),
            context=payload.query,
        )
        try:
            count = await process(job)
        except UnknownCaptureKind as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"status": "ok", "items": count}

    return app
