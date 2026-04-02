from collections import defaultdict


def dedup_within_branch(products):
    """Remove duplicates within the same branch.

    A product appears multiple times in a branch if it's listed in multiple categories.
    Keep the first occurrence (they should be identical).

    Args:
        products: List of normalized product dicts.

    Returns:
        Deduplicated list.
    """
    by_branch = defaultdict(dict)

    for product in products:
        branch = product["branch"]
        barcode = product.get("barcode")
        name_key = product.get("normalized_name", "") + "|" + str(product.get("size")) + "|" + str(product.get("unit"))

        # Prefer barcode as dedup key, fallback to name+size+unit
        key = barcode if barcode else name_key

        if key not in by_branch[branch]:
            by_branch[branch][key] = product

    result = []
    for branch_products in by_branch.values():
        result.extend(branch_products.values())

    return result
