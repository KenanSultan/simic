from bs4 import BeautifulSoup

from scraping.mongo import (
    neptun_raw_pages,
    neptun_raw_products,
)
from scraping.raw_products.writer import write_raw_product


def extract_neptun_products(attempt: int | None = None):
    """
    Parse Neptun search page HTML and write raw products.
    """

    query = {}
    if attempt is not None:
        query["attempt"] = attempt

    cursor = neptun_raw_pages.find(query)

    for page in cursor:
        page_attempt = page["attempt"]
        fetched_at = page["fetched_at"]
        search_term = page["search_term"]
        page_no = page["page"]

        print(f"Attempt: {page_attempt}, search term: {search_term}, page no: {page_no}")

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
                        "source": "search_page",
                        "search_term": search_term,
                        "page": page_no,
                    },
                },
            )


def _parse_products_from_html(html: str) -> list[dict]:
    """
    Extract product list from Neptun search page HTML.
    """

    soup = BeautifulSoup(html, "html.parser")

    products = []

    # Neptun search page-də qeyd etdiyimiz əsas selector
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

    # variant 1: product link içində
    link_tag = card.select_one("a[href*='product_id=']")
    if link_tag:
        href = link_tag.get("href", "")
        # product_id=12345
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
    if link_tag:
        product_url = link_tag.get("href")

    return {
        "product_id": product_id,
        "name": name,
        "price": price,
        "old_price": old_price,
        "image": image,
        "product_url": product_url,
        "raw_html": str(card),
    }


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
