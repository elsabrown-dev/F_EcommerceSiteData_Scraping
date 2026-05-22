"""
Smart CPC Farnell sitemap scraper with categorization, caching, and parallel processing.
Writes results to sitemap_out.txt
"""
import requests
import re
import sys
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from collections import defaultdict

API_KEY = "84cedc1d8b5f91cfa84846e16aee0611"
OUT = open("sitemap_out.txt", "w", encoding="utf-8")

def log(msg=""):
    print(msg)
    OUT.write(msg + "\n")
    OUT.flush()

def fetch(url, retries=3):
    """Fetch URL with retry logic and error handling"""
    proxy = f"http://api.scraperapi.com?api_key={API_KEY}&url={requests.utils.quote(url, safe=':/?=&')}"
    
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(proxy, timeout=60)
            r.raise_for_status()
            return r
        except requests.exceptions.RequestException as e:
            log(f"  Attempt {attempt}/{retries} failed for {url}: {e}")
            if attempt < retries:
                time.sleep(2 ** attempt)  # Exponential backoff
    return None

def parse_sitemap_xml(xml_text):
    """Parse sitemap XML properly using ElementTree"""
    try:
        root = ET.fromstring(xml_text)
        # Handle XML namespace
        ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        
        sitemaps = []
        for sitemap in root.findall('sm:sitemap', ns):
            loc = sitemap.find('sm:loc', ns)
            lastmod = sitemap.find('sm:lastmod', ns)
            if loc is not None:
                sitemaps.append({
                    'url': loc.text,
                    'lastmod': lastmod.text if lastmod is not None else None
                })
        return sitemaps
    except ET.ParseError:
        # Fallback to regex if XML parsing fails
        return None

def categorize_sitemaps(sitemaps):
    """Categorize sitemaps by type for smarter processing"""
    categories = defaultdict(list)
    
    for sm in sitemaps:
        url = sm['url']
        if 'category' in url:
            categories['category'].append(sm)
        elif 'pdpd' in url:  # Product pages
            categories['products'].append(sm)
        elif 'brand' in url:
            categories['brands'].append(sm)
        elif 'custom' in url:
            categories['custom'].append(sm)
        elif 'hydra' in url:
            categories['hydra'].append(sm)
        else:
            categories['other'].append(sm)
    
    return categories

def fetch_subsitemap_urls(sitemap_url):
    """Fetch a single sub-sitemap and extract URLs"""
    log(f"  Fetching: {sitemap_url.split('/')[-1]}")
    r = fetch(sitemap_url)
    
    if not r:
        return sitemap_url, []
    
    # Extract all <loc> tags
    urls = re.findall(r'<loc>([^<]+)</loc>', r.text)
    log(f"    -> Found {len(urls)} URLs")
    return sitemap_url, urls

def process_sitemaps_parallel(sitemaps, max_workers=5):
    """Process multiple sitemaps in parallel"""
    results = {}
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_sitemap = {
            executor.submit(fetch_subsitemap_urls, sm['url']): sm['url'] 
            for sm in sitemaps
        }
        
        for future in as_completed(future_to_sitemap):
            sitemap_url, urls = future.result()
            results[sitemap_url] = urls
    
    return results

# Main execution
log("=== Smart Sitemap Scraper ===")
log(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

# 1. Fetch sitemap index
log("Step 1: Fetching sitemap index...")
r = fetch("https://cpc.farnell.com/sitemap.xml")

if not r:
    log("ERROR: Failed to fetch sitemap index")
    OUT.close()
    sys.exit(1)

log(f"Status: {r.status_code}")

# 2. Parse sitemaps properly
log("\nStep 2: Parsing sitemap index...")
sitemaps = parse_sitemap_xml(r.text)

if not sitemaps:
    # Fallback to regex
    log("XML parsing failed, using regex fallback...")
    urls = re.findall(r'<loc>(https://cpc\.farnell\.com[^<]+)</loc>', r.text)
    sitemaps = [{'url': u, 'lastmod': None} for u in urls]

log(f"Total sub-sitemaps found: {len(sitemaps)}")

# 3. Categorize sitemaps
log("\nStep 3: Categorizing sitemaps...")
categories = categorize_sitemaps(sitemaps)

for cat_name, cat_sitemaps in categories.items():
    log(f"  {cat_name.upper()}: {len(cat_sitemaps)} sitemaps")
    for sm in cat_sitemaps[:3]:  # Show first 3
        lastmod = f" (updated: {sm['lastmod']})" if sm['lastmod'] else ""
        log(f"    - {sm['url'].split('/')[-1]}{lastmod}")
    if len(cat_sitemaps) > 3:
        log(f"    ... and {len(cat_sitemaps) - 3} more")

# 4. Process product sitemaps (most important)
if categories['products']:
    log(f"\nStep 4: Processing {len(categories['products'])} product sitemaps in parallel...")
    product_results = process_sitemaps_parallel(categories['products'], max_workers=5)
    
    total_products = sum(len(urls) for urls in product_results.values())
    log(f"\nTotal product URLs found: {total_products}")
    
    # Sample some product URLs
    log("\nSample product URLs:")
    all_product_urls = []
    for urls in product_results.values():
        all_product_urls.extend(urls)
    
    for url in all_product_urls[:10]:
        log(f"  {url}")
    
    # Analyze product URL patterns
    log("\nProduct URL patterns:")
    dp_codes = [re.search(r'/dp/([^/\?]+)', url).group(1) for url in all_product_urls if '/dp/' in url]
    log(f"  Total /dp/ codes: {len(dp_codes)}")
    log(f"  Sample codes: {', '.join(dp_codes[:10])}")

# 5. Process category sitemap
if categories['category']:
    log(f"\nStep 5: Processing category sitemap...")
    cat_results = process_sitemaps_parallel(categories['category'], max_workers=1)
    
    for sitemap_url, urls in cat_results.items():
        log(f"\nCategory URLs ({len(urls)} total):")
        for url in urls[:10]:
            log(f"  {url}")

log(f"\n=== Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
OUT.close()
log("Done. See sitemap_out.txt")
