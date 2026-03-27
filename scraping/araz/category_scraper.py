import json
from datetime import datetime, timezone
from pathlib import Path

import requests

from scraping.mongo import araz_raw_categories

API_URL = "https://b7x9kq.arazmarket.az/api/categories"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Accept": "application/json",
}
OUTPUT_PATH = Path(__file__).resolve().parents[2] / "data" / "categories" / "araz-categories.json"


def clean_tree(nodes: list) -> list:
    """Strip icon/parent, rename sub -> children, keep title + slug."""
    result = []
    for node in nodes:
        result.append({
            "id": node["id"],
            "title": node["title"],
            "slug": node["slug"],
            "children": clean_tree(node.get("sub") or []),
        })
    return result


def scrape_araz_categories():
    resp = requests.get(API_URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    if data.get("status") != "success":
        raise RuntimeError(f"Araz categories API error: {data.get('message')}")

    raw_tree = data["data"]
    print(f"[INFO] Extracted {len(raw_tree)} top-level categories")

    # store raw result in MongoDB
    araz_raw_categories.update_one(
        {"source": "api"},
        {
            "$set": {
                "source": "api",
                "fetched_at": datetime.now(tz=timezone.utc),
                "data": raw_tree,
            }
        },
        upsert=True,
    )
    print("[OK] Saved raw categories to MongoDB")

    # clean and write JSON file
    cleaned = clean_tree(raw_tree)
    output = {"data": cleaned}

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=4)

    print(f"[OK] Written to {OUTPUT_PATH}")
