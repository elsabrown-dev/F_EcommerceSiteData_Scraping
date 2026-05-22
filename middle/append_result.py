"""
Runs the scraper and appends results to test.csv in the correct column format.

Usage:
    python append_result.py                            # uses DEFAULT_URL (single product)
    python append_result.py <product_url>              # scrapes a single product URL
    python append_result.py --category <slug>          # scrapes ALL products in a category
    python append_result.py --category <slug1> <slug2> # scrapes multiple categories

Category slug examples (the part after cpc.farnell.com/c/):
    hand-tools
    power-tools
    test-equipment
"""

import csv
import re
import sys
import json
import time
import requests
from bs4 import BeautifulSoup

API_KEY = "84cedc1d8b5f91cfa84846e16aee0611"
BASE_URL = "https://cpc.farnell.com"
DEFAULT_URL = "https://cpc.farnell.com/rolson-tools/60680/security-spikes-9-pc/dp/SR11815"
CSV_PATH = r"c:\Users\freelancer\Downloads\task\test.csv"
PAGE_SIZE = 100  # max products per page on CPC

FIELDNAMES = [
    "Category_Name", "Page_URL", "Path", "Title", "Product_Image",
    "Manufacturer", "Manufacturer_Link", "Manufacturer_Part_No", "Order_Code",
    "Product_Range", "Also_Known_As", "in_stock", "Quantity_Price_Tiers",
    "Kit_1_Price", "Product_Overview", "Technical_Specifications"
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def scraperapi_get(url: str, timeout: int = 120) -> requests.Response:
    """Fetch a URL through ScraperAPI."""
    proxy_url = (
        f"http://api.scraperapi.com"
        f"?api_key={API_KEY}"
        f"&url={requests.utils.quote(url, safe=':/?=&')}"
    )
    response = requests.get(proxy_url, timeout=timeout)
    response.raise_for_status()
    return response


# ---------------------------------------------------------------------------
# Category crawler – returns a list of product URLs
# ---------------------------------------------------------------------------

def get_category_product_urls(category_slug: str) -> list[str]:
    """
    Crawl all pages of a CPC Farnell category listing and return every
    product URL found.

    CPC listing URL pattern:
        https://cpc.farnell.com/c/<slug>?pageSize=100&start=<offset>
    Product links on the page match /dp/ in their href.
    """
    urls = []
    start = 0

    print(f"  Fetching category: {category_slug}")

    while True:
        listing_url = f"{BASE_URL}/c/{category_slug}?pageSize={PAGE_SIZE}&start={start}"
        print(f"    Page offset {start} -> {listing_url}")

        try:
            response = scraperapi_get(listing_url)
        except requests.RequestException as exc:
            print(f"    ERROR fetching listing page: {exc}")
            break

        soup = BeautifulSoup(response.text, "html.parser")

        # Product links contain /dp/ in the path
        product_links = soup.find_all("a", href=re.compile(r"/dp/", re.IGNORECASE))
        page_urls = []
        seen = set()
        for tag in product_links:
            href = tag["href"]
            if not href.startswith("http"):
                href = BASE_URL + href
            # Deduplicate within this page
            if href not in seen:
                seen.add(href)
                page_urls.append(href)

        if not page_urls:
            print(f"    No products found on this page – stopping pagination.")
            break

        print(f"    Found {len(page_urls)} product URLs on this page.")
        urls.extend(page_urls)

        # Check if there is a next page
        # CPC uses a "next" link or shows fewer results than PAGE_SIZE when done
        next_link = soup.find("a", {"aria-label": re.compile(r"next", re.IGNORECASE)})
        if next_link is None and len(page_urls) < PAGE_SIZE:
            break  # last page

        start += PAGE_SIZE
        time.sleep(1)  # be polite between listing pages

    # Global dedup while preserving order
    seen_global = set()
    unique_urls = []
    for u in urls:
        if u not in seen_global:
            seen_global.add(u)
            unique_urls.append(u)

    print(f"  Total unique product URLs found: {len(unique_urls)}")
    return unique_urls


# ---------------------------------------------------------------------------
# Product scraper
# ---------------------------------------------------------------------------

def scrape_cpc_product(url: str) -> dict:
    response = scraperapi_get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    data = {}

    # --- Product title ---
    title_tag = soup.find("h1")
    data["title"] = title_tag.get_text(strip=True) if title_tag else None

    # --- Product info table ---
    info = {}
    for row in soup.select("table tr"):
        cells = row.find_all(["th", "td"])
        if len(cells) == 2:
            key = cells[0].get_text(strip=True)
            value = cells[1].get_text(strip=True)
            if key:
                info[key] = value

    data["manufacturer"] = info.get("Manufacturer")
    data["manufacturer_part_no"] = info.get("Manufacturer Part No")
    data["order_code"] = info.get("Order Code")
    data["product_range"] = info.get("Product Range", "-")
    data["also_known_as"] = info.get("Also Known As", "")
    data["kit_contents_summary"] = info.get("Kit Contents")
    data["svhc"] = info.get("SVHC")
    data["country_of_origin"] = info.get("Country of Origin")
    data["rohs_compliant"] = info.get("RoHS Compliant")
    data["weight_kg"] = info.get("Weight (kg)")

    # --- Pricing tiers ---
    prices = []
    for row in soup.select("table tr"):
        cells = row.find_all("td")
        if len(cells) == 2:
            qty_text = cells[0].get_text(strip=True)
            price_text = cells[1].get_text(strip=True)
            if re.match(r"^\d+\+$", qty_text) and "£" in price_text:
                prices.append(f"{qty_text}/{price_text}")
    data["pricing_tiers"] = "; ".join(prices)

    # Kit_1_Price = first tier price
    if prices:
        data["kit_1_price"] = prices[0].split("/")[-1]
    else:
        data["kit_1_price"] = None

    # --- Stock ---
    stock_tag = soup.find(string=re.compile(r"\d+\s+In Stock", re.IGNORECASE))
    if stock_tag:
        match = re.search(r"(\d+)\s+In Stock", stock_tag, re.IGNORECASE)
        data["stock"] = int(match.group(1)) if match else stock_tag.strip()
    else:
        data["stock"] = None

    # --- Product overview ---
    overview_section = soup.find("div", class_=re.compile(r"overview|description", re.IGNORECASE))
    if overview_section:
        data["overview"] = overview_section.get_text(separator=" ", strip=True)
    else:
        paragraphs = [p.get_text(strip=True) for p in soup.find_all("p") if len(p.get_text(strip=True)) > 80]
        data["overview"] = paragraphs[0] if paragraphs else None

    # --- Image URL ---
    img_tag = soup.find("img", src=re.compile(r"/productimages/large/"))
    data["image_url"] = img_tag["src"] if img_tag else None

    # --- Category breadcrumb path ---
    breadcrumb = soup.find("nav", {"aria-label": re.compile(r"breadcrumb", re.IGNORECASE)})
    if breadcrumb:
        crumbs = [a.get_text(strip=True) for a in breadcrumb.find_all("a")]
        data["path"] = " / ".join(crumbs) if crumbs else None
    else:
        data["path"] = None

    # --- Category name (first breadcrumb after Home) ---
    data["category_name"] = None
    if data["path"]:
        parts = data["path"].split(" / ")
        data["category_name"] = parts[1] if len(parts) > 1 else parts[0]

    # --- Manufacturer link ---
    mfr_link_tag = soup.find("a", href=re.compile(r"\?brand="))
    data["manufacturer_link"] = mfr_link_tag["href"] if mfr_link_tag else None
    if data["manufacturer_link"] and data["manufacturer_link"].startswith("/"):
        data["manufacturer_link"] = BASE_URL + data["manufacturer_link"]

    # --- Technical Specifications ---
    tech_specs_parts = []
    if data.get("product_range"):
        tech_specs_parts.append(f"Product Range: {data['product_range']}")
    if data.get("svhc"):
        tech_specs_parts.append(f"SVHC: {data['svhc']}")
    data["technical_specifications"] = " | ".join(tech_specs_parts) if tech_specs_parts else None

    return data


# ---------------------------------------------------------------------------
# CSV row builder
# ---------------------------------------------------------------------------

def build_csv_row(product: dict, url: str) -> dict:
    return {
        "Category_Name": product.get("category_name") or "",
        "Page_URL": url,
        "Path": product.get("path") or "",
        "Title": product.get("title") or "",
        "Product_Image": product.get("image_url") or "",
        "Manufacturer": product.get("manufacturer") or "",
        "Manufacturer_Link": product.get("manufacturer_link") or "",
        "Manufacturer_Part_No": product.get("manufacturer_part_no") or "",
        "Order_Code": product.get("order_code") or "",
        "Product_Range": product.get("product_range") or "-",
        "Also_Known_As": product.get("also_known_as") or "",
        "in_stock": product.get("stock") if product.get("stock") is not None else "",
        "Quantity_Price_Tiers": product.get("pricing_tiers") or "",
        "Kit_1_Price": product.get("kit_1_price") or "",
        "Product_Overview": product.get("overview") or "",
        "Technical_Specifications": product.get("technical_specifications") or "",
    }


# ---------------------------------------------------------------------------
# Core: scrape a list of URLs and append to CSV
# ---------------------------------------------------------------------------

def scrape_and_append(target_urls: list[str]):
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, quoting=csv.QUOTE_ALL)

        for i, url in enumerate(target_urls, 1):
            print(f"\n[{i}/{len(target_urls)}] Scraping: {url}")
            try:
                product = scrape_cpc_product(url)
                row = build_csv_row(product, url)
                writer.writerow(row)
                print(f"  -> Appended: {product.get('title', 'N/A')}")
            except Exception as exc:
                print(f"  ERROR scraping {url}: {exc}")

            if i < len(target_urls):
                time.sleep(0.5)  # small delay between product requests

    print(f"\nDone. {len(target_urls)} row(s) processed -> {CSV_PATH}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    args = sys.argv[1:]

    if not args:
        # No arguments – scrape the single default URL
        print(f"No arguments provided. Scraping default URL:\n  {DEFAULT_URL}\n")
        scrape_and_append([DEFAULT_URL])

    elif args[0] == "--category":
        # --category <slug1> [slug2 ...]
        slugs = args[1:]
        if not slugs:
            print("ERROR: --category requires at least one category slug.")
            print("Example: python append_result.py --category hand-tools")
            sys.exit(1)

        all_urls = []
        for slug in slugs:
            print(f"\nDiscovering products in category: '{slug}'")
            urls = get_category_product_urls(slug)
            all_urls.extend(urls)

        if not all_urls:
            print("No product URLs found. Check the category slug(s) and try again.")
            sys.exit(1)

        print(f"\nTotal products to scrape: {len(all_urls)}")
        scrape_and_append(all_urls)

    else:
        # Treat all arguments as direct product URLs
        print(f"Scraping {len(args)} URL(s) provided as arguments.\n")
        scrape_and_append(args)
