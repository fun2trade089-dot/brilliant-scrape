import os
from supabase import create_client, Client
from dotenv import load_dotenv
import logging

load_dotenv()

class SupabasePipeline:
    def __init__(self):
        self.url = os.environ.get("SUPABASE_URL")
        self.key = os.environ.get("SUPABASE_KEY")
        self.supabase: Client = create_client(self.url, self.key)

    def process_item(self, item, spider):
        spider.logger.info(f"--- Pipeline: Processing {item.get('title')} ---")
        
        course_data = {
            "title": item.get("title"),
            "url": item.get("url"),
            "description": item.get("description"),
            "intro_text": item.get("intro_text"),
            "lesson_count": item.get("lesson_count"),
            "chapters": item.get("chapters")
        }
        
        try:
            # 1. Upsert Course
            # We use select() at the end to ensure we get the ID back even on update
            res = self.supabase.table("courses").upsert(course_data, on_conflict="url").execute()
            
            if not res.data:
                # If upsert doesn't return data (sometimes happens on no-op updates), 
                # we fetch the ID manually
                spider.logger.info("Upsert returned no data, fetching ID manually...")
                existing = self.supabase.table("courses").select("id").eq("url", item.get("url")).execute()
                course_id = existing.data[0]['id'] if existing.data else None
            else:
                course_id = res.data[0]['id']
            
            if not course_id:
                spider.logger.error(f"Failed to get/create course_id for {item.get('url')}")
                return item

            spider.logger.info(f"Course ID verified: {course_id}")

            # 2. Upsert Activities
            activities = item.get("activities", [])
            if activities:
                spider.logger.info(f"Inserting {len(activities)} activities...")
                for activity in activities:
                    activity_data = {
                        "course_id": course_id,
                        "title": activity.get("title"),
                        "url": activity.get("url"),
                        "parent_lesson": activity.get("parent_lesson")
                    }
                    # Small delay or batching isn't needed here for small sets, but we log errors
                    try:
                        self.supabase.table("activities").upsert(activity_data, on_conflict="url").execute()
                    except Exception as act_e:
                        spider.logger.error(f"Failed to insert activity {activity.get('url')}: {act_e}")
                spider.logger.info("Activities processing complete")
            else:
                spider.logger.warning(f"No activities found for course: {item.get('title')}")
                    
        except Exception as e:
            spider.logger.error(f"SUPABASE PIPELINE CRITICAL ERROR: {e}")

        return item
