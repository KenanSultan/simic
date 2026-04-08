"""Cross-source product matching: website products vs Wolt golden records.

Three-tier hybrid approach:
  Tier 1 (EXACT)          — All extracted fields identical → confidence 0.95
  Tier 2 (EXACT-ON-SHARED)— Match on fields non-null on both sides → confidence 0.90
  Tier 3 (SCORING)        — Weighted field similarity → variable confidence

Hard requirements: brand + size + unit must match to even consider a pair.
"""

import logging
from collections import Counter

logger = logging.getLogger(__name__)


# Fields used in exact matching (beyond the hard requirements)
_EXACT_FIELDS = [
    "normalized_name",
    "packaging",
    "flavor",
    "is_sparkling",
    "product_type",
    "is_sugar_free",
    "product_line",
]

# Scoring weights for Tier 3
_SCORE_WEIGHTS = {
    "normalized_name": 0.25,
    "flavor": 0.20,
    "packaging": 0.15,
    "product_type": 0.15,
    "is_sugar_free": 0.10,
    "product_line": 0.10,
    "price": 0.05,
}

# Per-field null semantics
# "neutral" = null vs value → skip field (no penalty, no reward)
# "default" = null has a default value to compare against
# "blocking" = if both non-null and different → no match possible
_NULL_SEMANTICS = {
    "normalized_name": "neutral",
    "packaging": "neutral",
    "flavor": "blocking",          # different flavors = different products
    "is_sparkling": "blocking",    # sparkling ≠ still = different products
    "product_type": "neutral",
    "is_sugar_free": {"default": False},  # null means "has sugar"
    "product_line": "neutral",
}


def _name_token_overlap(name_a, name_b):
    """Jaccard similarity on word tokens."""
    if not name_a or not name_b:
        return 0.0
    tokens_a = set(name_a.split())
    tokens_b = set(name_b.split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = len(tokens_a & tokens_b)
    union = len(tokens_a | tokens_b)
    return intersection / union if union > 0 else 0.0


def _get_field_value(product, field):
    """Get field value, applying default for null semantics."""
    value = product.get(field)
    if value is None:
        semantics = _NULL_SEMANTICS.get(field, "neutral")
        if isinstance(semantics, dict) and "default" in semantics:
            return semantics["default"]
    return value


def _fields_match(web_val, golden_val, field):
    """Check if two field values match, respecting null semantics.

    Returns:
        True if values match
        False if values conflict
        None if comparison should be skipped (one side is null with neutral semantics)
        "block" if both non-null, different, and field has blocking semantics
    """
    semantics = _NULL_SEMANTICS.get(field, "neutral")

    # Apply defaults for fields with default null semantics
    if isinstance(semantics, dict) and "default" in semantics:
        if web_val is None:
            web_val = semantics["default"]
        if golden_val is None:
            golden_val = semantics["default"]

    # Both null → match
    if web_val is None and golden_val is None:
        return True

    # One null → depends on semantics
    if web_val is None or golden_val is None:
        if semantics in ("neutral", "blocking"):
            return None  # Skip — one side missing
        return None

    # Both non-null → compare
    if web_val == golden_val:
        return True

    # Both non-null, different
    if semantics == "blocking":
        return "block"  # Hard block — different products
    return False


class CrossSourceMatcher:
    """Matches website products against Wolt golden records."""

    def __init__(self, score_threshold=0.70, review_threshold=0.50):
        self.score_threshold = score_threshold
        self.review_threshold = review_threshold

    def match(self, web_products, golden_docs, web_prices=None, golden_prices=None):
        """Match website products to golden records.

        Args:
            web_products: List of normalized website product dicts.
            golden_docs: List of golden record match documents (from MongoDB).
            web_prices: Optional dict {product_id: price} for website products.
            golden_prices: Optional dict {golden_doc_id: price} for golden records.

        Returns:
            matched: List of (web_product, golden_doc, tier, confidence)
            unmatched: List of web_products that didn't match
            stats: Counter of match tier distribution
        """
        web_prices = web_prices or {}
        golden_prices = golden_prices or {}

        # Build index: (normalized_brand, size, unit) → list of golden docs
        # This enforces the hard requirements efficiently
        golden_index = {}
        for doc in golden_docs:
            gr = doc["golden_record"]
            key = (
                gr.get("normalized_brand") or "",
                gr.get("size"),
                gr.get("unit"),
            )
            golden_index.setdefault(key, []).append(doc)

        matched = []
        unmatched = []
        stats = Counter()

        for wp in web_products:
            key = (
                wp.get("normalized_brand") or "",
                wp.get("size"),
                wp.get("unit"),
            )

            candidates = golden_index.get(key, [])
            if not candidates:
                unmatched.append(wp)
                stats["no_candidates"] += 1
                continue

            wp_price = wp.get("price") or web_prices.get(wp.get("product_id"))

            # Tier 1: EXACT
            result = self._tier_exact(wp, candidates)
            if result:
                matched.append((wp, result, "exact", 0.95))
                stats["exact"] += 1
                continue

            # Tier 2: EXACT-ON-SHARED
            result = self._tier_exact_shared(wp, candidates)
            if result:
                matched.append((wp, result, "exact_shared", 0.90))
                stats["exact_shared"] += 1
                continue

            # Tier 3: SCORING
            result, score, needs_review = self._tier_scoring(
                wp, candidates, wp_price, golden_prices
            )
            if result:
                tier_name = "scoring_review" if needs_review else "scoring"
                matched.append((wp, result, tier_name, score))
                stats[tier_name] += 1
                continue

            unmatched.append(wp)
            stats["unmatched"] += 1

        return matched, unmatched, stats

    def _tier_exact(self, wp, candidates):
        """Tier 1: All extracted fields must be identical (both non-null)."""
        for doc in candidates:
            gr = doc["golden_record"]
            all_match = True
            for field in _EXACT_FIELDS:
                web_val = wp.get(field)
                golden_val = gr.get(field)
                # Both must be non-null AND equal
                if web_val is None or golden_val is None:
                    all_match = False
                    break
                if web_val != golden_val:
                    all_match = False
                    break
            if all_match:
                return doc
        return None

    def _tier_exact_shared(self, wp, candidates):
        """Tier 2: Match on fields non-null on BOTH sides. Skip null fields."""
        for doc in candidates:
            gr = doc["golden_record"]
            all_shared_match = True
            shared_count = 0

            for field in _EXACT_FIELDS:
                result = _fields_match(wp.get(field), gr.get(field), field)
                if result is None:
                    continue  # Skip — one side is null
                if result == "block" or result is False:
                    all_shared_match = False
                    break
                shared_count += 1

            # Need at least 2 shared fields matching (beyond brand+size)
            if all_shared_match and shared_count >= 2:
                return doc
        return None

    def _tier_scoring(self, wp, candidates, wp_price, golden_prices):
        """Tier 3: Weighted score from field comparisons.

        Blocking fields (flavor, is_sparkling) prevent match if both non-null and different.
        """
        best_score = 0
        best_doc = None

        for doc in candidates:
            gr = doc["golden_record"]
            score = 0.0
            max_possible = 0.0
            blocked = False

            for field, weight in _SCORE_WEIGHTS.items():
                if field == "price":
                    continue  # Handle separately

                if field == "normalized_name":
                    overlap = _name_token_overlap(
                        wp.get("normalized_name") or "",
                        gr.get("normalized_name") or "",
                    )
                    score += weight * overlap
                    max_possible += weight
                else:
                    result = _fields_match(wp.get(field), gr.get(field), field)
                    if result == "block":
                        blocked = True
                        break
                    if result is None:
                        continue  # Null field, skip
                    max_possible += weight
                    if result:
                        score += weight

            if blocked:
                continue

            # Price similarity
            golden_price = golden_prices.get(doc.get("_id"))
            if wp_price and golden_price and golden_price > 0:
                price_ratio = min(wp_price, golden_price) / max(wp_price, golden_price)
                score += _SCORE_WEIGHTS["price"] * price_ratio
                max_possible += _SCORE_WEIGHTS["price"]

            # Normalize score to 0-1 range based on max possible
            if max_possible > 0:
                normalized_score = score / max_possible
            else:
                normalized_score = 0

            if normalized_score > best_score:
                best_score = normalized_score
                best_doc = doc

        if best_doc and best_score >= self.score_threshold:
            return best_doc, best_score, False
        elif best_doc and best_score >= self.review_threshold:
            return best_doc, best_score, True

        return None, 0, False
