"""
Probe Farnell's known public Search API (used by cpc.farnell.com).
Farnell exposes a documented REST API at api.element14.com
"""
import requests
import json

# Farnell/element14 public API - requires a free API key from
# https://partner.element14.com but let's first check what CPC's
# own headless backend exposes (the React app calls something)

API_KEY_SCRAPER = "84cedc1d8b5f91cfa84846e16aee0611"

# CPC's React frontend fetches from a GraphQL or REST backend.
# Common patterns for headless commerce (IBM WebSphere / SAP Hybris):
candidates = [
    # IBM WebSphere Commerce REST pattern
    "https://cpc.farnell.com/wcs/resources/store/10180/categoryview/@top?langId=-1&pageSize=25",
    "https://cpc.farnell.com/wcs/resources/store/10180/productview/byCategory/cable-leads-connectors?langId=-1&pageSize=25&pageNumber=1",
    # Solr search with JSON response
    "https://cpc.farnell.com/wcs/resources/store/10180/productview/bySearchTerm/*?langId=-1&pageSize=25&searchTerm=*&categoryId=audio-video-connectors",
    # GraphQL
    "https://cpc.farnell.com/graphql",
    # Direct search API
    "https://cpc.farnell.com/api/products?category=audio-video-connectors&pageSize=25",
]

headers = {
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0",
    "Referer": "https://cpc.farnell.com/c/cable-leads-connectors/connectors/audio-video-connectors",
    "x-requested-with": "XMLHttpRequest",
}

for url in candidates:
    proxy = f"http://api.scraperapi.com?api_key={API_KEY_SCRAPER}&url={requests.utils.quote(url, safe=':/?=&')}"
    print(f"\nTrying: {url[:120]}")
    try:
        r = requests.get(proxy, timeout=60, headers=headers)
        print(f"  Status: {r.status_code} | Content-Type: {r.headers.get('content-type','')[:60]}")
        print(f"  Body[:300]: {r.text[:300]}")
    except Exception as e:
        print(f"  ERROR: {e}")
