import requests
import re
import json

url = "https://brilliant.org/courses/complex-plane/complex-multiplication/multiple-rotations/"
response = requests.get(url)
match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', response.text)
if match:
    data = json.loads(match.group(1))
    # Filter for anything interesting
    apollo = data.get('props', {}).get('pageProps', {}).get('apolloState', {})
    for key, value in apollo.items():
        if isinstance(value, dict) and value.get('__typename') in ['Interaction', 'Step', 'Card', 'Question']:
            print(f"--- {value.get('__typename')}: {key} ---")
            print(json.dumps(value, indent=2))
else:
    print("Not found")
