from dataclasses import dataclass
from typing import Any, cast

import httpx
import pytest
from longscrape.fetchers.httpx_fetcher import HttpxFetcher
from longscrape.models import Document, InputQuery, InputUrl
from longscrape.protocols import Fetcher


@dataclass(frozen=True)
class SearchQuery:
    search_term: str


class PageNotFound(Exception):
    pass


class ExampleFetcher(Fetcher[InputUrl]):
    """Fetcher driven by URL inputs."""

    def __init__(self, document: Document):
        self._doc = document

    async def fetch(self, fetch_input: InputUrl) -> Document:
        if fetch_input.url != "https://example.com/page":
            raise PageNotFound()

        return self._doc


class QueryExampleFetcher[T](Fetcher[InputQuery[T]]):
    """Fetcher driven by search query inputs."""

    def __init__(self, document: Document):
        self._doc = document

    async def fetch(self, fetch_input: InputQuery[T]) -> Document:
        query = fetch_input.query

        # Support both dict lookups (untyped Any) and attribute access (typed model)
        if isinstance(query, dict):
            term = cast(dict[str, Any], query).get("search_term")
        else:
            term = getattr(query, "search_term", None)

        if term != "example":
            raise PageNotFound()

        return self._doc


@pytest.fixture
def sample_html_doc() -> Document:
    return Document(
        url="https://example.com/page",
        content_type="text/html",
        content="<html>"
        "   <body>"
        "       <h1>Hello world!</h1>"
        "       <h2>From HTML :D</h2>"
        "   </body>"
        "</html>".encode("utf-8"),
    )


@pytest.mark.asyncio
async def test_basic_fetch_returns_document(sample_html_doc: Document):
    fetcher = ExampleFetcher(sample_html_doc)
    input_data = InputUrl(url="https://example.com/page")

    doc = await fetcher.fetch(input_data)

    assert isinstance(doc, Document)
    assert doc.url == "https://example.com/page"
    assert "Hello world!" in doc.text


@pytest.mark.asyncio
async def test_url_fetcher_raises_page_not_found_on_unknown_url(
    sample_html_doc: Document,
):
    fetcher = ExampleFetcher(sample_html_doc)
    input_data = InputUrl(url="https://example.com/missing")

    with pytest.raises(PageNotFound):
        await fetcher.fetch(input_data)


@pytest.mark.asyncio
async def test_query_fetcher_returns_document_for_untyped_any_query(
    sample_html_doc: Document,
):
    """Tests InputQuery using an untyped dictionary (InputQuery[Any])."""
    fetcher = QueryExampleFetcher[Any](sample_html_doc)
    input_data: InputQuery[Any] = InputQuery(query={"search_term": "example"})

    doc = await fetcher.fetch(input_data)

    assert isinstance(doc, Document)
    assert doc.url == "https://example.com/page"


@pytest.mark.asyncio
async def test_query_fetcher_returns_document_for_typed_query(
    sample_html_doc: Document,
):
    """Tests InputQuery using a concrete dataclass type (InputQuery[SearchQuery])."""
    fetcher = QueryExampleFetcher[SearchQuery](sample_html_doc)
    input_data = InputQuery(query=SearchQuery(search_term="example"))

    doc = await fetcher.fetch(input_data)

    assert isinstance(doc, Document)
    assert doc.url == "https://example.com/page"


@pytest.mark.asyncio
async def test_query_fetcher_raises_page_not_found_for_unmatched_search(
    sample_html_doc: Document,
):
    fetcher = QueryExampleFetcher[SearchQuery](sample_html_doc)
    input_data = InputQuery(query=SearchQuery(search_term="unknown"))

    with pytest.raises(PageNotFound):
        await fetcher.fetch(input_data)


@pytest.mark.asyncio
async def test_httpx_fetcher_fetches_url_successfully():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            headers={"Content-Type": "text/html; charset=utf-8"},
            content=b"<html><body><h1>HTTPX Response</h1></body></html>",
        )

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        fetcher = HttpxFetcher(client=client)
        fetch_input = InputUrl(url="https://example.com/page")

        doc = await fetcher.fetch(fetch_input)

        assert isinstance(doc, Document)
        assert doc.url == "https://example.com/page"
        assert doc.content_type == "text/html; charset=utf-8"
        assert "HTTPX Response" in doc.text


@pytest.mark.asyncio
async def test_httpx_fetcher_raises_http_status_error_on_404():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=404, content=b"Not Found")

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        fetcher = HttpxFetcher(client=client)
        fetch_input = InputUrl(url="https://example.com/404")

        with pytest.raises(httpx.HTTPStatusError):
            await fetcher.fetch(fetch_input)
