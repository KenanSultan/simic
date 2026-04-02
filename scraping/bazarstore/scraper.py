from datetime import datetime, timezone
import time
import random

from scraping.bazarstore.client import fetch_bazarstore_collection_page
from scraping.bazarstore.categories import load_leaf_categories
from scraping.bazarstore.attempts import (
    get_next_attempt,
    get_last_page_for_category,
)
from scraping.mongo import bazarstore_raw_pages

SHOPIFY_PAGE_SIZE = 30


def scrape_bazarstore(resume_attempt: int | None = None):
    """
    Crawl Bazarstore category pages (JSON) and store them into bazarstore_raw_pages.
    This function DOES NOT extract individual products.
    """

    if resume_attempt is not None:
        attempt = resume_attempt
    else:
        attempt = get_next_attempt()

    print(f"[INFO] Using attempt: {attempt}")

    categories = load_leaf_categories()
    print(f"[INFO] Loaded {len(categories)} leaf categories")

    for cat in categories:
        category_handle = cat["handle"]
        category_title = cat["title"]
        parent_title = cat["parent_title"]
        root_title = cat["root_title"]

        last_page = get_last_page_for_category(attempt, category_handle)

        # If last saved page had fewer products than a full page,
        # that category is already fully scraped — skip it
        if last_page > 0 and _category_is_done(attempt, category_handle, last_page):
            print(
                f"[SKIP] Category '{category_title}' ({root_title}) "
                f"already complete (last_page={last_page})"
            )
            continue

        start_page = last_page + 1

        print(
            f"[INFO] Category: {category_title} ({root_title}) "
            f"| starting from page={start_page}"
        )

        page = start_page

        while True:
            time.sleep(random.uniform(1, 3))

            data = fetch_bazarstore_collection_page(
                handle=category_handle,
                page=page,
            )

            products = data.get("products")

            if not isinstance(products, list) or len(products) == 0:
                print(
                    f"[DONE] No products found "
                    f"for category='{category_title}', page={page}"
                )
                break

            doc = {
                "attempt": attempt,
                "category_handle": category_handle,
                "category_title": category_title,
                "parent_category_title": parent_title,
                "root_category_title": root_title,
                "page": page,
                "fetched_at": datetime.now(tz=timezone.utc),
                "data": {"products": products},
            }

            result = bazarstore_raw_pages.update_one(
                {
                    "attempt": attempt,
                    "category_handle": category_handle,
                    "page": page,
                },
                {"$setOnInsert": doc},
                upsert=True,
            )

            if result.upserted_id:
                print(
                    f"[OK] Saved attempt={attempt}, "
                    f"category='{category_title}', page={page}"
                )
            else:
                print(
                    f"[SKIP] Exists attempt={attempt}, "
                    f"category='{category_title}', page={page}"
                )

            page += 1

    print("[DONE] Bazarstore category scraping finished")


def _category_is_done(attempt: int, category_handle: str, last_page: int) -> bool:
    """
    Check if a category was fully scraped by looking at the product count
    on its last saved page. A full Shopify page has SHOPIFY_PAGE_SIZE products;
    fewer means it was the final page.
    """
    doc = bazarstore_raw_pages.find_one(
        {
            "attempt": attempt,
            "category_handle": category_handle,
            "page": last_page,
        },
        projection={"data.products": 1},
    )
    if not doc:
        return False

    products = doc.get("data", {}).get("products", [])
    return len(products) < SHOPIFY_PAGE_SIZE
