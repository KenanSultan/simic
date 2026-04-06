"""Rule loading system with explicit scope hierarchy.

Rule scopes (from broadest to narrowest):
    general/   — ALL products, ALL categories, ALL markets
    category/  — specific top-level category (e.g., beverages)
    market/    — specific marketplace (e.g., araz)
    brand/     — specific brand (future)

Usage:
    loader = RuleLoader(category_slug="spirtsiz-ickiler", market="araz")
    brands = loader.get_brands()                    # general
    flavors = loader.get_flavor_rules()             # category-specific
    mapping = loader.get_category_mapping("wolt")   # market-specific
"""

import json
import re
from pathlib import Path

_RULES_DIR = Path(__file__).resolve().parent

# Category slug → directory name mapping
_CATEGORY_DIR_MAP = {
    "spirtsiz-ickiler": "beverages",
}


class RuleLoader:
    """Loads rules by scope. Each method documents which scope it reads from."""

    def __init__(self, category_slug=None, market=None):
        self.category_slug = category_slug
        self.market = market
        self._cache = {}

    def _load_json(self, path):
        """Load and cache a JSON file."""
        key = str(path)
        if key not in self._cache:
            with open(path, encoding="utf-8") as f:
                self._cache[key] = json.load(f)
        return self._cache[key]

    def _category_dir(self):
        """Resolve category slug to directory path."""
        if not self.category_slug:
            return None
        dir_name = _CATEGORY_DIR_MAP.get(self.category_slug)
        if not dir_name:
            return None
        path = _RULES_DIR / "category" / dir_name
        return path if path.exists() else None

    # ── General rules (always available) ──────────────────────────

    def get_brands(self):
        """Load brand dictionary. Scope: GENERAL."""
        data = self._load_json(_RULES_DIR / "general" / "brands.json")
        brands = []
        for entry in data["brands"]:
            canonical = entry["canonical"]
            for alias in entry["aliases"]:
                brands.append((alias, canonical))
        brands.sort(key=lambda x: len(x[0]), reverse=True)
        return brands

    def get_prefixes(self):
        """Load product-type prefixes for brand extraction. Scope: CATEGORY."""
        cat_dir = self._category_dir()
        if not cat_dir:
            return []
        path = cat_dir / "prefixes.json"
        if not path.exists():
            return []
        data = self._load_json(path)
        return data.get("prefixes", [])

    # ── Category-specific rules ───────────────────────────────────

    def _load_category_patterns(self, filename, key="patterns"):
        """Load regex patterns from a category-specific JSON file."""
        cat_dir = self._category_dir()
        if not cat_dir:
            return []
        path = cat_dir / filename
        if not path.exists():
            return []
        data = self._load_json(path)
        result = []
        for entry in data.get(key, []):
            regex = entry.get("regex", "")
            compiled = re.compile(regex, re.IGNORECASE)
            result.append((compiled, entry))
        return result

    def get_packaging_rules(self):
        """Load packaging patterns. Scope: CATEGORY (beverages)."""
        rules = self._load_category_patterns("packaging.json")
        return [(pattern, entry["type"]) for pattern, entry in rules]

    def get_sparkling_rules(self):
        """Load sparkling/still patterns. Scope: CATEGORY (beverages)."""
        rules = self._load_category_patterns("sparkling.json")
        return [(pattern, entry["value"]) for pattern, entry in rules]

    def get_product_type_rules(self):
        """Load product type patterns. Scope: CATEGORY (beverages)."""
        rules = self._load_category_patterns("product_types.json")
        return [(pattern, entry["type"]) for pattern, entry in rules]

    def get_stop_words(self):
        """Load stop phrases and words. Scope: CATEGORY (beverages).

        Returns (compiled_phrases, compiled_word_re).
        """
        cat_dir = self._category_dir()
        if not cat_dir:
            return [], None
        path = cat_dir / "stop_words.json"
        if not path.exists():
            return [], None
        data = self._load_json(path)
        phrases = [re.compile(p, re.IGNORECASE) for p in data.get("phrases", [])]
        words = data.get("words", [])
        word_re = re.compile(
            r"\b(?:" + "|".join(re.escape(w) for w in words) + r")\b",
            re.IGNORECASE,
        ) if words else None
        return phrases, word_re

    def get_flavor_rules(self):
        """Load flavor patterns. Scope: CATEGORY (beverages).

        Returns list of (compiled_regex, canonical_flavor).
        Compound patterns come first.
        """
        cat_dir = self._category_dir()
        if not cat_dir:
            return []
        path = cat_dir / "flavors.json"
        if not path.exists():
            return []
        data = self._load_json(path)
        result = []

        for section in ["compound_patterns", "single_patterns"]:
            for entry in data.get(section, []):
                combined = "|".join(r"\b" + p + r"\b" for p in entry["patterns"])
                compiled = re.compile(combined, re.IGNORECASE)
                result.append((compiled, entry["canonical"]))

        return result

    def get_sugar_free_rules(self):
        """Load sugar-free indicator patterns. Scope: CATEGORY."""
        rules = self._load_category_patterns("sugar_free.json")
        return [(pattern, entry["value"]) for pattern, entry in rules]

    def get_product_line_rules(self):
        """Load product line / sub-brand patterns. Scope: CATEGORY."""
        rules = self._load_category_patterns("product_lines.json")
        return [(pattern, entry["canonical"]) for pattern, entry in rules]

    def get_sanity_checker(self):
        """Load sanity check function. Scope: CATEGORY (beverages)."""
        cat_dir = self._category_dir()
        if not cat_dir:
            return None
        try:
            from scraping.normalization.rules.category.beverages.sanity import sanity_check_size
            return sanity_check_size
        except ImportError:
            return None

    def get_inference_fn(self):
        """Load post-parse inference function. Scope: CATEGORY (beverages)."""
        cat_dir = self._category_dir()
        if not cat_dir:
            return None
        try:
            from scraping.normalization.rules.category.beverages.inference import apply_inference
            return apply_inference
        except ImportError:
            return None

    # ── Market-specific rules ─────────────────────────────────────

    def get_abbreviations(self):
        """Load market-specific abbreviations. Scope: MARKET."""
        if not self.market:
            return []
        path = _RULES_DIR / "market" / self.market / "abbreviations.json"
        if not path.exists():
            return []
        data = self._load_json(path)
        return data.get("abbreviations", [])

    def get_category_mapping_path(self, source_type):
        """Get path to category mapping file. Scope: MARKET."""
        if not self.market:
            raise ValueError("Market not set on RuleLoader")
        path = _RULES_DIR / "market" / self.market / f"{source_type}_categories.json"
        if not path.exists():
            raise FileNotFoundError(f"Category mapping not found: {path}")
        return path
