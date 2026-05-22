"""
Runs the scraper and appends the result to test.csv in the correct column format.
"""

import csv
import re
import json
import requests
from bs4 import BeautifulSoup

API_KEY = "84cedc1d8b5f91cfa84846e16aee0611"
TARGET_URL = "https://cpc.farnell.com/proto-advantage/ss-metal-pen/solder-paste-squeegee-ss-pen-kit/dp/SD03523"
CSV_PATH = r"c:\Users\freelancer\Downloads\task -src-1\test.csv"

FIELDNAMES = [
    "Category_Name", "Page_URL", "Path", "Title", "Product_Image",
    "Manufacturer", "Manufacturer_Link", "Manufacturer_Part_No", "Order_Code",
    "Product_Range", "Also_Known_As", "in_stock", "Quantity_Price_Tiers",
    "Kit_1_Price", "Product_Overview", "Technical_Specifications"
]


def scrape_cpc_product(url: str) -> dict:
    scraper_url = (
        f"http://api.scraperapi.com"
        f"?api_key={API_KEY}"
        f"&url={url}"
    )
    response = requests.get(scraper_url, timeout=120)
    response.raise_for_status()
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
        first_price = prices[0].split("/")[-1]
        data["kit_1_price"] = first_price
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
        data["manufacturer_link"] = "https://cpc.farnell.com" + data["manufacturer_link"]

    # --- Technical Specifications ---
    tech_specs_parts = []
    if data.get("product_range"):
        tech_specs_parts.append(f"Product Range: {data['product_range']}")
    if data.get("svhc"):
        tech_specs_parts.append(f"SVHC: {data['svhc']}")
    data["technical_specifications"] = " | ".join(tech_specs_parts) if tech_specs_parts else None

    return data


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


if __name__ == "__main__":
    print(f"Scraping: {TARGET_URL}\n")
    product = scrape_cpc_product(TARGET_URL)
    print(json.dumps(product, indent=2, ensure_ascii=False))

    row = build_csv_row(product, TARGET_URL)

    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, quoting=csv.QUOTE_ALL)
        writer.writerow(row)

    print("\nRow appended to test.csv successfully.")
