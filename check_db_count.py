import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

res = supabase.table("courses").select("url", count="exact").execute()
print(f"Total courses in DB: {res.count}")

if res.data:
    urls = [d['url'] for d in res.data]
    print(f"First 10 URLs:\n{chr(10).join(urls[:10])}")
