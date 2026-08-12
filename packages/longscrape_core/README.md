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
from longscrape_core import Document, InputDocument, InputQuery, InputUrl, Job

url_job = Job(
    kind="company",
    input=InputUrl("https://example.com/company/acme"),
)

query_job = Job(
    kind="search",
    input=InputQuery({"name": "Acme", "country": "PL"}),
)

document_job = Job(
    kind="company",
    input=InputDocument(
        Document(url="https://example.com", content=b"<html>...</html>")
    ),
)
```

`Fetcher`, `Extractor`, and `Transformer` are structural protocols. Extractors
receive the core queue and may enqueue discovered jobs directly. Queue consumers
claim one explicit kind at a time with `dequeue(kind)`; no consumer can
accidentally take work intended for another backend.

`InMemoryJobQueue`, `InMemoryDocumentStore`, and `InMemoryRecordStore` are
process-local implementations for single-process applications and tests.
