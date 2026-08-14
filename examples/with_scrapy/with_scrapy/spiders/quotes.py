import scrapy
from longscrape_core import InputUrl
from longscrape_scrapy import JobSpider, LongscrapeRequest

from with_scrapy.items import QuoteItem


class QuotesSpider(JobSpider):
    name = "quotes"
    start_urls = ["https://quotes.toscrape.com/page/1/"]

    async def start(self):
        job = self.job
        if job is not None:
            if not isinstance(job.input, InputUrl):
                raise TypeError("QuotesSpider requires an InputUrl job")
            # LongscrapeRequest keeps the initiating Job available on the request.
            yield LongscrapeRequest(job.input.url, callback=self.parse, job=job)
            return

        # Preserve normal Scrapy behavior under ``scrapy crawl quotes``.
        async for request in scrapy.Spider.start(self):
            yield request

    def parse(self, response):
        for quote in response.css(".quote"):
            yield QuoteItem(
                text=quote.css(".text::text").get(default="").strip(),
                author=quote.css(".author::text").get(default="").strip(),
                tags=quote.css(".tags a::text").getall(),
                source_url=response.url,
            )
        next_page = response.css("li.next a::attr(href)").get()
        if next_page is not None:
            yield response.follow(next_page, callback=self.parse)
