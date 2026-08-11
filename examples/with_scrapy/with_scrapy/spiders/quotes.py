import scrapy
from longscrape_scrapy import JobSpider

from with_scrapy.loaders import QuoteLoader


class QuotesSpider(JobSpider):
    name = "quotes"

    async def start(self):
        yield scrapy.Request(self.job.query["url"], callback=self.parse)

    def parse(self, response):
        for quote in response.css(".quote"):
            loader = QuoteLoader(selector=quote, response=response)
            loader.add_css("text", ".text::text")
            loader.add_css("author", ".author::text")
            loader.add_css("tags", ".tags a::text")
            loader.add_value("source_url", response.url)
            yield loader.load_item()
