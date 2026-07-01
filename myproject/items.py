# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class CourseItem(scrapy.Item):
    title = scrapy.Field()
    url = scrapy.Field()
    description = scrapy.Field()
    intro_text = scrapy.Field()
    lesson_count = scrapy.Field()
    chapters = scrapy.Field()
    activities = scrapy.Field()


