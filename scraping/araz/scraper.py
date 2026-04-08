from datetime import datetime, timezone

from scraping.araz.client import fetch_araz_page
from scraping.araz.attempts import get_next_attempt, get_last_page_for_attempt
from datastore.mongo import araz_raw_pages


def scrape_araz(resume_attempt: int | None = None):
    if resume_attempt is not None:
        attempt = resume_attempt
        start_page = get_last_page_for_attempt(attempt) + 1
    else:
        attempt = get_next_attempt()
        start_page = 1

    print(f"[INFO] Using attempt: {attempt}")
    print(f"[INFO] Starting from page: {start_page}")

    page = start_page
    last_page = None

    while True:
        data = fetch_araz_page(page)

        if data.get("status") != "success":
            raise RuntimeError(f"Araz API returned invalid status on page {page}")

        payload = data["data"]

        # determine pagination limits once
        pagination = payload["pagination"]
        current_page = pagination["current_page"]
        last_page = pagination["last_page"]

        # drop heavy category key
        payload.pop("category", None)

        # build mongo document
        doc = {
            "attempt": attempt,
            "page": current_page,
            "fetched_at": datetime.now(tz=timezone.utc),
            "data": payload,
        }

        # write (idempotent)
        araz_raw_pages.update_one(
            {"attempt": attempt, "page": current_page},
            {"$setOnInsert": doc},
            upsert=True,
        )

        print(f"[OK] Saved attempt={attempt}, page={current_page}")

        if current_page >= last_page:
            print("[DONE] Reached last page")
            break

        page += 1
