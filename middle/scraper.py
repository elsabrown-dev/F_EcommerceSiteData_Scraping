"""
Scraper for CPC Farnell product pages using ScraperAPI.
Install dependencies:
    pip install requests beautifulsoup4
"""

import re
import json
import requests
from bs4 import BeautifulSoup

API_KEY = "84cedc1d8b5f91cfa84846e16aee0611"
TARGET_URL = "https://cpc.farnell.com/duratool/d02154/tool-set-129pc/dp/TL14956"


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

    # --- Product info table (Manufacturer, Part No, Order Code, etc.) ---
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
                prices.append({"quantity": qty_text, "price_ex_vat": price_text})
    data["pricing_tiers"] = prices

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

    # --- Datasheet URL ---
    datasheet_link = soup.find("a", string=re.compile(r"data\s*sheet", re.IGNORECASE))
    data["datasheet_url"] = datasheet_link["href"] if datasheet_link else None

    return data


if __name__ == "__main__":
    print(f"Scraping: {TARGET_URL}\n")
    product = scrape_cpc_product(TARGET_URL)
    print(json.dumps(product, indent=2, ensure_ascii=False))
