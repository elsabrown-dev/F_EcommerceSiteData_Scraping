"""
Complete pipeline to scrape 1,050 products and save to test.csv
"""
import requests
import re
import csv
import time
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

API_KEY = "84cedc1d8b5f91cfa84846e16aee0611"
TARGET_PRODUCTS = 1050
MAX_WORKERS = 2  # Reduced to avoid rate limits
OUTPUT_FILE = "test.csv"
REQUEST_DELAY = 2  # Seconds between requests

def fetch(url, retries=3):
    """Fetch URL with retry logic"""
    proxy = f"http://api.scraperapi.com?api_key={API_KEY}&url={requests.utils.quote(url, safe=':/?=&')}"
    
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(proxy, timeout=120)
            r.raise_for_status()
            return r
        except Exception as e:
            print(f"  Retry {attempt}/{retries} for {url}: {e}")
            if attempt < retries:
                time.sleep(2)
    return None

def get_product_urls(limit=1050):
    """Get product URLs from sitemap"""
    print(f"Fetching product URLs (target: {limit})...")
    
    # Get sitemap index
    r = fetch("https://cpc.farnell.com/sitemap.xml")
    if not r:
        return []
    
    # Find product sitemaps
    product_sitemaps = re.findall(r'<loc>(https://cpc\.farnell\.com[^<]*cpc-pdpd-[^<]+\.xml)</loc>', r.text)
    print(f"Found {len(product_sitemaps)} product sitemaps")
    
    all_urls = []
    
    # Fetch URLs from each sitemap until we have enough
    for i, sitemap_url in enumerate(product_sitemaps, 1):
        if len(all_urls) >= limit:
            break
            
        print(f"[{i}/{len(product_sitemaps)}] Fetching: {sitemap_url.split('/')[-1]}")
        r = fetch(sitemap_url)
        if not r:
            continue
        
        urls = re.findall(r'<loc>(https://cpc\.farnell\.com[^<]+/dp/[^<]+)</loc>', r.text)
        all_urls.extend(urls)
        print(f"  -> {len(urls)} URLs (total: {len(all_urls)})")
        
        if len(all_urls) >= limit:
            break
    
    return all_urls[:limit]

def scrape_product(url):
    """Scrape a single product page"""
    try:
        r = fetch(url)
        if not r:
            return None
        
        soup = BeautifulSoup(r.text, "html.parser")
        data = {}
        
        # Category from breadcrumb
        breadcrumb = soup.find("nav", {"aria-label": re.compile("breadcrumb", re.I)})
        if breadcrumb:
            links = breadcrumb.find_all("a")
            data["category"] = links[-1].get_text(strip=True) if links else ""
        else:
            data["category"] = ""
        
        # URL
        data["url"] = url
        
        # Path from breadcrumb
        if breadcrumb:
            path_parts = [a.get_text(strip=True) for a in breadcrumb.find_all("a")]
            data["path"] = " / ".join(path_parts) if path_parts else ""
        else:
            data["path"] = ""
        
        # Title
        title_tag = soup.find("h1")
        data["title"] = title_tag.get_text(strip=True) if title_tag else ""
        
        # Image
        img_tag = soup.find("img", src=re.compile(r"/productimages/"))
        data["image"] = img_tag["src"] if img_tag else ""
        
        # Product info table
        info = {}
        for row in soup.select("table tr"):
            cells = row.find_all(["th", "td"])
            if len(cells) == 2:
                key = cells[0].get_text(strip=True)
                value = cells[1].get_text(strip=True)
                if key:
                    info[key] = value
        
        data["manufacturer"] = info.get("Manufacturer", "")
        data["manufacturer_part_no"] = info.get("Manufacturer Part No", "")
        data["order_code"] = info.get("Order Code", "")
        data["product_range"] = info.get("Product Range", "")
        data["also_known_as"] = info.get("Also Known As", "")
        
        # Manufacturer link
        if data["manufacturer"]:
            brand_slug = data["manufacturer"].lower().replace(" ", "-").replace("/", "-")
            data["manufacturer_link"] = f"https://cpc.farnell.com/c/audio-visual/av-accessories?brand={brand_slug}"
        else:
            data["manufacturer_link"] = ""
        
        # Stock
        stock_tag = soup.find(string=re.compile(r"\d+\s+In Stock", re.IGNORECASE))
        if stock_tag:
            match = re.search(r"(\d+)\s+In Stock", stock_tag, re.IGNORECASE)
            data["stock"] = match.group(1) if match else ""
        else:
            data["stock"] = ""
        
        # Pricing tiers
        prices = []
        for row in soup.select("table tr"):
            cells = row.find_all("td")
            if len(cells) == 2:
                qty_text = cells[0].get_text(strip=True)
                price_text = cells[1].get_text(strip=True)
                if re.match(r"^\d+\+$", qty_text) and "£" in price_text:
                    prices.append(f"{qty_text}/{price_text}")
        data["pricing"] = "; ".join(prices)
        
        # Kit 1 Price (first price tier)
        data["kit_price"] = prices[0].split("/")[1] if prices else ""
        
        # Overview
        overview_section = soup.find("div", class_=re.compile(r"overview|description", re.IGNORECASE))
        if overview_section:
            data["overview"] = overview_section.get_text(separator=" ", strip=True)
        else:
            paragraphs = [p.get_text(strip=True) for p in soup.find_all("p") if len(p.get_text(strip=True)) > 80]
            data["overview"] = paragraphs[0] if paragraphs else ""
        
        # Technical specs
        specs = []
        spec_table = soup.find("table", class_=re.compile(r"spec|technical", re.IGNORECASE))
        if spec_table:
            for row in spec_table.find_all("tr"):
                cells = row.find_all(["th", "td"])
                if len(cells) == 2:
                    key = cells[0].get_text(strip=True)
                    value = cells[1].get_text(strip=True)
                    if key and value:
                        specs.append(f"{key}: {value}")
        
        # Add SVHC and other info to specs
        if info.get("SVHC"):
            specs.append(f"SVHC: {info['SVHC']}")
        if info.get("Product Range"):
            specs.insert(0, f"Product Range: {info['Product Range']}")
        
        data["specs"] = " | ".join(specs)
        
        print(f"✓ {data['order_code']}: {data['title'][:50]}")
        return data
        
    except Exception as e:
        print(f"✗ Error scraping {url}: {e}")
        return None

def scrape_products_parallel(urls, max_workers=5, batch_size=50):
    """Scrape multiple products in parallel with batch saving"""
    all_results = []
    total = len(urls)
    
    # Process in batches
    for batch_start in range(0, total, batch_size):
        batch_end = min(batch_start + batch_size, total)
        batch_urls = urls[batch_start:batch_end]
        
        print(f"\n--- Batch {batch_start//batch_size + 1}: Products {batch_start+1}-{batch_end} ---")
        
        batch_results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {executor.submit(scrape_product, url): url for url in batch_urls}
            
            for future in as_completed(future_to_url):
                result = future.result()
                if result:
                    batch_results.append(result)
        
        # Save batch immediately
        if batch_results:
            save_to_csv(batch_results, OUTPUT_FILE)
            all_results.extend(batch_results)
            print(f"✓ Batch saved: {len(batch_results)} products (Total: {len(all_results)}/{total})")
        
        time.sleep(1)  # Brief pause between batches
    
    return all_results

def save_to_csv(products, filename):
    """Save products to CSV in test.csv format"""
    print(f"\nSaving {len(products)} products to {filename}...")
    
    # Check if file exists to determine if we need headers
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            file_exists = True
    except FileNotFoundError:
        file_exists = False
    
    with open(filename, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Write header if new file
        if not file_exists:
            writer.writerow([
                "Category_Name", "Page_URL", "Path", "Title", "Product_Image",
                "Manufacturer", "Manufacturer_Link", "Manufacturer_Part_No",
                "Order_Code", "Product_Range", "Also_Known_As", "in_stock",
                "Quantity_Price_Tiers", "Kit_1_Price", "Product_Overview",
                "Technical_Specifications"
            ])
        
        # Write products
        for p in products:
            writer.writerow([
                p.get("category", ""),
                p.get("url", ""),
                p.get("path", ""),
                p.get("title", ""),
                p.get("image", ""),
                p.get("manufacturer", ""),
                p.get("manufacturer_link", ""),
                p.get("manufacturer_part_no", ""),
                p.get("order_code", ""),
                p.get("product_range", ""),
                p.get("also_known_as", ""),
                p.get("stock", ""),
                p.get("pricing", ""),
                p.get("kit_price", ""),
                p.get("overview", ""),
                p.get("specs", "")
            ])
    
    print(f"✓ Saved to {filename}")

# Main execution
if __name__ == "__main__":
    print("=== CPC Farnell Product Scraper ===\n")
    
    # Step 1: Get product URLs
    urls = get_product_urls(TARGET_PRODUCTS)
    print(f"\nCollected {len(urls)} product URLs\n")
    
    if not urls:
        print("ERROR: No URLs found")
        exit(1)
    
    # Step 2: Scrape products in batches
    print(f"Scraping {len(urls)} products with {MAX_WORKERS} workers...\n")
    products = scrape_products_parallel(urls, max_workers=MAX_WORKERS)
    
    print(f"\n✓ Successfully scraped {len(products)}/{len(urls)} products")
    
    # Step 3: Save to CSV
    if products:
        save_to_csv(products, OUTPUT_FILE)
        print(f"\n=== COMPLETE ===")
        print(f"Total products scraped: {len(products)}")
        print(f"Output file: {OUTPUT_FILE}")
    else:
        print("\n✗ No products scraped")
