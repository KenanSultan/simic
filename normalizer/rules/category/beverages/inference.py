"""Post-parse inference rules for beverages category.

These rules set fields based on combinations of already-extracted fields
and the canonical subcategory ID. Applied after parse_product_name().

Also corrects canonical_category_id when product_type detection from the
product name disagrees with the marketplace category assignment. This handles
cases where marketplaces put products in overly broad categories (e.g.,
a kompot product in a "juice" category).

Additionally filters out non-beverage products that end up in beverage
categories due to marketplace miscategorization (e.g., instant coffee
powder in "Soyuq kofe").
"""

import re

# Subcategory IDs
_STILL_WATER_ID = 1401
_SPARKLING_WATER_ID = 1402
_JUICE_ID = 1403
_KOMPOT_ID = 1404

# Packaging types that indicate juice (not kompot)
_JUICE_PACKAGING = {"tetra", "pet"}

# Words in original name that indicate juice (subcategory-scoped)
_JUICE_NAME_RE = re.compile(r"\bsuyu\b", re.IGNORECASE)

# Maps detected product_type → correct canonical subcategory ID.
# Used to override the marketplace category assignment when the product
# name clearly indicates a specific subcategory.
_PRODUCT_TYPE_TO_CATEGORY = {
    "Kompot": 1404,
    "Meyvə şirəsi": 1403,
    "Smuzi": 1403,
    "Limonad": 1406,
    "Kvas": 1411,
    "Şalqam suyu": 1411,
    "Vitamin Water": 1411,
    "Tonik": 1405,
    "Bubble Tea": 1405,
    "Alkoqolsuz pivə": 1407,
    "Soyuq çay": 1409,
    "Soyuq kofe": 1410,
    "Mineral su": 1402,
}

# Brands that are NOT non-alcoholic beer despite triggering "alkoqolsuz" detection
_NOT_BEER_BRANDS = {"Milkis"}


def _is_non_beverage(parsed):
    """Detect products that don't belong in beverage categories.

    Returns True if the product should be excluded (e.g., instant coffee
    powder, hot tea bags measured in grams with small sizes).
    """
    unit = parsed.get("unit")
    size = parsed.get("size")

    # Gram-based small products are powder/granule, not liquid beverages
    # (e.g., Jacobs Cappuccino 12.5g, Carte Noire 8g, Full Coffee 3in1 20g)
    if unit == "g" and size is not None and size <= 100:
        return True

    return False


def apply_inference(parsed, canonical_category_id, original_name=None):
    """Apply inference rules. Modifies parsed dict in place.

    Sets product_type based on category, and corrects canonical_category_id
    when product_type detection suggests a different subcategory.
    If corrected, sets parsed["_corrected_category_id"].

    Returns None via _skip marker if product should be excluded from beverages.
    """
    # ── Filter non-beverages ──
    if _is_non_beverage(parsed):
        parsed["_skip"] = True
        return parsed

    # ── Category correction from product_type ──
    # E.g., "Mineral su" → 1402, "Alkoqolsuz pivə" → 1407
    detected_type = parsed.get("product_type")
    if detected_type and detected_type in _PRODUCT_TYPE_TO_CATEGORY:
        correct_id = _PRODUCT_TYPE_TO_CATEGORY[detected_type]
        if correct_id != canonical_category_id:
            parsed["_corrected_category_id"] = correct_id
            canonical_category_id = correct_id

    # ── Brand-specific category corrections (overrides product_type) ──
    brand = parsed.get("brand") or ""
    if brand in _NOT_BEER_BRANDS and canonical_category_id == 1407:
        parsed["_corrected_category_id"] = 1411
        canonical_category_id = 1411

    # ── Category correction from is_sparkling (water categories) ──
    # Overrides when explicit qazsız/qazlı detected in product name.
    is_sparkling = parsed.get("is_sparkling")
    if is_sparkling is True and canonical_category_id == _STILL_WATER_ID:
        parsed["_corrected_category_id"] = _SPARKLING_WATER_ID
        canonical_category_id = _SPARKLING_WATER_ID
    elif is_sparkling is False and canonical_category_id == _SPARKLING_WATER_ID:
        parsed["_corrected_category_id"] = _STILL_WATER_ID
        canonical_category_id = _STILL_WATER_ID

    # ── Product type inference from category ──
    # Still water subcategory
    if canonical_category_id == _STILL_WATER_ID and parsed.get("product_type") is None:
        parsed["product_type"] = "Qazsız su"

    # Sparkling/mineral water subcategory
    if canonical_category_id == _SPARKLING_WATER_ID and parsed.get("product_type") is None:
        parsed["product_type"] = "Qazlı su"

    # Juice subcategory: infer product_type from packaging/name
    if canonical_category_id == _JUICE_ID and parsed.get("product_type") is None:
        if parsed.get("packaging") in _JUICE_PACKAGING:
            parsed["product_type"] = "Meyvə şirəsi"
        elif original_name and _JUICE_NAME_RE.search(original_name):
            parsed["product_type"] = "Meyvə şirəsi"

    # Kompot subcategory
    if canonical_category_id == _KOMPOT_ID and parsed.get("product_type") is None:
        parsed["product_type"] = "Kompot"

    return parsed
