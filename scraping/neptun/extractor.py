import re

from bs4 import BeautifulSoup

from datastore.mongo import (
    neptun_raw_pages,
    neptun_raw_products,
)
from scraping.raw_products.writer import write_raw_product


def extract_neptun_products(attempt: int | None = None):
    """
    Parse Neptun category page HTML and write raw products.
    """

    query = {}
    if attempt is not None:
        query["attempt"] = attempt

    cursor = neptun_raw_pages.find(query)

    for page in cursor:
        page_attempt = page["attempt"]
        fetched_at = page["fetched_at"]
        page_no = page["page"]

        category_url = page.get("category_url")
        category_title = page.get("category_title")
        parent_category_title = page.get("parent_category_title")

        print(
            f"Attempt: {page_attempt}, "
            f"category: {category_title}, page no: {page_no}"
        )

        html = page.get("html")
        if not html:
            continue

        products = _parse_products_from_html(html)

        for product in products:
            write_raw_product(
                neptun_raw_products,
                product_id=product["product_id"],
                attempt=page_attempt,
                fetched_at=fetched_at,
                product={
                    **product,
                    "_meta": {
                        "source": "category_page",
                        "category_url": category_url,
                        "category_title": category_title,
                        "parent_category_title": parent_category_title,
                        "page": page_no,
                    },
                },
            )


def _parse_products_from_html(html: str) -> list[dict]:
    """
    Extract product list from Neptun category page HTML.
    """

    soup = BeautifulSoup(html, "html.parser")

    products = []

    for card in soup.select("div.product-layout"):
        product = _parse_single_product(card)
        if product:
            products.append(product)

    return products


def _parse_single_product(card) -> dict | None:
    """
    Parse a single product card.
    """

    # ---- product_id ----
    product_id = None

    # variant 1: quickview button data-product_id (most reliable)
    qv_btn = card.select_one("button[data-product_id]")
    if qv_btn:
        product_id = qv_btn.get("data-product_id")

    # variant 2: product link içində
    if not product_id:
        link_tag = card.select_one("a[href*='product_id=']")
        if link_tag:
            href = link_tag.get("href", "")
            if "product_id=" in href:
                product_id = href.split("product_id=")[-1].split("&")[0]

    if not product_id:
        return None

    # ---- product name ----
    name = None
    name_tag = card.select_one("h4 a") or card.select_one("h4")
    if name_tag:
        name = name_tag.get_text(strip=True)

    # ---- prices ----
    price = None
    old_price = None

    price_new = card.select_one(".price-new")
    price_old = card.select_one(".price-old")

    if price_new:
        price = _normalize_price(price_new.get_text())
    elif price_old:
        price = _normalize_price(price_old.get_text())

    if price_old:
        old_price = _normalize_price(price_old.get_text())

    # ---- image ----
    image = None
    img_tag = card.select_one("img")
    if img_tag:
        image = img_tag.get("src")

    # ---- product url ----
    product_url = None
    link_tag = card.select_one("h4 a") or card.select_one("a[href]")
    if link_tag:
        product_url = link_tag.get("href")

    # ---- product code from URL slug ----
    product_code = None
    if product_url:
        product_code = _extract_product_code(product_url)

    return {
        "product_id": product_id,
        "name": name,
        "price": price,
        "old_price": old_price,
        "image": image,
        "product_url": product_url,
        "product_code": product_code,
        "raw_html": str(card),
    }


def _extract_product_code(url: str) -> str | None:
    """
    Extract trailing numeric code from Neptun product URL slug.
    e.g. 'https://neptun.az/.../coca-cola-1lt-015045' → '015045'
    """
    match = re.search(r"-(\d{4,})$", url)
    return match.group(1) if match else None


def _normalize_price(text: str) -> float | None:
    """
    Normalize price like '2.35₼' → 2.35
    """
    if not text:
        return None

    cleaned = (
        text.replace("₼", "")
        .replace("AZN", "")
        .replace(",", ".")
        .strip()
    )

    try:
        return float(cleaned)
    except ValueError:
        return None
