import asyncio
import sys

from common import close_store, get_document_store, get_record_store
from longscrape import InputUrl, JobRequest, PipelineContext, RecordSink
from longscrape.fetchers import CachedFetcher
from longscrape.runtime import Flow, InMemoryJobQueue
from longscrape.stores import InMemoryDocumentStore
from quotes import (
    AUTHOR,
    QUOTES,
    START_URL,
    AuthorExtractor,
    QuotesExtractor,
)


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
    context = PipelineContext(job_queue)
    await job_queue.submit(JobRequest(QUOTES, InputUrl(START_URL)))

    seen: set[str] = set()

    quote_store = get_record_store("quotes")
    author_store = get_record_store("authors")

    quote_sink = RecordSink(quote_store)
    author_sink = RecordSink(author_store)

    fetcher = CachedFetcher(None, store, write=False)
    flows = {
        QUOTES: (
            Flow(context)
            .fetch(fetcher)
            .extract(QuotesExtractor())
            .consume(quote_sink)
            .build()
        ),
        AUTHOR: (
            Flow(context)
            .fetch(fetcher)
            .extract(AuthorExtractor())
            .consume(author_sink)
            .build()
        ),
    }

    try:
        while not job_queue.empty():
            job = await job_queue.get()
            if not isinstance(job.input, InputUrl) or job.input.url in seen:
                continue

            seen.add(job.input.url)
            flow = flows.get(job.kind)
            if flow is None:
                continue
            async for _ in flow(job):
                pass
    finally:
        await close_store(store)
        await close_store(quote_store)
        await close_store(author_store)


if __name__ == "__main__":
    asyncio.run(main())
