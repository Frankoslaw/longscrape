# longscrape

**Author:** Franciszek Łopuszański

## Aim

longscrape is an embeddable scraping framework for applications that need to
own their execution model. It is intended to work equally well in a small,
purpose-built script—such as a cron job or a Jupyter playbook—and in a more
powerful crawling system built on Scrapy through `longscrape-scrapy`.

The project separates a small, framework-neutral core from optional adapters:

- `longscrape-core` defines the shared job, document, record, queue, store,
  extraction, and transformation vocabulary.
- `longscrape` provides direct adapters such as HTTP and browser fetchers,
  capture handling, and MongoDB stores.
- `longscrape-scrapy` connects core jobs to Scrapy spiders and item pipelines
  for crawler-based systems.

This separation lets an application begin with a single, non-concurrent job
and grow towards a distributed job crawler at the scale of Frontera, without
forcing the same runtime model on every use case.

## Direction

The library is intended to make common operational features composable rather
than hidden behind a fixed worker framework. Its direction includes:

- manual handoff of jobs and acquired documents between people or systems;
- a simple sink API for delivering extracted records;
- captcha handling; and
- LLM integrations.

These are design goals; features not yet implemented should be treated as
planned work rather than part of the current public API.

## License notice

longscrape is licensed under the **Big Time Public License, version 2.0.2**.
It permits non-commercial and qualifying small-business use, while larger
businesses need to follow its commercial-licensing terms. See the complete,
controlling [LICENSE](LICENSE) text.
