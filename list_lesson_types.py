import requests
import re
import json

url = "https://brilliant.org/courses/complex-plane/complex-multiplication/multiple-rotations/"
response = requests.get(url)
match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', response.text)
if match:
    data = json.loads(match.group(1))
    apollo = data.get('props', {}).get('pageProps', {}).get('apolloState', {})
    types = set(v.get('__typename') for v in apollo.values() if isinstance(v, dict))
    print("\n".join(sorted(types)))
else:
    print("Not found")
