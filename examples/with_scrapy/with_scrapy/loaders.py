from itemloaders import ItemLoader
from itemloaders.processors import Identity, MapCompose, TakeFirst

from with_scrapy.items import BookItem, QuoteItem


def strip(value: str) -> str:
    return value.strip()


class QuoteLoader(ItemLoader):
    default_item_class = QuoteItem
    default_input_processor = MapCompose(strip)
    default_output_processor = TakeFirst()
    tags_out = Identity()


class BookLoader(ItemLoader):
    default_item_class = BookItem
    default_input_processor = MapCompose(strip)
    default_output_processor = TakeFirst()
