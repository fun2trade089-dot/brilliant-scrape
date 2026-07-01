import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_KEY')

print(f"Connecting to: {url}")
try:
    supabase = create_client(url, key)
    test_data = {'title': 'Test Connection', 'url': 'https://test-connection.com'}
    print(f"Attempting to insert test row: {test_data}")
    
    response = supabase.table('courses').upsert(test_data, on_conflict='url').execute()
    
    print("\n--- RESULT ---")
    if response.data:
        print("SUCCESS! Data was written to the database.")
        print(f"Returned row: {response.data}")
    else:
        print("FAILED: No data returned. Check Row Level Security (RLS) policies.")
        
except Exception as e:
    print("\n--- ERROR ---")
    print(f"Type: {type(e).__name__}")
    print(f"Message: {e}")
    if '42501' in str(e):
        print("\nSUGGESTION: This is a Permission Error (RLS). You MUST use the 'service_role' key in your .env file or disable RLS in the Supabase dashboard.")
