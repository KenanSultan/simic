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
        page_no = page.get("page")

        category_handle = page.get("category_handle")
        category_title = page.get("category_title")
        parent_category_title = page.get("parent_category_title")
        root_category_title = page.get("root_category_title")

        print(
            f"Attempt: {page_attempt}, "
            f"category: {category_title}, page no: {page_no}"
        )

        for product in page["data"]["products"]:
            write_raw_product(
                bazarstore_raw_products,
                product_id=product["id"],
                attempt=page_attempt,
                product={
                    **product,
                    "_meta": {
                        "source": "category_page",
                        "category_handle": category_handle,
                        "category_title": category_title,
                        "parent_category_title": parent_category_title,
                        "root_category_title": root_category_title,
                        "page": page_no,
                    },
                },
                fetched_at=fetched_at,
            )
