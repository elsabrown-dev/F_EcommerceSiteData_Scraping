import requests
from bs4 import BeautifulSoup
import re

API_KEY = "84cedc1d8b5f91cfa84846e16aee0611"

url = "https://cpc.farnell.com/c/cable-leads-connectors/connectors/audio-video-connectors?pageSize=100&start=0"
proxy = f"http://api.scraperapi.com?api_key={API_KEY}&url={requests.utils.quote(url, safe=':/?=&')}"
print(f"Trying: {url}")
r = requests.get(proxy, timeout=120)
print(f"STATUS: {r.status_code}")
soup = BeautifulSoup(r.text, "html.parser")
print(f"TITLE: {soup.title.string if soup.title else 'N/A'}")

# /dp/ links
links = soup.find_all("a", href=re.compile(r"/dp/"))
print(f"/dp/ LINKS: {len(links)}")
for l in links[:10]:
    print("  ", l["href"])

# pagination
pag = soup.find_all("a", href=re.compile(r"start=", re.I))
print(f"PAGINATION LINKS: {len(pag)}")
for p in pag[:5]:
    print("  ", p.get("href",""), "|", p.get_text(strip=True))

# JSON embedded URLs
json_dp = re.findall(r'"(?:url|href)"\s*:\s*"(/[^"]+/dp/[^"]+)"', r.text)
print(f"JSON /dp/ refs: {len(json_dp)}")
for j in json_dp[:10]:
    print("  ", j)

# Any anchor with product-like href
all_anchors = soup.find_all("a", href=True)
print(f"\nTotal anchors: {len(all_anchors)}")
sample = [a["href"] for a in all_anchors if "/dp/" in a["href"] or "product" in a["href"].lower()]
print(f"Product-like anchors: {len(sample)}")
for s in sample[:10]:
    print("  ", s)

# Raw HTML snippet to understand structure
print("\n--- RAW HTML (chars 0-5000) ---")
print(r.text[:5000])
