from scraping.normalization.category import load_canonical_categories

_CACHE = None


def get_category_map():
    """Return {category_id: category_name} dict, cached after first call."""
    global _CACHE
    if _CACHE is None:
        cats = load_canonical_categories()
        _CACHE = {cid: info["name"] for cid, info in cats.items()}
    return _CACHE


def get_category_choices():
    """Return list of (id, name) tuples for filter dropdowns.

    Only includes subcategories of 'Spirtsiz içkilər' (id 14).
    """
    cats = load_canonical_categories()
    result = []
    for cid, info in cats.items():
        if info["parent_id"] == 14:
            result.append((cid, info["name"]))
    return sorted(result, key=lambda x: x[1])
