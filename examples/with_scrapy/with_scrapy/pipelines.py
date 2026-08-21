import structlog

logger = structlog.get_logger()


class PrettyPrintQuotesPipeline:
    def process_item(self, item):
        """Pretty-prints scraped quote items to the terminal using structlog."""
        logger.info(
            "quote_scraped",
            author=item.get("author_name"),
            quote=item.get("quote_content"),
            tags=item.get("tags", []),
            birthday=item.get("author_birthday"),
            born_location=item.get("author_bornlocation"),
        )
        return item
