from longscrape.core.doamin.pipeline import ExtractionResult, ScraperTask
from longscrape.core.ports.pipeline import ExtractorPort, FetcherPort
from longscrape.logging import get_logger

logger = get_logger(__name__)


class ScraperWorker[T]:
    def __init__(
        self,
        fetcher: FetcherPort,
        extractor: ExtractorPort[T],
        *,
        task_kind: str | None = None,
    ):
        self.fetcher = fetcher
        self.extractor = extractor
        self.task_kind = task_kind

    def is_compatible(self, task: ScraperTask) -> bool:
        return self.task_kind is None or task.kind == self.task_kind

    async def run(self, task: ScraperTask) -> ExtractionResult[T]:
        if not self.is_compatible(task):
            logger.error("task rejected: id=%s kind=%s", task.id, task.kind)
            raise ValueError(f"Worker incompatible with task: {task.kind}")

        logger.info("task started: id=%s kind=%s", task.id, task.kind)
        try:
            logger.debug("fetching task: id=%s", task.id)
            raw_entry = await self.fetcher.fetch(task)
        except Exception:
            logger.exception("fetch failed: id=%s kind=%s", task.id, task.kind)
            raise

        logger.info(
            "fetch complete: id=%s status=%s url=%s",
            task.id,
            raw_entry.status_code,
            raw_entry.url,
        )
        if not self.extractor.is_compatible(raw_entry):
            logger.error("entry rejected: id=%s url=%s", task.id, raw_entry.url)
            raise ValueError(f"Extractor incompatible with URL: {raw_entry.url}")

        try:
            logger.debug("extracting entry: id=%s url=%s", task.id, raw_entry.url)
            extraction = await self.extractor.extract(task, raw_entry)
        except Exception:
            logger.exception("extraction failed: id=%s url=%s", task.id, raw_entry.url)
            raise

        logger.info(
            "task complete: id=%s items=%d tasks=%d",
            task.id,
            len(extraction.items),
            len(extraction.tasks),
        )
        return extraction
