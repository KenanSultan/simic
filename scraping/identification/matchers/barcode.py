from collections import defaultdict


def match_by_barcode(products):
    """Group products by barcode (GTIN).

    Args:
        products: List of normalized product dicts.

    Returns:
        (matched_groups, unmatched): Tuple of:
            - matched_groups: list of lists, each inner list = products with same barcode
            - unmatched: list of products without a barcode
    """
    by_barcode = defaultdict(list)
    unmatched = []

    for product in products:
        barcode = product.get("barcode")
        if barcode:
            by_barcode[barcode].append(product)
        else:
            unmatched.append(product)

    # Only groups with 2+ products are "matches"; singles are also unmatched
    matched_groups = []
    for barcode, group in by_barcode.items():
        if len(group) >= 2:
            matched_groups.append(group)
        else:
            unmatched.extend(group)

    return matched_groups, unmatched
