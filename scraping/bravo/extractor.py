from scraping.mongo import (
    bravo_raw_pages,
    bravo_raw_products,
)
from scraping.raw_products.writer import write_raw_product


def extract_bravo_products(attempt: int | None = None):
    query = {}
    if attempt is not None:
        query["attempt"] = attempt

    cursor = bravo_raw_pages.find(query)

    for page in cursor:
        page_attempt = page.get("attempt", 1)
        fetched_at = page["fetched_at"]

        for product in page["products"]:
            write_raw_product(
                bravo_raw_products,
                product_id=product["id"],
                attempt=page_attempt,
                product=product,
                fetched_at=fetched_at,
            )
