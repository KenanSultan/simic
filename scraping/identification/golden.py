import logging
from collections import Counter

logger = logging.getLogger(__name__)


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

    record = {
        "brand": most_frequent([p.get("brand") for p in match_group]),
        "product_name": most_frequent([p.get("product_name") for p in match_group]),
        "normalized_brand": most_frequent([p.get("normalized_brand") for p in match_group]),
        "normalized_name": most_frequent([p.get("normalized_name") for p in match_group]),
        "size": most_frequent([p.get("size") for p in match_group]),
        "unit": most_frequent([p.get("unit") for p in match_group]),
        "pack_size": any_non_null([p.get("pack_size") for p in match_group]),
        "packaging": most_frequent([p.get("packaging") for p in match_group]),
        "flavor": most_frequent([p.get("flavor") for p in match_group]),
        "product_type": most_frequent([p.get("product_type") for p in match_group]),
        "is_sparkling": most_frequent([p.get("is_sparkling") for p in match_group]),
        "barcode": any_non_null([p.get("barcode") for p in match_group]),
        "canonical_category_id": most_frequent([p.get("canonical_category_id") for p in match_group]),
        "image": any_non_null([p.get("image") for p in match_group]),
        "local_image": any_non_null([p.get("local_image") for p in match_group]),
        "original_name": most_frequent([p.get("original_name") for p in match_group]),
        "branch_count": len(set(p.get("branch") for p in match_group)),
    }
    if warnings:
        record["golden_warnings"] = warnings
    return record
