from dataclasses import dataclass


@dataclass(frozen=True)
class Document:
    url: str
    content_type: str
    content: bytes

    @property
    def text(self) -> str:
        return self.content.decode("utf-8")


@dataclass(frozen=True)
class Record[T]:
    data: T
