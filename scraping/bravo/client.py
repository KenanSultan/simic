import time
import random
import requests

BASE_URL = "https://mp-catalog.umico.az/api/v1/products"

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

def fetch_products(page: int, category_id: int, per_page: int = 24) -> dict:
    sleep_seconds = random.uniform(1, 3)
    time.sleep(sleep_seconds)
    params = {
        "page": page,
        "category_id": category_id,
        "per_page": per_page,
    }

    response = requests.get(
        BASE_URL,
        params=params,
        headers=DEFAULT_HEADERS,
        timeout=10,
    )
    response.raise_for_status()
    return response.json()
