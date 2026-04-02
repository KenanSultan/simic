import json
import re
import unicodedata
from pathlib import Path

from scraping.normalization.rules.general.text import normalize_for_matching

_CATEGORIES_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "categories"


class CategoryAssigner:
    """Two-layer category assigner.

    Layer 1: Direct mappings (wolt_category → canonical_category_id).
    Layer 2: Rule-based mappings (keyword matching on normalized product name).
    """

    def __init__(self, mapping_path):
        with open(mapping_path, encoding="utf-8") as f:
            data = json.load(f)

        self.direct = {}
        for entry in data.get("direct_mappings", []):
            key = unicodedata.normalize("NFC", entry["wolt_category"].strip())
            self.direct[key] = entry["canonical_category_id"]

        self.rules = {}
        for entry in data.get("rule_based_mappings", []):
            key = unicodedata.normalize("NFC", entry["wolt_category"].strip())
            self.rules[key] = {
                "rules": entry["rules"],
                "default": entry.get("default_canonical_category_id"),
            }

    def all_wolt_categories(self):
        """Return all Wolt category names that have any mapping."""
        return set(self.direct.keys()) | set(self.rules.keys())

    def assign(self, wolt_category, product_name):
        """Assign a canonical category ID to a product."""
        wolt_category = unicodedata.normalize("NFC", wolt_category.strip())

        # Layer 1: direct mapping
        if wolt_category in self.direct:
            return self.direct[wolt_category]

        # Layer 2: rule-based mapping
        if wolt_category in self.rules:
            config = self.rules[wolt_category]
            normalized = normalize_for_matching(product_name)
            for rule in config["rules"]:
                for keyword in rule["keywords"]:
                    if normalize_for_matching(keyword) in normalized:
                        return rule["canonical_category_id"]
            return config["default"]

        return None


def load_category_assigner(market, source_type):
    """Load a CategoryAssigner from rules/market/{market}/ directory."""
    from scraping.normalization.rules import RuleLoader
    loader = RuleLoader(market=market)
    path = loader.get_category_mapping_path(source_type)
    return CategoryAssigner(path)


def load_canonical_categories():
    """Load canonical category tree."""
    path = _CATEGORIES_DIR / "canonical-categories.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    categories = {}
    for parent in data["categories"]:
        categories[parent["id"]] = {
            "name": parent["name"],
            "slug": parent["slug"],
            "parent_id": None,
        }
        for child in parent.get("children", []):
            categories[child["id"]] = {
                "name": child["name"],
                "slug": child["slug"],
                "parent_id": parent["id"],
            }
    return categories


def get_subcategory_ids(canonical_categories, parent_slug):
    """Get all canonical category IDs under a parent slug (inclusive)."""
    parent_id = None
    for cat_id, cat in canonical_categories.items():
        if cat["slug"] == parent_slug:
            parent_id = cat_id
            break

    if parent_id is None:
        raise ValueError(f"Category slug not found: {parent_slug}")

    ids = {parent_id}
    for cat_id, cat in canonical_categories.items():
        if cat["parent_id"] == parent_id:
            ids.add(cat_id)
    return ids
