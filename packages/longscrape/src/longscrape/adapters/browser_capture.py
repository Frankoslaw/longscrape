import hmac
import inspect
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from typing import Annotated, Any

from fastapi import FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from longscrape_core import (
    DISCARD_SUBMITTER,
    Document,
    Extractor,
    InputDocument,
    Job,
    JobSubmitter,
    Record,
)
from longscrape_core.ports import DocumentStore
from pydantic import BaseModel, Field


class BrowserCapture(BaseModel):
    kind: str
    url: str
    content: str
    content_type: str = "text/html"
    context: dict[str, Any] = Field(default_factory=dict)


async def _one(document: Document) -> AsyncIterator[Document]:
    yield document


class BrowserCaptureServer:
    def __init__(
        self,
        extractors: Mapping[str, Extractor] | None = None,
        *,
        path: str = "/v1/captures",
        token: str | None = None,
        document_store: DocumentStore | None = None,
        submitter: JobSubmitter = DISCARD_SUBMITTER,
        on_records: Callable[[list[Record]], Awaitable[None] | None] | None = None,
        allow_origins: tuple[str, ...] = ("*",),
    ) -> None:
        if not path.startswith("/"):
            raise ValueError("path must start with '/'")
        if token == "":
            raise ValueError("token must not be empty")
        self.extractors = dict(extractors or {})
        self._token = token
        self._document_store = document_store
        self._submitter = submitter
        self._on_records = on_records
        self.app = FastAPI()
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=list(allow_origins),
            allow_methods=["POST"],
            allow_headers=["Authorization", "Content-Type"],
        )
        self.app.post(path)(self.capture)

    def register(self, kind: str, extractor: Extractor) -> None:
        if not kind:
            raise ValueError("kind must not be empty")
        self.extractors[kind] = extractor

    async def capture(
        self,
        capture: BrowserCapture,
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, int | str]:
        self._authenticate(authorization)
        try:
            extractor = self.extractors[capture.kind]
        except KeyError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No extractor registered for capture kind: {capture.kind}",
            ) from error

        document = Document(
            url=capture.url,
            content=capture.content.encode("utf-8"),
            content_type=capture.content_type,
        )
        if self._document_store is not None:
            await self._document_store.store(document)

        job = Job(
            kind=capture.kind,
            input=InputDocument(document),
            context=capture.context,
        )
        records = [
            record
            async for record in extractor.extract(_one(document), job, self._submitter)
        ]
        if self._on_records is not None:
            result = self._on_records(records)
            if inspect.isawaitable(result):
                await result
        return {"status": "ok", "records": len(records)}

    def _authenticate(self, authorization: str | None) -> None:
        if self._token is None:
            return
        expected = f"Bearer {self._token}"
        if authorization is None or not hmac.compare_digest(authorization, expected):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid bearer token",
                headers={"WWW-Authenticate": "Bearer"},
            )
