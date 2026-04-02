import json
from pathlib import Path

CATEGORIES_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "categories"
    / "neptun-categories.json"
)


def load_leaf_categories() -> list[dict]:
    """
    Load leaf categories from neptun-categories.json.

    Returns list of dicts with keys: title, parent_title, url.
    Filters out external URLs (e.g. soliton.az) and empty parents.
    """
    with open(CATEGORIES_PATH, encoding="utf-8") as f:
        data = json.load(f)

    leaves = []

    for root in data["data"]:
        parent_title = root["title"]

        for child in root.get("children", []):
            url = child.get("url", "")
            if not url.startswith("https://neptun.az/"):
                continue

            leaves.append(
                {
                    "title": child["title"],
                    "parent_title": parent_title,
                    "url": url,
                }
            )

    return leaves
