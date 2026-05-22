"""
Fetches all product URLs for a given CPC category by scanning the sitemaps.
Usage:
    python get_category_urls.py audio-video-connectors
Outputs a text file: <category-slug>_urls.txt
"""
import requests
import re
import sys
import time

API_KEY = "84cedc1d8b5f91cfa84846e16aee0611"

SITEMAP_INDEX = "https://cpc.farnell.com/sitemap.xml"

# Only the pdpd (product) sitemaps — skip category/brand/custom
PRODUCT_SITEMAP_PATTERN = re.compile(r'cpc-pdpd-[A-Z]+\.xml')


def fetch(url, retries=3):
    proxy = f"http://api.scraperapi.com?api_key={API_KEY}&url={requests.utils.quote(url, safe=':/?=&')}"
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(proxy, timeout=60)
            r.raise_for_status()
            return r.text
        except Exception as e:
            print(f"  Attempt {attempt} failed for {url}: {e}")
            time.sleep(2)
    return ""


def get_product_sitemaps():
    print("Fetching sitemap index...")
    xml = fetch(SITEMAP_INDEX)
    urls = re.findall(r'<loc>(https://cpc\.farnell\.com[^<]+)</loc>', xml)
    product_sitemaps = [u for u in urls if PRODUCT_SITEMAP_PATTERN.search(u)]
    print(f"Found {len(product_sitemaps)} product sitemap files.")
    return product_sitemaps


def get_urls_for_category(category_slug):
    sitemaps = get_product_sitemaps()
    matched_urls = []

    for i, sitemap_url in enumerate(sitemaps, 1):
        print(f"[{i}/{len(sitemaps)}] Scanning: {sitemap_url.split('/')[-1]}")
        xml = fetch(sitemap_url)
        if not xml:
            continue

        # Each <url> block contains <loc> and optionally other tags
        # Product URLs look like: https://cpc.farnell.com/.../dp/XXXX
        all_locs = re.findall(r'<loc>(https://cpc\.farnell\.com[^<]+)</loc>', xml)

        # Filter by category slug appearing in the URL
        matched = [u for u in all_locs if category_slug.lower() in u.lower()]
        print(f"  -> {len(matched)} matches out of {len(all_locs)} URLs")
        matched_urls.extend(matched)
        time.sleep(0.3)

    # Deduplicate
    unique = list(dict.fromkeys(matched_urls))
    print(f"\nTotal unique URLs for '{category_slug}': {len(unique)}")
    return unique


if __name__ == "__main__":
    category = sys.argv[1] if len(sys.argv) > 1 else "audio-video-connectors"
    urls = get_urls_for_category(category)

    out_file = f"{category}_urls.txt"
    with open(out_file, "w", encoding="utf-8") as f:
        for u in urls:
            f.write(u + "\n")

    print(f"Saved {len(urls)} URLs to {out_file}")
