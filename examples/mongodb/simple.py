import asyncio
import os

from longscrape import HttpxFetcher
from longscrape.mongodb import PyMongoDocumentStore, PyMongoRecordStore
from longscrape_core import InputUrl, Job, Record
from parsel import Selector

URL = "https://www.scrapethissite.com/pages/simple/"


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
    documents = PyMongoDocumentStore(uri)
    records = PyMongoRecordStore(uri)
    try:
        async with HttpxFetcher() as fetcher:
            job = Job(kind="countries", input=InputUrl(URL))
            document = await fetcher.fetch(job)
            await documents.save(document)
            for record in extract_countries(job, document):
                await records.save(record)
                print(record.data["name"])
    finally:
        await documents.close()
        await records.close()


if __name__ == "__main__":
    asyncio.run(main())
