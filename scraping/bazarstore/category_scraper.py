import json
import re
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

from scraping.mongo import bazarstore_raw_categories

BASE_URL = "https://bazarstore.az"
OUTPUT_PATH = Path(__file__).resolve().parents[2] / "data" / "categories" / "bazarstore-categories.json"

EMOJI_PATTERN = re.compile(
    r"^[\U0001F000-\U0001FFFF\u2600-\u27BF\u2702-\u27B0\uFE0F\u200D\u20E3"
    r"\U0001F1E0-\U0001F1FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF"
    r"\u2328\u23CF\u23E9-\u23F3\u23F8-\u23FA\u2934\u2935\u25AA\u25AB"
    r"\u25B6\u25C0\u25FB-\u25FE\u2600-\u2604\u260E\u2611\u2614\u2615"
    r"\u2618\u261D\u2620\u2622\u2623\u2626\u262A\u262E\u262F\u2638-\u263A"
    r"\u2640\u2642\u2648-\u2653\u265F\u2660\u2663\u2665\u2666\u2668\u267B"
    r"\u267E\u267F\u2692-\u2697\u2699\u269B\u269C\u26A0\u26A1\u26A7"
    r"\u26AA\u26AB\u26B0\u26B1\u26BD\u26BE\u26C4\u26C5\u26C8\u26CE\u26CF"
    r"\u26D1\u26D3\u26D4\u26E9\u26EA\u26F0-\u26F5\u26F7-\u26FA\u26FD"
    r"\u2702\u2705\u2708-\u270D\u270F\u2712\u2714\u2716\u271D\u2721\u2728"
    r"\u2733\u2734\u2744\u2747\u274C\u274E\u2753-\u2755\u2757\u2763\u2764"
    r"\u2795-\u2797\u27A1\u27B0\u27BF\u2934\u2935\u2B05-\u2B07\u2B1B\u2B1C"
    r"\u2B50\u2B55\u3030\u303D\u3297\u3299\u00A9\u00AE\u200D\uFE0F\u20E3"
    r"\u270A\u270B\u270C\u270D\u2764\uFE0F\u200D\U0001F525\u200D\U0001FA79"
    r"\u2388\u2600-\u27BF✏️]+\s*"
)


def clean_name(name: str) -> str:
    return EMOJI_PATTERN.sub("", name).strip()


def clean_tree(nodes: list) -> None:
    for node in nodes:
        node["title"] = clean_name(node.pop("name"))
        clean_tree(node["children"])


JS_EXTRACT_TREE = """() => {
    const topUl = document.querySelector('div.header-sidecategory > ul.site-cat');
    if (!topUl) return [];

    function parseLevel(ul) {
        const items = [];
        ul.querySelectorAll(':scope > li').forEach(li => {
            const a = li.querySelector(':scope > a');
            if (!a) return;
            const childUl = li.querySelector(':scope > div > ul');
            items.push({
                name: a.textContent.trim(),
                handle: (a.getAttribute('href') || '').replace('/collections/', ''),
                url: a.getAttribute('href'),
                children: childUl ? parseLevel(childUl) : []
            });
        });
        return items;
    }

    return parseLevel(topUl);
}"""


def scrape_bazarstore_categories():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BASE_URL, wait_until="domcontentloaded")
        page.click("nav.category_box span.side-categories")
        page.wait_for_selector("ul.site-cat li")

        raw_tree = page.evaluate(JS_EXTRACT_TREE)
        browser.close()

    print(f"[INFO] Extracted {len(raw_tree)} top-level categories")

    # store raw result in MongoDB
    bazarstore_raw_categories.update_one(
        {"source": "nav_menu"},
        {
            "$set": {
                "source": "nav_menu",
                "fetched_at": datetime.now(tz=timezone.utc),
                "data": raw_tree,
            }
        },
        upsert=True,
    )
    print("[OK] Saved raw categories to MongoDB")

    # clean emoji prefixes and write JSON file
    clean_tree(raw_tree)
    output = {"data": raw_tree}

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=4)

    print(f"[OK] Written to {OUTPUT_PATH}")
