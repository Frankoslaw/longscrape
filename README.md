# longscrape

> [!WARNING]
> The canonical repository and issue tracker are at
> [forgejo.frankoslaw.top/frankoslaw/longscrape](https://forgejo.frankoslaw.top/frankoslaw/longscrape).
> GitHub is a read-only mirror.

`longscrape` is an async, composable scraping toolkit. It supplies small
components for fetching, extraction, persistence, browser automation, and
optional durable execution. It does not hide a crawler runtime behind a
framework.

```text
Job → Fetcher → Document → Extractor → Record → Transformer
                    └──────────────→ JobSpec (follow-up work)
```

`longscrape-core` contains the immutable domain values and lightweight stage
protocols. The main package adds HTTP and browser fetchers, fetcher decorators,
stores, a linear `Flow` builder, local development helpers, and a Dramatiq
adapter.

## Install

For development in this repository:

```bash
uv sync
```

For an application, install the package with only the adapters it uses:

```bash
uv add longscrape                         # HTTP fetching and HTML selection
uv add 'longscrape[browser]'              # Playwright browser provider
uv add 'longscrape[mongodb]'              # PyMongo stores
uv add 'longscrape[dramatiq]'             # Redis-backed Dramatiq execution
uv add 'longscrape[structlog,otel]'       # optional observability adapters
```

The `browser-capture` extra provides the optional FastAPI receiver used by the
browser-extension example. Browser binaries are installed separately:

```bash
uv run playwright install chromium
```

## Build a streaming flow

Stages exchange async iterables. A record can therefore be consumed as soon as
the extractor produces it, without buffering a whole crawl.

```python
import httpx

from longscrape import InputUrl, Job, JobSpec
from longscrape.fetchers import HttpxFetcher
from longscrape.runtime import Flow

async with httpx.AsyncClient() as client:
  flow = Flow().fetch(HttpxFetcher(client)).extract(ArticleExtractor()).build()
  job = Job.spawn_job(JobSpec("article", InputUrl("https://example.com")))
  async for record in flow(job):
    print(record.data)
```

`Fetcher`, `Extractor`, and `Transformer` are protocols, so ordinary classes
that expose the expected async-iterator method compose directly.
Use `.transform(...)` for both record transforms and terminal sinks such as
`RecordSink`; a sink simply yields no records.

## Optional record typing

`Flow` is immutable and carries record shapes from extractors through
transformers and sinks. Type annotations remain optional; untyped stages
compose as `Any`. `TypedDict` works well for JSON-compatible stored records:

```python
from typing import TypedDict

from longscrape import Extractor, Record, Transformer
from longscrape.runtime import Flow

class Article(TypedDict):
    title: str

class Summary(TypedDict):
    summary: str

class ToSummary(Transformer[Article, Summary]):
    async def transform(self, records, job, context=None):
        async for record in records:
            yield Record[Summary]("summary", {"summary": record.data["title"]})

flow = Flow().fetch(fetcher).extract(article_extractor).transform(ToSummary())
```

The type checker can now reject a transformer or `RecordSink` that expects a
different record shape. See [`examples/typed_records.py`](examples/typed_records.py)
for a complete runnable pipeline.

Give `Flow` a `PipelineContext` when stages need process-local capabilities,
such as submitting a child job or sharing a live browser page:

```python
context = PipelineContext(submitter)
flow = Flow(context).fetch(fetcher).extract(extractor).transform(sink).build()
```

`JobSpec` is the input for root or child work; `Job.spawn_job(request)`
creates a root job. Inside an extractor, use
`await context.submit_child(job, JobSpec(...))` to preserve the parent and
root lineage.

## Fetcher composition

Use the fetchers directly for a single concern, or use `FetcherBuilder` to make
the decorator order explicit:

```python
from datetime import timedelta

from longscrape.fetchers import FetcherBuilder

fetcher = (
    FetcherBuilder()
    .base(HttpxFetcher(client))
    .rate_limit(requests_per_second=2)
    .cache(document_store, max_age=timedelta(hours=1))
    .build()
)
```

`CachedFetcher` can also run without a fallback fetcher, which is useful for
re-extracting documents that are already in a store:

```python
cached_only = FetcherBuilder().cache(document_store, write=False).build()
```

`HandoffFetcher` runs an application-defined recovery step, such as a manual
browser login, when a failure policy chooses `HANDOFF`. `RetryingFetcher` is
available for a small local retry loop; durable retries and delays belong in
Dramatiq for production work.

## Stores and local queues

Document and record stores use opaque references plus stable keys. Documents
are versioned; records can be keyed and replaced according to
`CollisionPolicy`. In-memory stores are useful for scripts and tests;
`PyMongoDocumentStore`, `PyMongoRecordStore`, and `PyMongoJobStore` are
available with the MongoDB extra.

For small scripts or notebooks, `InMemoryJobQueue` and `FlowRouter` provide a
simple way to drain a finite set of jobs. Wrap the queue in `StoredJobQueue`
with a `JobStore` to register accepted work and track its state:

```python
from longscrape import InputUrl, JobSpec, PipelineContext
from longscrape.runtime import Flow, FlowRouter, InMemoryJobQueue, StoredJobQueue

queue = StoredJobQueue(InMemoryJobQueue(), job_store)
context = PipelineContext(queue)
await queue.submit(JobSpec("article", InputUrl("https://example.com")))
await FlowRouter({"article": Flow(context).fetch(fetcher).extract(extractor).build()}).run(queue)
```

This local runner intentionally stays small. Use Dramatiq when jobs need
durability, delayed scheduling, retries, or multiple workers.

## Dramatiq execution

Install `longscrape[dramatiq]`, run Redis, and register flow factories at
module import time. `PipelineContext` is supplied by the adapter, so child-job
submission automatically targets the broker.

```python
from longscrape import InputUrl, JobSpec
from longscrape.orchestration import DramatiqApp, dramatiq_retries
from longscrape.runtime import Flow

app = DramatiqApp.redis(url="redis://localhost:6379/0")


@app.flow(kind="article", queue="scrape")
@dramatiq_retries(policy=policy, max_retries=3)
def article(context):
  return Flow(context).fetch(fetcher).extract(extractor).transform(sink).build()


await app.submit(JobSpec("article", InputUrl("https://example.com")))
```

Run the worker with `dramatiq your_module`. `RecoveryPolicy` decides whether a
failed observed stage should retry or fail; Dramatiq owns the backoff and job
delivery. `dramatiq_retries` intentionally keeps that recovery configuration
separate from job-kind and queue registration. A worker can be given a stable
`worker_id` through `DramatiqApp.redis` to process page-affine jobs on its own
queue.

## Browser fetching and page reuse

`BrowserManager` works with the built-in `PlaywrightBrowserProvider` or an
application-owned provider that implements the same small protocol. Pass a
`page_ready` coroutine to `BrowserFetcher` to wait for application-specific
content after navigation.

`BrowserFetcher(page_mode="reuse")` takes the live page from
`PipelineContext`; `page_mode="stored"` restores a page ID from job metadata.
Both modes are process-local. When passing a page ID to a child job, pin that
job to the browser-owning worker with `worker_id=context.require_worker_id()`.
They are not durable browser-session resume mechanisms.

The browser module also includes composable request middlewares for URL/content
blocking, caching, and rate limiting. See the page reuse and custom-provider
examples below for complete setups.

## Failures and observability

Pipeline stages ordinarily raise their own errors. Observability is optional
and lives in `longscrape.observability`, rather than in the stage contracts or
`Flow`. Its wrappers emit lifecycle events and re-raise the original exception
unchanged.

```python
from longscrape.observability import configure, observe_extractor, observe_fetch

observer = configure(logging_enabled=True)
fetcher = observe_fetch(fetcher, observer=observer)
extractor = observe_extractor(extractor, observer=observer)
flow = Flow().fetch(fetcher).extract(extractor).build()
```

Stages use ordinary `logging.getLogger()` calls. The observer installs scoped
metadata for lifecycle events; `StructlogSink` and `OpenTelemetrySink` are
opt-in adapters. Configure logging and OpenTelemetry exporters in the
application, not in the library.

`HttpxFetcher` and `BrowserFetcher` raise `HttpStatusError` for unsuccessful
responses. For HTTP 429, `HttpxFetcher` parses `Retry-After` into
`error.retry_after`, which a `RecoveryPolicy` can use when choosing a retry.

## Examples

Run these from the repository root:

- `uv run python -m examples.quotes` — a local queue, crawling follow-up jobs,
  cache, rate limiting, sinks, and optional MongoDB stores (`MONGODB_URI`).
- `uv run python -m examples.reextract` — extract stored documents without
  fetching again; set `MONGODB_URI` after running the quotes example.
- `uv run --extra browser python -m examples.reuse_page` — pass one live
  Playwright page between two local flows.
- `uv run --with patchright python -m examples.custom_browser` — supply a
  custom Patchright browser provider without coupling it to the package.
- `uv run --extra browser python -m examples.with_handoff` — recover a browser
  session through a headed manual login.
- `uv run --package longscrape --extra structlog --extra otel python -m examples.observability --structlog --otel`
  — standard logging, Structlog events, and OpenTelemetry spans.
- `uv run --package longscrape --extra dramatiq dramatiq examples.orchestration`
  — worker for the Redis/Dramatiq orchestration example; in another terminal,
  run `uv run --package longscrape --extra dramatiq python -m examples.orchestration`.
- `examples/browser_plugin` — a temporary Firefox extension and receiver for
  explicitly authorized browser captures; see its own README.
