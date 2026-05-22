"""
Probe CPC Farnell's internal product listing API.
CPC/Farnell uses an SOLR-based search API endpoint.
"""
import requests
import json

API_KEY = "84cedc1d8b5f91cfa84846e16aee0611"

# Known Farnell/CPC API endpoints to try
candidates = [
    # Farnell search API (used by cpc.farnell.com)
    "https://cpc.farnell.com/api/2.0/page/products/category?lang=en_GB&currentPage=1&pageSize=25&categoryPath=cable-leads-connectors%2Fconnectors%2Faudio-video-connectors",
    "https://cpc.farnell.com/api/2.0/page/products/category?lang=en_GB&currentPage=1&pageSize=25&categoryPath=audio-video-connectors",
    # Headless API pattern
    "https://cpc.farnell.com/headless/api/products?category=audio-video-connectors&pageSize=25&page=1",
    # Solr/search pattern
    "https://cpc.farnell.com/search?term=&categoryPath=cable-leads-connectors%2Fconnectors%2Faudio-video-connectors&pageSize=25&start=0&view=list&format=json",
]

headers = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://cpc.farnell.com/c/cable-leads-connectors/connectors/audio-video-connectors",
}

for url in candidates:
    proxy = f"http://api.scraperapi.com?api_key={API_KEY}&url={requests.utils.quote(url, safe=':/?=&')}"
    print(f"\nTrying: {url[:100]}...")
    try:
        r = requests.get(proxy, timeout=60, headers=headers)
        print(f"  Status: {r.status_code}")
        ct = r.headers.get("content-type", "")
        print(f"  Content-Type: {ct}")
        snippet = r.text[:500]
        print(f"  Body: {snippet}")
    except Exception as e:
        print(f"  ERROR: {e}")
