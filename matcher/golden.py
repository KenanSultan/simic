import logging
from collections import Counter

logger = logging.getLogger(__name__)

# Fields resolved by most-frequent-value consensus
_CONSENSUS_FIELDS = [
    # General (always present)
    "brand", "product_name", "normalized_brand", "normalized_name",
    "size", "unit", "original_name", "canonical_category_id",
    # Category-specific (null for non-applicable categories)
    "packaging", "flavor", "product_type",
    "is_sparkling", "is_sugar_free", "product_line",
]

# Fields resolved by first non-null value
_ANY_NON_NULL_FIELDS = ["pack_size", "barcode", "image", "local_image"]


def create_golden_record_consensus(match_group):
    """Create a golden record from a group of matched products using consensus.

    For Wolt-only matches: most frequent value wins for text fields,
    any non-null value for barcode.

    Args:
        match_group: List of normalized product dicts (all representing the same product).

    Returns:
        Dict with golden record fields + provenance.
    """
    def most_frequent(values):
        """Return most common non-null value."""
        filtered = [v for v in values if v]
        if not filtered:
            return None
        return Counter(filtered).most_common(1)[0][0]

    def any_non_null(values):
        for v in values:
            if v:
                return v
        return None

    # Warn if size or unit differs within the group — strong signal of false match
    sizes = {p.get("size") for p in match_group if p.get("size") is not None}
    units = {p.get("unit") for p in match_group if p.get("unit") is not None}
    warnings = []
    if len(sizes) > 1:
        names = [p.get("original_name", "?") for p in match_group[:3]]
        warnings.append(f"size_mismatch:{sizes}")
        logger.warning("Golden record has mixed sizes %s — possible false match: %s", sizes, names)
    if len(units) > 1:
        names = [p.get("original_name", "?") for p in match_group[:3]]
        warnings.append(f"unit_mismatch:{units}")
        logger.warning("Golden record has mixed units %s — possible false match: %s", units, names)

    record = {}
    for field in _CONSENSUS_FIELDS:
        record[field] = most_frequent([p.get(field) for p in match_group])
    for field in _ANY_NON_NULL_FIELDS:
        record[field] = any_non_null([p.get(field) for p in match_group])
    record["branch_count"] = len(set(p.get("branch") for p in match_group))
    if warnings:
        record["golden_warnings"] = warnings
    return record
