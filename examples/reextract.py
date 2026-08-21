import asyncio
import sys

from longscrape import InputUrl, JobRequest, PipelineContext, RecordSink
from longscrape.fetchers import FetcherBuilder
from longscrape.runtime import (
    Flow,
    FlowRouter,
    InMemoryJobQueue,
    StoredJobQueue,
)
from longscrape.stores import InMemoryDocumentStore

from .common import close_store, get_document_store, get_job_store, get_record_store
from .quotes import AUTHOR, QUOTES, START_URL, AuthorExtractor, QuotesExtractor


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

    job_store = get_job_store()
    job_queue = StoredJobQueue(InMemoryJobQueue(), job_store)
    context = PipelineContext(job_queue)
    await job_queue.submit(JobRequest(QUOTES, InputUrl(START_URL)))

    quote_store = get_record_store("quotes")
    author_store = get_record_store("authors")

    quote_sink = RecordSink(quote_store)
    author_sink = RecordSink(author_store)

    fetcher = FetcherBuilder().cache(store, write=False).build()
    flows = {
        QUOTES: (
            Flow(context)
            .fetch(fetcher)
            .extract(QuotesExtractor())
            .sink(quote_sink)
            .build()
        ),
        AUTHOR: (
            Flow(context)
            .fetch(fetcher)
            .extract(AuthorExtractor())
            .sink(author_sink)
            .build()
        ),
    }

    try:
        await FlowRouter(flows, job_store=job_store).run(job_queue)
    finally:
        await close_store(store)
        await close_store(job_store)
        await close_store(quote_store)
        await close_store(author_store)


if __name__ == "__main__":
    asyncio.run(main())
