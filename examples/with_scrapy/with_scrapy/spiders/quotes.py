import scrapy
from longscrape_core import InputUrl
from longscrape_scrapy import JobSpider

from with_scrapy.loaders import QuoteLoader


class QuotesSpider(JobSpider):
    name = "quotes"

    async def start_job(self):
        job = self.job
        if job is None or not isinstance(job.input, InputUrl):
            raise TypeError("QuotesSpider requires an InputUrl job")
        yield scrapy.Request(job.input.url, callback=self.parse)

    def parse(self, response):
        for quote in response.css(".quote"):
            loader = QuoteLoader(selector=quote, response=response)
            loader.add_css("text", ".text::text")
            loader.add_css("author", ".author::text")
            loader.add_css("tags", ".tags a::text")
            loader.add_value("source_url", response.url)
            yield loader.load_item()
