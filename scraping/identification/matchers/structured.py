from collections import defaultdict


def match_by_structured_fields(products):
    """Group products by parsed structured fields: (brand, size, unit, pack_size, flavor).

    For beverages, products with same brand, size, and flavor are considered
    identical regardless of packaging or remaining text differences.

    Requires brand to be present — brandless products pass through unmatched.

    Args:
        products: List of normalized product dicts (unmatched from prior tiers).

    Returns:
        (matched_groups, unmatched)
    """
    by_key = defaultdict(list)
    no_brand = []

    for product in products:
        brand = product.get("normalized_brand") or ""
        flavor = product.get("flavor") or ""
        if not brand or not flavor:
            no_brand.append(product)
            continue
        key = (
            brand,
            product.get("size"),
            product.get("unit"),
            product.get("pack_size"),
            flavor,
        )
        by_key[key].append(product)

    matched_groups = []
    unmatched = list(no_brand)

    for key, group in by_key.items():
        if len(group) >= 2:
            matched_groups.append(group)
        else:
            unmatched.extend(group)

    return matched_groups, unmatched


def match_by_structured_sparkling(products):
    """Group products by (brand, size, unit, pack_size, is_sparkling, packaging, flavor).

    For beverages where sparkling and packaging are known, these fields plus
    brand and size are enough to identify identical products. Flavor can be null.

    Requires brand, is_sparkling, and packaging to be present.

    Args:
        products: List of normalized product dicts (unmatched from prior tiers).

    Returns:
        (matched_groups, unmatched)
    """
    by_key = defaultdict(list)
    skipped = []

    for product in products:
        brand = product.get("normalized_brand") or ""
        is_sparkling = product.get("is_sparkling")
        packaging = product.get("packaging")
        if not brand or is_sparkling is None or not packaging:
            skipped.append(product)
            continue
        key = (
            brand,
            product.get("size"),
            product.get("unit"),
            product.get("pack_size"),
            is_sparkling,
            packaging,
            product.get("flavor") or "",
        )
        by_key[key].append(product)

    matched_groups = []
    unmatched = list(skipped)

    for key, group in by_key.items():
        if len(group) >= 2:
            matched_groups.append(group)
        else:
            unmatched.extend(group)

    return matched_groups, unmatched
