from datetime import datetime

from itemloaders.processors import MapCompose, TakeFirst
from scrapy.item import Field, Item


def remove_quotes(text):
    # strip the unicode quotes
    text = text.strip("\u201c\u201d")
    return text


def convert_date(text):
    # convert string March 14, 1879 to Python date
    return datetime.strptime(text, "%B %d, %Y")


def parse_location(text):
    # parse location "in Ulm, Germany"
    # this simply remove "in ", you can further parse city, state, country, etc.
    return text[3:]


class QuoteItem(Item):
    quote_content = Field(
        input_processor=MapCompose(remove_quotes),
        # TakeFirst return the first value not the whole list
        output_processor=TakeFirst(),
    )
    author_name = Field(
        input_processor=MapCompose(str.strip), output_processor=TakeFirst()
    )
    author_birthday = Field(
        input_processor=MapCompose(convert_date), output_processor=TakeFirst()
    )
    author_bornlocation = Field(
        input_processor=MapCompose(parse_location), output_processor=TakeFirst()
    )
    author_bio = Field(
        input_processor=MapCompose(str.strip), output_processor=TakeFirst()
    )
    tags = Field()
