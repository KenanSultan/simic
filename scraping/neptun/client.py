import time
import random
import requests

BASE_URL = "https://neptun.az/index.php"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/129.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "az,en-US;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
    "Referer": "https://neptun.az/",
}


def fetch_neptun_search_page(
    *,
    search_term: str,
    page: int,
    limit: int = 100,
    timeout: int = 20,
) -> str:
    """
    Fetch Neptun search result page HTML.

    This function:
    - returns RAW HTML
    - does NOT parse anything
    - raises on HTTP errors
    """

    # human-like delay (Cloudflare-safe)
    time.sleep(random.uniform(0.5, 1.5))

    params = {
        "route": "product/search",
        "search": search_term,
        "page": page,
        "limit": limit,
    }

    resp = requests.get(
        BASE_URL,
        params=params,
        headers=HEADERS,
        timeout=timeout,
    )

    # hard fail on HTTP problems
    resp.raise_for_status()

    return resp.text
