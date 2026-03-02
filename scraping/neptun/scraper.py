from datetime import datetime, timezone
import time
import random

from scraping.mongo import neptun_raw_pages
from scraping.neptun.client import fetch_neptun_search_page
from scraping.neptun.attempts import (
    get_next_attempt,
    get_last_page_for_attempt,
)

# Azərbaycan dilində bütün saitlər
# VOWELS = ["a", "e", "ə", "i", "ı", "o", "ö", "u", "ü"]
VOWELS = [" "]
# Search page-də istifadə edəcəyimiz maksimum limit
PAGE_LIMIT = 100


def scrape_neptun(resume_attempt: int | None = None):
    """
    Crawl Neptun search pages (HTML) and store them into neptun_raw_pages.
    This function DOES NOT parse products.
    """

    # attempt müəyyənləşdir
    if resume_attempt is not None:
        attempt = resume_attempt
    else:
        attempt = get_next_attempt()

    print(f"[INFO] Using attempt: {attempt}")

    # hər sait üçün ayrıca crawl
    for search_term in VOWELS:
        # resume logic: bu attempt + sait üçün son page
        start_page = get_last_page_for_attempt(attempt, search_term) + 1

        print(
            f"[INFO] Search term='{search_term}' | starting from page={start_page}"
        )

        page = start_page

        while True:
            # rate limit (Cloudflare-safe)
            time.sleep(random.uniform(1, 3))

            # HTML fetch
            html = fetch_neptun_search_page(
                search_term=search_term,
                page=page,
                limit=PAGE_LIMIT,
            )

            # Mongo document
            doc = {
                "attempt": attempt,
                "search_term": search_term,
                "page": page,
                "limit": PAGE_LIMIT,
                "fetched_at": datetime.now(tz=timezone.utc),
                "html": html,
            }

            # idempotent insert
            result = neptun_raw_pages.update_one(
                {
                    "attempt": attempt,
                    "search_term": search_term,
                    "page": page,
                },
                {"$setOnInsert": doc},
                upsert=True,
            )

            if result.upserted_id:
                print(
                    f"[OK] Saved attempt={attempt}, "
                    f"search='{search_term}', page={page}"
                )
            else:
                print(
                    f"[SKIP] Exists attempt={attempt}, "
                    f"search='{search_term}', page={page}"
                )

            # ---- STOP CONDITION ----
            # HTML-də məhsul YOXDURSA → bu sait üçün bitir
            # (parse ETMİRİK, sadəcə lightweight check)
            if _no_products_in_html(html):
                print(
                    f"[DONE] No products found "
                    f"for search='{search_term}', page={page}"
                )
                break

            page += 1

    print("[DONE] Neptun page scraping finished")


def _no_products_in_html(html: str) -> bool:
    if not html:
        return True

    # Neptun search page product markers
    return (
        "product-layout" not in html
        and "product-grid" not in html
    )

