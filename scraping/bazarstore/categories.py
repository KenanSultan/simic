import json
from pathlib import Path

CATEGORIES_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "categories"
    / "bazarstore-categories.json"
)


def load_leaf_categories() -> list[dict]:
    """
    Load leaf categories from bazarstore-categories.json.

    Returns list of dicts with keys: title, parent_title, root_title, handle.
    Filters out placeholder entries (url/handle = "#").
    """
    with open(CATEGORIES_PATH, encoding="utf-8") as f:
        data = json.load(f)

    leaves = []

    for root in data["data"]:
        root_title = root["title"]
        _collect_leaves(root, root_title=root_title, parent_title=root_title, leaves=leaves)

    return leaves


def _collect_leaves(
    node: dict,
    *,
    root_title: str,
    parent_title: str,
    leaves: list[dict],
):
    children = node.get("children", [])

    if not children:
        # This is a leaf node
        handle = node.get("handle", "")
        if handle == "#" or node.get("url") == "#":
            return

        # Fix malformed handles containing full myshopify URLs
        # e.g. "https://bazar-store-az.myshopify.comxirdavat-3" → "xirdavat-3"
        if "myshopify.com" in handle:
            handle = handle.split("myshopify.com")[-1]

        leaves.append(
            {
                "title": node["title"],
                "parent_title": parent_title,
                "root_title": root_title,
                "handle": handle,
            }
        )
        return

    for child in children:
        _collect_leaves(
            child,
            root_title=root_title,
            parent_title=node["title"],
            leaves=leaves,
        )
