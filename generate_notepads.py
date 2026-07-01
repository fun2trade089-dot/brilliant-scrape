import os
import json
from supabase import create_client
from dotenv import load_dotenv

# 1. Load credentials
load_dotenv()
url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_KEY')

if not url or not key or "your_" in url:
    print("Error: Please check your .env file and ensure SUPABASE_URL and SUPABASE_KEY are correct.")
    exit(1)

try:
    supabase = create_client(url, key)

    # 2. Fetch Data
    print("Fetching data from Supabase...")
    courses_res = supabase.table("courses").select("title, url, description").execute()
    activities_res = supabase.table("activities").select("title, url").execute()

    # 3. Create Courses Notepad File
    print("Creating courses.txt...")
    with open("courses.txt", "w", encoding="utf-8") as f:
        f.write("--- BRILLIANT COURSES LIST ---\n\n")
        for i, c in enumerate(courses_res.data, 1):
            f.write(f"{i}. {c['title']}\n")
            f.write(f"   URL: {c['url']}\n")
            f.write(f"   About: {c['description']}\n")
            f.write("-" * 40 + "\n")

    # 4. Create Activities Notepad File
    print("Creating activity_urls.txt...")
    with open("activity_urls.txt", "w", encoding="utf-8") as f:
        f.write("--- BRILLIANT ACTIVITY & PRACTICE LINKS ---\n\n")
        for i, a in enumerate(activities_res.data, 1):
            f.write(f"{i}. {a['title']}\n")
            f.write(f"   LINK: {a['url']}\n")
            f.write("-" * 30 + "\n")

    print("\nSUCCESS!")
    print("You can now open these files in Notepad:")
    print("1. courses.txt")
    print("2. activity_urls.txt")

except Exception as e:
    print(f"Error: {e}")
