# longscrape-core

`longscrape-core` contains the small, framework-neutral vocabulary shared by
direct longscrape code and Scrapy integration. It does not execute crawls,
coordinate child work, rate-limit requests, or depend on browser libraries.

The application owns the processing loop:

```text
Job → Fetcher (when needed) → Document → Extractor → Transformer(s) → RecordStore
```

Jobs are initial queue inputs. Their input is explicit:

```python
from longscrape_core import (
    Document,
    InMemoryDocumentStore,
    InputDocument,
    InputQuery,
    InputUrl,
    Job,
)

url_job = Job(
    kind="company",
    input=InputUrl("https://example.com/company/acme"),
)

query_job = Job(
    kind="search",
    input=InputQuery({"name": "Acme", "country": "PL"}),
)

documents = InMemoryDocumentStore()
document_ref = await documents.save(
    Document(url="https://example.com", content=b"<html>...</html>")
)
document_job = Job(kind="company", input=InputDocument(document_ref))
```

`Job`, `Document`, and `Record` cross store boundaries by `JobRef`,
`DocumentRef`, and `RecordRef`. Jobs hold only JSON-safe values and document
references, so `job.to_json()` is safe to hand to durable infrastructure.

`JobStore` owns job data and lifecycle status. `JobQueue` only schedules refs:
it returns an expiring lease which can be acknowledged, retried, or extended.
This makes a crashed worker's lease reclaimable without tying persistence to a
queue implementation.

For most applications, use `JobManager(InMemoryJobStore(), InMemoryJobQueue())`.
Its `submit(job)` and `lease(kind)` methods coordinate the two protocols and
return a managed lease whose `acknowledge()`, `retry(error)`, `fail(error)`, and
`extend()` methods update the right state. Advanced infrastructure can use the independent
stores and queue protocols directly.

`InMemoryJobStore`, `InMemoryJobQueue`, `InMemoryDocumentStore`, and
`InMemoryRecordStore` are process-local implementations for single-process
applications and tests.
