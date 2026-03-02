from datetime import datetime, timezone

from scraping.bazarstore.client import fetch_bazarstore_page
from scraping.bazarstore.attempts import (
    get_next_attempt,
    get_last_page_for_attempt,
)
from scraping.mongo import bazarstore_raw_pages


def scrape_bazarstore(resume_attempt: int | None = None):
    # 1️⃣ decide attempt
    if resume_attempt is not None:
        attempt = resume_attempt
        start_page = get_last_page_for_attempt(attempt) + 1
    else:
        attempt = get_next_attempt()
        start_page = 1

    print(f"[INFO] Using attempt: {attempt}")
    print(f"[INFO] Starting from page: {start_page}")

    page = start_page

    while True:
        data = fetch_bazarstore_page(page)

        products = data.get("products")

        # 🛑 stop condition
        if not isinstance(products, list) or len(products) == 0:
            print(f"[STOP] No products on page {page}")
            break

        doc = {
            "attempt": attempt,
            "page": page,
            "fetched_at": datetime.now(tz=timezone.utc),
            "data": {
                "products": products
            },
        }

        bazarstore_raw_pages.update_one(
            {"attempt": attempt, "page": page},
            {"$setOnInsert": doc},
            upsert=True,
        )

        print(f"[OK] Saved attempt={attempt}, page={page}")

        page += 1

    print("[DONE] Bazarstore scraping finished")
