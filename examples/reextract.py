import asyncio
import sys
from collections.abc import AsyncIterator

from common import close_store, get_document_store, get_record_store
from longscrape import Document, InputUrl, JobRequest, RecordSink
from longscrape.runtime import InMemoryJobQueue
from longscrape.stores import InMemoryDocumentStore
from quotes import (
    AUTHOR,
    QUOTES,
    START_URL,
    AuthorExtractor,
    QuotesExtractor,
)


async def one(document: Document) -> AsyncIterator[Document]:
    yield document


async def main() -> None:
    store = get_document_store()
    if isinstance(store, InMemoryDocumentStore):
        print(
            "Warning: MONGODB_URI is not set. The in-memory document store is "
            "empty in this new process, so re-extraction is a no-op. Run "
            "quotes.py with MONGODB_URI set first.",
            file=sys.stderr,
        )
        return

    job_queue = InMemoryJobQueue()
    await job_queue.submit(JobRequest(QUOTES, InputUrl(START_URL)))

    seen: set[str] = set()

    quotes_extractor = QuotesExtractor()
    author_extractor = AuthorExtractor()

    quote_store = get_record_store("quotes")
    author_store = get_record_store("authors")

    quote_sink = RecordSink(quote_store)
    author_sink = RecordSink(author_store)

    try:
        while not job_queue.empty():
            job = await job_queue.get()
            if not isinstance(job.input, InputUrl) or job.input.url in seen:
                continue

            seen.add(job.input.url)
            document = await store.load(job.input.url)
            if document is None:
                continue

            if job.kind == QUOTES:
                records = quotes_extractor.extract(one(document), job, job_queue)
                async for _ in quote_sink.transform(records, job, job_queue):
                    pass
            elif job.kind == AUTHOR:
                records = author_extractor.extract(one(document), job, job_queue)
                async for _ in author_sink.transform(records, job, job_queue):
                    pass
    finally:
        await close_store(store)
        await close_store(quote_store)
        await close_store(author_store)


if __name__ == "__main__":
    asyncio.run(main())
