from dataclasses import dataclass
import re
from typing import TypedDict, AsyncIterable

import pytest

from longscrape.models import Document, Record
from longscrape.protocols import Extractor


@dataclass(frozen=True)
class ExampleRecord(TypedDict):
    h1: str
    h2: str

@dataclass(frozen=True)
class ExamplePartialRecord(TypedDict):
    h1: str
    h2: str | None

@pytest.fixture
def sample_html_doc() -> Document:
    return Document(
        url="https://example.com/page",
        content_type="text/html",
        content="<html><body><h1>Hello world!</h1><h2>From HTML :D</h2></body></html>".encode('utf-8'),
    )

@pytest.fixture
def partial_html_doc() -> Document:
    return Document(
        url="https://example.com/partial",
        content_type="text/html",
        content="<html><body><h1>Hello world!</h1></body></html>".encode('utf-8'),
    )

class SingleRecordExtractor(Extractor[ExampleRecord]):
    """Extracts a single record; returns [] if core elements are absent."""
    async def extract(self, document: Document) -> AsyncIterable[Record[ExampleRecord]]:
        h1_match = re.search(r"<h1>(.*?)</h1>", document.text)
        h2_match = re.search(r"<h2>(.*?)</h2>", document.text)

        if not h1_match:
            return

        yield Record(
                data={
                    "h1": h1_match.group(1),
                    "h2": h2_match.group(1) if h2_match else "",
                }
            )

class ListItemsExtractor(Extractor[dict]):
    """Yields 0..N records from repeated tags."""
    async def extract(self, document: Document) -> AsyncIterable[Record[dict]]:
        items = re.findall(r"<li>(.*?)</li>", document.text)

        for item in items:
            yield Record(data={"title": item})

class StrictExampleExtractor(Extractor[ExampleRecord]):
    """Fails with ValueError when expected data is missing."""
    async def extract(self, document: Document) -> AsyncIterable[Record[ExampleRecord]]:
        h1_match = re.search(r"<h1>(.*?)</h1>", document.text)
        h2_match = re.search(r"<h2>(.*?)</h2>", document.text)

        if not h1_match or not h2_match:
            raise ValueError("Missing required field: h2")

        yield Record(
                data={
                    "h1": h1_match.group(1),
                    "h2": h2_match.group(1),
                }
            )

class LenientExampleExtractor(Extractor[ExamplePartialRecord]):
    """Fills missing optional values with None instead of raising errors."""
    async def extract(self, document: Document) -> AsyncIterable[Record[ExamplePartialRecord]]:
        h1_match = re.search(r"<h1>(.*?)</h1>", document.text)
        h2_match = re.search(r"<h2>(.*?)</h2>", document.text)

        if not h1_match:
            return

        yield Record(
                data={
                    "h1": h1_match.group(1),
                    "h2": h2_match.group(1) if h2_match else None,
                }
            )

@pytest.mark.asyncio
async def test_basic_extract_returns_single_record_list(sample_html_doc: Document):
    extractor = SingleRecordExtractor()
    records = [r async for r in extractor.extract(sample_html_doc)]

    assert isinstance(records, list)
    assert len(records) == 1
    assert records[0].data["h1"] == "Hello world!"
    assert records[0].data["h2"] == "From HTML :D"


@pytest.mark.asyncio
async def test_multiple_records_extract():
    list_doc = Document(
        url="https://example.com/list",
        content_type="text/html",
        content="<ul><li>Item 1</li><li>Item 2</li><li>Item 3</li></ul>".encode('utf-8'),
    )
    extractor = ListItemsExtractor()

    records = [r async for r in extractor.extract(list_doc)]

    assert isinstance(records, list)
    assert len(records) == 3
    assert [r.data["title"] for r in records] == ["Item 1", "Item 2", "Item 3"]

@pytest.mark.asyncio
async def test_zero_records_extract_returns_empty_list():
    empty_doc = Document(
        url="https://example.com/empty",
        content_type="text/html",
        content="<html><body><p>No target elements here</p></body></html>".encode('utf-8'),
    )
    extractor = SingleRecordExtractor()

    records = [r async for r in extractor.extract(empty_doc)]

    assert records == []

@pytest.mark.asyncio
async def test_typed_extractor_returns_typed_record(sample_html_doc: Document):
    extractor = SingleRecordExtractor()
    records = [r async for r in extractor.extract(sample_html_doc)]

    assert len(records) == 1
    record = records[0]

    assert isinstance(record.data, dict)
    assert "h1" in record.data
    assert "h2" in record.data
    assert isinstance(record.data["h1"], str)
    assert isinstance(record.data["h2"], str)

@pytest.mark.asyncio
async def test_strict_extractor_fails_on_missing_required_data(partial_html_doc: Document):
    extractor = StrictExampleExtractor()

    with pytest.raises(ValueError, match="Missing required field: h2"):
        _ = [r async for r in extractor.extract(partial_html_doc)]


@pytest.mark.asyncio
async def test_lenient_extractor_returns_none_on_missing_optional_data(partial_html_doc: Document):
    extractor = LenientExampleExtractor()

    records = [r async for r in extractor.extract(partial_html_doc)]

    assert len(records) == 1
    assert records[0].data["h1"] == "Hello world!"
    assert records[0].data["h2"] is None
