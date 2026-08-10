import pytest
from longscrape_core import CrawlJob, Extraction, SourceRecord


def test_crawl_job_round_trips_through_json() -> None:
    job = CrawlJob(
        kind="aleo.company_listing",
        query={"location": {"miasto": "Łódź"}},
        context={"requested_by": "csv"},
    )

    assert CrawlJob.from_json(job.to_json()) == job


def test_equivalent_jobs_have_same_fingerprint() -> None:
    first = CrawlJob(
        kind="aleo.company_listing",
        query={"count": 10, "location": {"miasto": "Łódź"}},
    )
    second = CrawlJob(
        kind="aleo.company_listing",
        query={"location": {"miasto": "Łódź"}, "count": 10},
    )

    assert first.fingerprint() == second.fingerprint()


def test_blank_job_kind_is_rejected() -> None:
    with pytest.raises(ValueError, match="kind"):
        CrawlJob(kind=" ", query={})


def test_extraction_contains_records_and_follow_ups() -> None:
    record = SourceRecord(
        id="aleo:company:example",
        kind="company_listing.details",
        provider="aleo",
        source_url="https://aleo.com/company/example",
        data={"record_type": "company", "name": "Example Sp. z o.o."},
    )
    follow_up = CrawlJob(
        kind="aleo.company_listing",
        query={"location": {"miasto": "Warszawa"}},
    )

    extraction = Extraction(
        records=(record,),
        follow_ups=(follow_up,),
    )

    assert extraction.records == (record,)
    assert extraction.follow_ups == (follow_up,)
