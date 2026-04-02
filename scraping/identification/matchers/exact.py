from collections import defaultdict


def match_by_exact_fields(products):
    """Group products by exact match on (normalized_brand, normalized_name, size, unit, packaging, flavor).

    Args:
        products: List of normalized product dicts (unmatched from prior tiers).

    Returns:
        (matched_groups, unmatched)
    """
    by_key = defaultdict(list)

    for product in products:
        key = (
            product.get("normalized_brand") or "",
            product.get("normalized_name") or "",
            product.get("size"),
            product.get("unit"),
            product.get("packaging"),
            product.get("flavor") or "",
        )
        by_key[key].append(product)

    matched_groups = []
    unmatched = []
    for key, group in by_key.items():
        if len(group) >= 2:
            matched_groups.append(group)
        else:
            unmatched.extend(group)

    return matched_groups, unmatched
