# Concepts and architecture

longscrape is built from a small set of explicit values and interfaces. An
application chooses its own runtime: it may process one job in a cron script,
work interactively in a Jupyter playbook, or dispatch jobs through Scrapy.
The libraries provide the vocabulary and adapters; they do not impose one
global worker or scheduling system.

## Core values

### `Job`

A `Job` is an initial unit of work. Its `kind` identifies the work that a
consumer supports, and its `context` carries JSON-compatible, application
specific information. Queues are kind-aware: a consumer calls
`dequeue(kind)` and therefore cannot claim a job intended for another
consumer.

Jobs are deliberately not requests. A job says what the application wants to
process; its input says what material is already available to do that work.
A fetcher, a direct extractor, or a Scrapy spider decides how to act on it.

### Job input types

Every job has exactly one explicit input:

| Type | Meaning | Typical use |
| --- | --- | --- |
| `InputUrl` | A non-blank URL to acquire. | Fetch a page with HTTP or a browser, or schedule a Scrapy request. |
| `InputQuery` | A JSON-compatible object describing a query. | Pass search parameters to application-specific logic or a spider. |
| `InputDocument` | A `Document` already acquired in memory. | Re-extract saved content, accept a browser capture, or parse without a network request. |

An input type is a useful boundary: code should check which input it supports
and fail clearly for the others instead of guessing how to interpret a job.

### `Document`

A `Document` is acquired source content. It contains its URL, bytes, content
type, status, headers, fetch time, and JSON-compatible metadata. The `text`
property decodes the bytes as UTF-8 with replacement for invalid sequences.

Documents are separate from jobs because the same content can be saved,
inspected, handed off, or extracted again without repeating acquisition.

### `Record`

A `Record` is structured data produced by extraction or transformation. It
has a `kind`, non-blank `source_url`, arbitrary `data`, optional originating
`Document`, metadata, and creation time. Keeping the source document attached
is optional, but useful when results must be audited or re-extracted later.

## Direct longscrape architecture

The usual direct-processing flow is:

```text
Job → Fetcher (when needed) → Document → Extractor → Record(s)
                                            │
                                            └─► discovered Job(s) → JobQueue

Record(s) → Transformer(s) → Record(s) → RecordStore / other sink
```

`longscrape-core` defines the interfaces and in-memory implementations.
`longscrape` supplies optional direct adapters, including HTTPX and browser
fetchers, browser capture, and MongoDB stores. The application owns the loop:
it selects jobs, calls the components, and decides how concurrency, retrying,
and lifecycle should work.

### Fetcher

A `Fetcher` acquires a `Document` from a `Job` whose input it understands.
For example, `HttpxFetcher` and the browser fetchers accept `InputUrl` jobs.
An `InputDocument` needs no fetch: the application can pass its document
directly to extraction.

### Extractor

An `Extractor` turns a job and document into zero or more records. It also
receives the `JobQueue`, allowing it to enqueue discovered jobs explicitly.
This is the extension point for parsing and for following links or spawning
later work; it is not a hidden crawler scheduler.

### Transformer

A `Transformer` maps one record to zero or more records. Use transformers for
normalisation, validation, enrichment, splitting, filtering, or other work
that does not acquire the original document. Applying zero outputs is the
normal way to drop a record.

### Stores and sinks

A `DocumentStore` saves and retrieves documents; a `RecordStore` saves
records. Both are deliberately small interfaces. In-memory stores serve tests
and one-process applications, while adapters such as the MongoDB stores add
persistence. A sink is the broader delivery idea: a record can be sent to a
store or to an application-specific destination with an equally small API.

## `longscrape-scrapy` integration

`longscrape-scrapy` lets core jobs run as in-process Scrapy crawls while
remaining compatible with normal Scrapy projects. `CrawlService` dequeues a
job by kind and starts the Scrapy spider registered under that kind. The
spider must inherit `JobSpider`.

The conceptual correspondence is:

| longscrape concept | Scrapy equivalent or location | Notes |
| --- | --- | --- |
| Fetcher | `Spider.start()` plus `scrapy.Request` | `JobSpider.start()` accepts the job; a subclass supplies initial requests through `start_job()`. |
| Extractor | `Spider.parse()` | A spider commonly extracts fields while parsing a response. With `UrlCrawler`, parsing can instead only wrap the fetched document, leaving extraction to a pipeline adapter. |
| Transformer | Scrapy item pipeline | `LongscrapePipeline` applies configured core transformers after converting an item to records. |
| Sink / record store | Scrapy item pipeline | `LongscrapePipeline` sends each resulting record to its configured `RecordSink` or `RecordStoreSink`. |
| Optional extractor with `UrlCrawler` | Scrapy item pipeline | A custom `ItemExtractor` can turn the `UrlCrawler` document item into records at the pipeline boundary. |

`JobSpider` is still a normal `scrapy.Spider`. With `InputUrl`, a subclass
implements `start_job()` and yields requests. With `InputDocument`,
`JobSpider.start()` constructs an in-memory response and invokes `parse()`, so
existing parsing code can work without making a request. With no job—such as
when run with `scrapy crawl` directly—it logs a warning and exits safely.

### Scrapy wrapper types

The integration offers wrapper types that retain longscrape context while
participating in Scrapy's normal lifecycle:

| Type | Purpose |
| --- | --- |
| `LongscrapeRequest` | A `scrapy.Request` that retains the originating core `Job`. |
| `LongscrapeResponse` | An `HtmlResponse` backed by a core `Document`; it can be made from either a document or a native response. |
| `LongscrapeDocumentItem` | A native `scrapy.Item` containing a core `Document` plus pending record data. |
| `LongscrapeRecordItem` | A native `scrapy.Item` representation of a core `Record`. |

Scrapy continues to use native `Request`, `Response`, and `Item` conventions
for compatibility with the broader Scrapy ecosystem. At the integration
boundary, data can be freely converted to and from `longscrape-core` types:
`LongscrapeResponse` exposes a `Document`, `LongscrapeDocumentItem` produces a
`Record`, and `LongscrapeRecordItem` converts directly to or from a `Record`.
Ordinary native items are also supported by `LongscrapePipeline` when they
provide a non-empty `source_url` field.

That conversion makes a Scrapy crawl one part of a larger longscrape workflow:
the same documents and records can be passed to existing scripts, Jupyter
playbooks, exploratory drafts, stores, and other application-owned tools.
