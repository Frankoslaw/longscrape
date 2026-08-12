import scrapy
from longscrape_core import InputUrl
from longscrape_scrapy import JobSpider

from with_scrapy.loaders import BookLoader


class BooksSpider(JobSpider):
    name = "books"

    async def start_job(self):
        job = self.job
        if job is None or not isinstance(job.input, InputUrl):
            raise TypeError("BooksSpider requires an InputUrl job")
        yield scrapy.Request(job.input.url, callback=self.parse)

    def parse(self, response):
        for book in response.css("article.product_pod"):
            loader = BookLoader(selector=book, response=response)
            loader.add_css("title", "h3 a::attr(title)")
            loader.add_css("price", ".price_color::text")
            loader.add_css("availability", ".availability::text")
            loader.add_css(
                "rating", "p.star-rating::attr(class)", re=r"star-rating (.+)"
            )
            href = book.css("h3 a::attr(href)").get()
            if href is None:
                continue
            loader.add_value("source_url", response.urljoin(href))
            yield loader.load_item()
