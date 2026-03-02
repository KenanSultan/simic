import time
import random
import requests

BASE_URL = "https://bazarstore.az/products.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

def fetch_bazarstore_page(page: int) -> dict:
    # random sleep 1–3 seconds
    time.sleep(random.uniform(0.5, 2))

    resp = requests.get(
        BASE_URL,
        params={"page": page},
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()
