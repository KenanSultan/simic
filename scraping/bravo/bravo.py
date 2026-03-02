import math
from datetime import datetime, timezone

from scraping.bravo.client import fetch_products
from scraping.bravo.attempts import (
    get_next_attempt,
    get_last_page_for_attempt,
)
from scraping.mongo import bravo_raw_pages

CATEGORY_ID = 4497
PER_PAGE = 24


def scrape_birmarket_bravo(resume_attempt: int | None = None):
    # 1️⃣ decide attempt
    if resume_attempt is not None:
        attempt = resume_attempt
        start_page = get_last_page_for_attempt(attempt) + 1
    else:
        attempt = get_next_attempt()
        start_page = 1

    print(f"[INFO] Using attempt: {attempt}")
    print(f"[INFO] Starting from page: {start_page}")

    # 2️⃣ initial request (page 1 always needed for total)
    first_page = fetch_products(
        page=1,
        category_id=CATEGORY_ID,
        per_page=PER_PAGE,
    )

    total_products = first_page["meta"]["total"]
    total_pages = math.ceil(total_products / PER_PAGE)

    print(f"[INFO] Total products: {total_products}")
    print(f"[INFO] Total pages: {total_pages}")

    # 3️⃣ loop pages
    for page in range(start_page, total_pages + 1):
        if page == 1:
            data = first_page
        else:
            data = fetch_products(
                page=page,
                category_id=CATEGORY_ID,
                per_page=PER_PAGE,
            )

        doc = {
            "attempt": attempt,
            "page": page,
            "fetched_at": datetime.now(tz=timezone.utc),
            "data": {
                "products": data.get("products", []),
                "meta": data.get("meta", {}),
                "per_page": PER_PAGE,
            },
        }

        # idempotent write
        bravo_raw_pages.update_one(
            {"attempt": attempt, "page": page},
            {"$setOnInsert": doc},
            upsert=True,
        )

        print(f"[OK] Saved attempt={attempt}, page={page}")

    print("[DONE] Bravo scraping finished")
