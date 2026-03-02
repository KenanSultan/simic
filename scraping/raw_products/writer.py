from datetime import datetime, timezone


def write_raw_product(
    collection,
    *,
    product_id,
    attempt,
    product,
    fetched_at=None,
):
    doc = {
        "product_id": product_id,
        "attempt": attempt,
        "fetched_at": fetched_at or datetime.now(tz=timezone.utc),
        "product": product,
    }

    result = collection.update_one(
        {"product_id": product_id, "attempt": attempt},
        {"$setOnInsert": doc},
        upsert=True,
    )

    return bool(result.upserted_id)  # True if inserted, False if skipped
