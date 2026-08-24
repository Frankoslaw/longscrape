from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Self, cast

from longscrape_core import FetchInput, InputQuery, InputUrl

from longscrape.storage.models import DocumentRef
from longscrape.utils import (
    FrozenJsonValue,
    JsonInput,
    JsonValue,
    freeze_json_object,
    thaw_json,
)


@dataclass(frozen=True)
class DocumentRefInput:
    """A durable worker input referring to a stored document revision."""

    ref: DocumentRef


type JobInput = FetchInput | DocumentRefInput


@dataclass(frozen=True)
class JobRequest:
    kind: str
    input: JobInput
    metadata: Mapping[str, JsonInput] = field(default_factory=dict)
    worker_id: str | None = None

    def __post_init__(self) -> None:
        if not self.kind:
            raise ValueError("job kind must not be empty")
        if self.worker_id == "":
            raise ValueError("worker_id must not be empty")
        object.__setattr__(self, "metadata", freeze_json_object(self.metadata))


@dataclass(frozen=True)
class Job:
    kind: str
    input: JobInput
    metadata: Mapping[str, JsonInput] = field(default_factory=dict)
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    parent_id: uuid.UUID | None = None
    root_id: uuid.UUID | None = None
    worker_id: str | None = None

    def __post_init__(self) -> None:
        if not self.kind:
            raise ValueError("job kind must not be empty")
        if self.root_id is None:
            object.__setattr__(self, "root_id", self.id)
        if self.worker_id == "":
            raise ValueError("worker_id must not be empty")
        object.__setattr__(self, "metadata", freeze_json_object(self.metadata))

    @classmethod
    def spawn_job(cls, request: JobRequest) -> Self:
        return cls(
            request.kind, request.input, request.metadata, worker_id=request.worker_id
        )

    def spawn_child(self, request: JobRequest) -> Self:
        return type(self)(
            request.kind,
            request.input,
            cast(
                dict[str, JsonInput],
                {
                    **{
                        key: thaw_json(cast(FrozenJsonValue, value))
                        for key, value in self.metadata.items()
                    },
                    **{
                        key: thaw_json(cast(FrozenJsonValue, value))
                        for key, value in request.metadata.items()
                    },
                },
            ),
            parent_id=self.id,
            root_id=self.root_id,
            worker_id=request.worker_id or self.worker_id,
        )

    @property
    def hash(self) -> str:
        payload = json.dumps(
            {"kind": self.kind, "input": _input_to_dict(self.input)},
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "id": str(self.id),
            "parent_id": str(self.parent_id) if self.parent_id else None,
            "root_id": str(self.root_id),
            "kind": self.kind,
            "input": _input_to_dict(self.input),
            "metadata": {
                key: thaw_json(cast(FrozenJsonValue, value))
                for key, value in self.metadata.items()
            },
            "worker_id": self.worker_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, JsonValue]) -> Self:
        parent_id = cast(str | None, value["parent_id"])
        return cls(
            id=uuid.UUID(cast(str, value["id"])),
            parent_id=uuid.UUID(parent_id) if parent_id else None,
            root_id=uuid.UUID(cast(str, value["root_id"])),
            kind=cast(str, value["kind"]),
            input=_input_from_dict(cast(dict[str, JsonValue], value["input"])),
            metadata=cast(Mapping[str, JsonInput], value["metadata"]),
            worker_id=cast(str | None, value.get("worker_id")),
        )


class JobStatus(Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class StoredJob:
    job: Job
    key: str
    status: JobStatus
    attempts: int = 0
    error: str | None = None


def _input_to_dict(value: JobInput) -> dict[str, JsonValue]:
    match value:
        case InputUrl(url):
            return {"type": "url", "url": url}
        case InputQuery(query):
            return {
                "type": "query",
                "query": thaw_json(cast(FrozenJsonValue, query)),
            }
        case DocumentRefInput(DocumentRef(store, ref)):
            return {"type": "document-ref", "store": store, "ref": ref}


def _input_from_dict(value: dict[str, JsonValue]) -> JobInput:
    match value["type"]:
        case "url":
            return InputUrl(cast(str, value["url"]))
        case "query":
            return InputQuery(cast(Mapping[str, JsonInput], value["query"]))
        case "document-ref":
            return DocumentRefInput(
                DocumentRef(cast(str, value["store"]), cast(str, value["ref"]))
            )
        case input_type:
            raise ValueError(f"unknown job input type: {input_type!r}")
