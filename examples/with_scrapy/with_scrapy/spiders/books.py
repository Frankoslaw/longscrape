from longscrape_core import InputUrl
from longscrape_scrapy import JobSpider, LongscrapeRequest

from with_scrapy.items import BookItem


class BooksSpider(JobSpider):
    name = "books"

    async def start_job(self):
        job = self.job
        if job is None or not isinstance(job.input, InputUrl):
            raise TypeError("BooksSpider requires an InputUrl job")
        yield LongscrapeRequest(job.input.url, callback=self.parse, job=job)

    def parse(self, response):
        for book in response.css("article.product_pod"):
            href = book.css("h3 a::attr(href)").get()
            if href is None:
                continue
            rating = book.css("p.star-rating::attr(class)").get(default="")
            yield BookItem(
                title=book.css("h3 a::attr(title)").get(default="").strip(),
                price=book.css(".price_color::text").get(default="").strip(),
                availability=book.css(".availability::text").get(default="").strip(),
                rating=rating.removeprefix("star-rating "),
                source_url=response.urljoin(href),
            )
