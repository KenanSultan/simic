from scraping.mongo import (
    bazarstore_raw_pages,
    bazarstore_raw_products,
)
from scraping.raw_products.writer import write_raw_product


def extract_bazarstore_products(attempt: int | None = None):
    query = {}
    if attempt is not None:
        query["attempt"] = attempt

    cursor = bazarstore_raw_pages.find(query)

    for page in cursor:
        page_attempt = page["attempt"]
        fetched_at = page["fetched_at"]

        for product in page["data"]["products"]:
            write_raw_product(
                bazarstore_raw_products,
                product_id=product["id"],
                attempt=page_attempt,
                product=product,
                fetched_at=fetched_at,
            )
