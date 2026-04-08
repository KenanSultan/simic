import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

from datastore.mongo import wolt_raw_categories

BASE_URL = "https://wolt.com/en/aze/baku"
OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "categories"

MARKETS = {
    "neptun": {"brand_slug": "neptun"},
    "araz": {"brand_slug": "araz-supermarkets"},
    "bravo": {"brand_slug": "bravo-supermarket"},
}

JS_DISCOVER_VENUES = """() => {
    const allLinks = document.querySelectorAll('a');
    const venues = [];
    const seen = new Set();

    allLinks.forEach(a => {
        const href = a.href || '';
        if (href.includes('/venue/')) {
            const slug = href.split('/venue/')[1]?.split('?')[0]?.split('#')[0];
            if (slug && !seen.has(slug)) {
                seen.add(slug);
                const nameEl = a.closest('li')?.querySelector('a[href*="/venue/"] ~ div a, a[href*="/venue/"] + div a');
                const name = nameEl ? nameEl.textContent.trim() : '';
                venues.push({ slug, name });
            }
        }
    });

    return venues;
}"""

JS_EXTRACT_CATEGORIES = """() => {
    const links = document.querySelectorAll('a[href*="/items/"]');
    const seen = new Set();
    const categories = [];

    links.forEach(a => {
        const href = a.getAttribute('href');
        const slug = href.split('/items/')[1];
        if (!slug || seen.has(slug)) return;
        seen.add(slug);

        const title = a.innerText.trim();
        if (title && title !== 'All items') {
            categories.push({ title, slug });
        }
    });

    return categories;
}"""

JS_DISMISS_OVERLAYS = """() => {
    document.querySelectorAll('[data-test-id="consents-banner-overlay"]').forEach(el => el.remove());
    document.querySelectorAll('[class*="ConsentsBanner"]').forEach(el => el.remove());
    document.querySelectorAll('dialog').forEach(el => el.remove());
}"""


def _get_venue_name(page):
    """Extract venue name from the page heading."""
    return page.evaluate("""() => {
        const h1 = document.querySelector('h1');
        return h1 ? h1.textContent.trim() : '';
    }""")


def _scrape_venue_categories(page, venue_slug):
    """Scrape 2-level category tree for a single venue."""
    venue_url = f"{BASE_URL}/venue/{venue_slug}"

    # Step 1: Get top-level categories from venue homepage
    page.goto(venue_url, wait_until="domcontentloaded")
    page.wait_for_timeout(2000)
    page.evaluate(JS_DISMISS_OVERLAYS)

    name = _get_venue_name(page)
    top_level = page.evaluate(JS_EXTRACT_CATEGORIES)
    top_slugs = {c["slug"] for c in top_level}

    print(f"  -> {len(top_level)} top-level categories, fetching subcategories...")

    # Step 2: For each top-level category, navigate to its page and extract subcategories
    categories = []
    for j, cat in enumerate(top_level):
        cat_url = f"{venue_url}/items/{cat['slug']}"

        try:
            page.goto(cat_url, wait_until="domcontentloaded")
            page.wait_for_timeout(1500)
            page.evaluate(JS_DISMISS_OVERLAYS)

            all_links = page.evaluate(JS_EXTRACT_CATEGORIES)
            # Subcategories = links on this page that aren't top-level categories
            children = [
                link for link in all_links
                if link["slug"] not in top_slugs and link["slug"] != cat["slug"]
            ]

            categories.append({
                "title": cat["title"],
                "slug": cat["slug"],
                "children": children,
            })

            if children:
                print(f"    [{j+1}/{len(top_level)}] {cat['title']}: {len(children)} subcategories")
        except Exception as e:
            print(f"    [{j+1}/{len(top_level)}] {cat['title']}: ERROR {e}")
            categories.append({
                "title": cat["title"],
                "slug": cat["slug"],
                "children": [],
            })

        if j < len(top_level) - 1:
            time.sleep(random.uniform(1, 2))

    total_children = sum(len(c["children"]) for c in categories)
    print(f"  -> {len(categories)} categories, {total_children} subcategories total")

    return name, categories


def scrape_wolt_categories(market: str):
    if market not in MARKETS:
        raise ValueError(f"Unknown market: {market}. Choose from: {list(MARKETS.keys())}")

    brand_slug = MARKETS[market]["brand_slug"]
    brand_url = f"{BASE_URL}/brand/{brand_slug}"
    output_path = OUTPUT_DIR / f"wolt-{market}-categories.json"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Step 1: Discover venues from brand page
        print(f"[INFO] Fetching brand page: {brand_url}")
        page.goto(brand_url, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        page.evaluate(JS_DISMISS_OVERLAYS)

        venues = page.evaluate(JS_DISCOVER_VENUES)
        print(f"[INFO] Found {len(venues)} venues for {market}")

        # Step 2: Scrape categories + subcategories for each venue
        branches = []
        for i, venue in enumerate(venues):
            slug = venue["slug"]
            print(f"[{i+1}/{len(venues)}] Scraping {slug}...")

            try:
                name, categories = _scrape_venue_categories(page, slug)
                name = name or venue.get("name") or slug

                branches.append({
                    "name": name,
                    "slug": slug,
                    "categories": categories,
                })
            except Exception as e:
                print(f"  -> ERROR: {e}")
                branches.append({
                    "name": venue.get("name") or slug,
                    "slug": slug,
                    "categories": [],
                    "error": str(e),
                })

            if i < len(venues) - 1:
                time.sleep(random.uniform(2, 4))

        browser.close()

    total_cats = sum(len(b["categories"]) for b in branches)
    total_subs = sum(
        sum(len(c["children"]) for c in b["categories"])
        for b in branches
    )
    print(f"[INFO] Total: {len(branches)} branches, {total_cats} categories, {total_subs} subcategories")

    # Store raw result in MongoDB
    fetched_at = datetime.now(tz=timezone.utc)
    wolt_raw_categories.update_one(
        {"market": market},
        {
            "$set": {
                "market": market,
                "fetched_at": fetched_at,
                "branches": branches,
            }
        },
        upsert=True,
    )
    print(f"[OK] Saved raw categories to MongoDB (market={market})")

    # Write cleaned JSON file
    output = {
        "market": market,
        "brand_url": f"/en/aze/baku/brand/{brand_slug}",
        "fetched_at": fetched_at.isoformat(),
        "branches": [
            {
                "name": b["name"],
                "slug": b["slug"],
                "categories": b["categories"],
            }
            for b in branches
        ],
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=4)

    print(f"[OK] Written to {output_path}")
