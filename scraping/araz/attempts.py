from datastore.mongo import araz_raw_pages


def get_next_attempt() -> int:
    doc = araz_raw_pages.find_one(
        {},
        sort=[("attempt", -1)],
        projection={"attempt": 1},
    )
    return (doc["attempt"] + 1) if doc else 1


def get_last_page_for_attempt(attempt: int) -> int:
    doc = araz_raw_pages.find_one(
        {"attempt": attempt},
        sort=[("page", -1)],
        projection={"page": 1},
    )
    return doc["page"] if doc else 0
