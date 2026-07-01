import scrapy
import json
import re
from myproject.items import CourseItem

class BrilliantSpider(scrapy.spiders.SitemapSpider):
    name = "brilliant"
    allowed_domains = ["brilliant.org"]
    sitemap_urls = ["https://brilliant.org/courses-sitemap.xml"]
    sitemap_rules = [
        ('/courses/[^/]+/$', 'parse_course'),
    ]

    def parse_course(self, response):
        script_data = response.xpath('//script[@id="__NEXT_DATA__"]/text()').get()
        if not script_data:
            return

        try:
            data = json.loads(script_data)
            apollo_state = data.get('props', {}).get('pageProps', {}).get('apolloState', {})
            
            # Find the course object in apolloState
            course_data = None
            for key, value in apollo_state.items():
                if key.startswith('Course:') and value.get('__typename') == 'Course':
                    course_data = value
                    break
            
            if not course_data:
                return

            item = CourseItem()
            item['title'] = course_data.get('title')
            item['url'] = response.url
            item['description'] = course_data.get('description')
            item['intro_text'] = course_data.get('introText')
            item['lesson_count'] = course_data.get('lessonCount')
            
            chapters = []
            activities = []
            gameboard = course_data.get('gameboard', {})
            levels = gameboard.get('levels', [])
            
            for level in levels:
                chapter = {
                    'name': level.get('name'),
                    'slug': level.get('slug'),
                    'lessons': []
                }
                nodes = level.get('nodesV2', [])
                for node in nodes:
                    node_data = {
                        'title': node.get('title'),
                        'url': response.urljoin(node.get('contentUrl')) if node.get('contentUrl') else None,
                        'type': node.get('__typename'),
                        'slug': node.get('lessonSlug') or node.get('practiceSlug')
                    }
                    
                    # If it has a practice slug, it's an activity
                    if node.get('nextPracticeSlug'):
                        activity_url = f"https://brilliant.org/practice/{node.get('nextPracticeSlug')}/"
                        activities.append({
                            'title': f"Practice: {node.get('title')}",
                            'url': activity_url,
                            'parent_lesson': node.get('title')
                        })
                    
                    chapter['lessons'].append(node_data)
                chapters.append(chapter)
            
            item['chapters'] = chapters
            item['activities'] = activities
            yield item

        except Exception as e:
            self.logger.error(f"Error parsing {response.url}: {e}")
