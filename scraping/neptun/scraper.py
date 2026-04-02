from datetime import datetime, timezone
import time
import random

from scraping.mongo import neptun_raw_pages
from scraping.neptun.client import fetch_neptun_category_page
from scraping.neptun.categories import load_leaf_categories
from scraping.neptun.attempts import (
    get_next_attempt,
    get_last_page_for_category,
)

PAGE_LIMIT = 100


def scrape_neptun(resume_attempt: int | None = None):
    """
    Crawl Neptun category pages (HTML) and store them into neptun_raw_pages.
    This function DOES NOT parse products.
    """

    # attempt müəyyənləşdir
    if resume_attempt is not None:
        attempt = resume_attempt
    else:
        attempt = get_next_attempt()

    print(f"[INFO] Using attempt: {attempt}")

    categories = load_leaf_categories()
    print(f"[INFO] Loaded {len(categories)} leaf categories")

    for cat in categories:
        category_url = cat["url"]
        category_title = cat["title"]
        parent_title = cat["parent_title"]

        # resume logic: bu attempt + category üçün son page
        last_page = get_last_page_for_category(attempt, category_url)

        # If last saved page had no products, category is already done
        if last_page > 0 and _category_is_done(attempt, category_url, last_page):
            print(
                f"[SKIP] Category '{category_title}' ({parent_title}) "
                f"already complete (last_page={last_page})"
            )
            continue

        start_page = last_page + 1

        print(
            f"[INFO] Category: {category_title} ({parent_title}) "
            f"| starting from page={start_page}"
        )

        page = start_page

        while True:
            # rate limit (Cloudflare-safe)
            time.sleep(random.uniform(1, 3))

            # HTML fetch
            html = fetch_neptun_category_page(
                category_url=category_url,
                page=page,
                limit=PAGE_LIMIT,
            )

            # Mongo document
            doc = {
                "attempt": attempt,
                "category_url": category_url,
                "category_title": category_title,
                "parent_category_title": parent_title,
                "page": page,
                "limit": PAGE_LIMIT,
                "fetched_at": datetime.now(tz=timezone.utc),
                "html": html,
            }

            # idempotent insert
            result = neptun_raw_pages.update_one(
                {
                    "attempt": attempt,
                    "category_url": category_url,
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

            # ---- STOP CONDITION ----
            # HTML-də məhsul YOXDURSA → bu category üçün bitir
            # (parse ETMİRİK, sadəcə lightweight check)
            if _no_products_in_html(html):
                print(
                    f"[DONE] No products found "
                    f"for category='{category_title}', page={page}"
                )
                break

            page += 1

    print("[DONE] Neptun category scraping finished")


def _category_is_done(attempt: int, category_url: str, last_page: int) -> bool:
    """
    Check if a category was fully scraped by looking at the HTML
    on its last saved page. If it has no products, it was the final page.
    """
    doc = neptun_raw_pages.find_one(
        {
            "attempt": attempt,
            "category_url": category_url,
            "page": last_page,
        },
        projection={"html": 1},
    )
    if not doc:
        return False

    return _no_products_in_html(doc.get("html", ""))


def _no_products_in_html(html: str) -> bool:
    if not html:
        return True

    # Neptun shows this message when a category page has no products
    if "Bu bölmədə hər hansı məhsul tapılmadı" in html:
        return True

    # Check for actual product card elements (not JS references)
    # <div class="product-layout ... "> appears only when real products exist
    return '<div class="product-layout' not in html
