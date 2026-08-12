import asyncio
import os

from longscrape.mongodb import PyMongoDocumentStore, PyMongoRecordStore
from longscrape_core import InputDocument, Job, Record
from parsel import Selector


def extract_countries(job: Job, document) -> list[Record]:
    selector = Selector(text=document.text)
    return [
        Record(
            kind=job.kind,
            source_url=document.url,
            document=document,
            data={"name": name.strip()},
        )
        for name in selector.css(".country-name::text").getall()
    ]


async def main() -> None:
    uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
    url = os.environ.get("DOCUMENT_URL", "https://www.scrapethissite.com/pages/simple/")
    documents = PyMongoDocumentStore(uri)
    records = PyMongoRecordStore(uri)
    try:
        document = await documents.get(url)
        if document is None:
            raise RuntimeError("No stored document found; run simple.py first")
        job = Job(kind="countries", input=InputDocument(document))
        for record in extract_countries(job, document):
            await records.save(record)
            print(record.data["name"])
    finally:
        await documents.close()
        await records.close()


if __name__ == "__main__":
    asyncio.run(main())
