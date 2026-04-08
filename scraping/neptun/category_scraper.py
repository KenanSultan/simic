import json
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from datastore.mongo import neptun_raw_categories

BASE_URL = "https://neptun.az"
OUTPUT_PATH = Path(__file__).resolve().parents[2] / "data" / "categories" / "neptun-categories.json"


def scrape_neptun_categories():
    resp = requests.get(BASE_URL, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    categories = []
    for li in soup.select("ul.megamenu > li.item-vertical"):
        strong = li.select_one("a strong")
        if not strong:
            continue

        name = strong.get_text(strip=True)
        children = []
        for sub_link in li.select("div.sub-menu a.main-menu"):
            children.append({
                "title": sub_link.get_text(strip=True),
                "url": sub_link.get("href"),
                "children": [],
            })

        categories.append({"title": name, "children": children})

    print(f"[INFO] Extracted {len(categories)} top-level categories")

    # store raw result in MongoDB
    neptun_raw_categories.update_one(
        {"source": "nav_menu"},
        {
            "$set": {
                "source": "nav_menu",
                "fetched_at": datetime.now(tz=timezone.utc),
                "data": categories,
            }
        },
        upsert=True,
    )
    print("[OK] Saved raw categories to MongoDB")

    # write JSON file
    output = {"data": categories}

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=4)

    print(f"[OK] Written to {OUTPUT_PATH}")
