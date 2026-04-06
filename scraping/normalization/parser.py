"""Product name parser. Thin orchestrator that delegates to RuleLoader for all rules.

Each extraction function takes a RuleLoader to make rule scope explicit.
General rules (text, size, brands) always apply.
Category-specific rules (packaging, sparkling, flavor, etc.) only apply if loaded.
"""

import re

from scraping.normalization.rules.general.text import clean_text, normalize_for_matching
from scraping.normalization.rules.general.size import (
    PACK_RE, SIZE_RE, BARE_VOLUME_RE, UNIT_MAP, SIZE_NORMALIZERS,
)
from scraping.normalization.rules.general.piece_count import PIECE_COUNT_RE


# ── General: Brand extraction ────────────────────────────────────

def _try_match_brand(name, brands):
    """Try to match a brand at the start of the name."""
    name_lower = name.lower()
    for alias, canonical in brands:
        alias_lower = alias.lower()
        if name_lower.startswith(alias_lower):
            rest_raw = name[len(alias):]
            if not rest_raw or not rest_raw[0].isalnum():
                return canonical, rest_raw.strip()
    return None, None


def extract_brand(name, rule_loader):
    """Extract brand from product name. Scope: GENERAL (brands) + CATEGORY (prefixes)."""
    brands = rule_loader.get_brands()
    prefixes = rule_loader.get_prefixes()

    # Try direct match first
    brand, rest = _try_match_brand(name, brands)
    if brand:
        return brand, rest

    # Try stripping known prefixes (category-specific)
    name_normalized = normalize_for_matching(name)
    for prefix in prefixes:
        prefix_norm = normalize_for_matching(prefix)
        if name_normalized.startswith(prefix_norm + " "):
            prefix_word_count = len(prefix.split())
            original_words = name.split()
            stripped = " ".join(original_words[prefix_word_count:])
            brand, rest = _try_match_brand(stripped, brands)
            if brand:
                return brand, rest

    # Last resort: search for brand anywhere in the name
    for alias, canonical in brands:
        alias_norm = normalize_for_matching(alias)
        if not alias_norm:
            continue
        idx = name_normalized.find(alias_norm)
        if idx < 0:
            continue
        before_ok = idx == 0 or not name_normalized[idx - 1].isalnum()
        after_idx = idx + len(alias_norm)
        after_ok = after_idx >= len(name_normalized) or not name_normalized[after_idx].isalnum()
        if before_ok and after_ok:
            alias_words = alias.lower().split()
            result_words = []
            skip = 0
            for w in name.split():
                if skip > 0:
                    skip -= 1
                    continue
                w_norm = normalize_for_matching(w)
                if w_norm == normalize_for_matching(alias_words[0]):
                    remaining_words = name.split()
                    start_idx = remaining_words.index(w)
                    candidate = [normalize_for_matching(ww) for ww in remaining_words[start_idx:start_idx + len(alias_words)]]
                    if candidate == [normalize_for_matching(a) for a in alias_words]:
                        skip = len(alias_words) - 1
                        continue
                result_words.append(w)
            return canonical, " ".join(result_words).strip()

    return None, name


# ── General: Size extraction ─────────────────────────────────────

def extract_size(name):
    """Extract size, unit, and pack_size. Scope: GENERAL."""
    # Try pack pattern first: "4x500ml"
    pack_match = PACK_RE.search(name)
    if pack_match:
        pack_size = int(pack_match.group(1))
        size_val = float(pack_match.group(2).replace(",", "."))
        raw_unit = pack_match.group(3).lower()
        unit = UNIT_MAP.get(raw_unit, raw_unit)
        remaining = name[:pack_match.start()] + name[pack_match.end():]
        remaining = re.sub(r"\s+", " ", remaining).strip()
        if unit in SIZE_NORMALIZERS:
            base_unit, multiplier = SIZE_NORMALIZERS[unit]
            size_val = size_val * multiplier
            unit = base_unit
        return size_val, unit, pack_size, remaining

    # Try single size pattern: "500ml", "1.5l"
    match = SIZE_RE.search(name)
    if match:
        size_val = float(match.group(1).replace(",", "."))
        raw_unit = match.group(2).lower()
        unit = UNIT_MAP.get(raw_unit, raw_unit)
        remaining = name[:match.start()] + name[match.end():]
        remaining = re.sub(r"\s+", " ", remaining).strip()
        if unit in SIZE_NORMALIZERS:
            base_unit, multiplier = SIZE_NORMALIZERS[unit]
            size_val = size_val * multiplier
            unit = base_unit
        return size_val, unit, None, remaining

    # Fallback: bare decimal number assumed to be liters
    bare_match = BARE_VOLUME_RE.search(name)
    if bare_match:
        size_val = float(bare_match.group(1).replace(",", "."))
        remaining = name[:bare_match.start()] + name[bare_match.end():]
        remaining = re.sub(r"\s+", " ", remaining).strip()
        size_val = size_val * 1000
        return size_val, "ml", None, remaining

    return None, None, None, name


# ── Category-specific extractions ────────────────────────────────

def extract_packaging(name, rules):
    """Extract packaging type. Scope: CATEGORY. Rules from packaging.json.

    Returns the first matched type, but removes ALL packaging patterns from the name.
    """
    detected_type = None
    for pattern, packaging_type in rules:
        match = pattern.search(name)
        if match:
            if detected_type is None:
                detected_type = packaging_type
            name = name[:match.start()] + name[match.end():]
            name = re.sub(r"\s+", " ", name).strip()
    return detected_type, name


def extract_sparkling(name, rules):
    """Extract sparkling/still. Scope: CATEGORY. Rules from sparkling.json."""
    for pattern, value in rules:
        match = pattern.search(name)
        if match:
            remaining = name[:match.start()] + name[match.end():]
            remaining = re.sub(r"\s+", " ", remaining).strip()
            return value, remaining
    return None, name


def extract_flavor(name, rules):
    """Extract all flavors. Scope: CATEGORY. Rules from flavors.json.

    Multiple flavors joined with "-".
    """
    flavors = []
    for pattern, flavor in rules:
        match = pattern.search(name)
        if match:
            if flavor not in flavors:
                flavors.append(flavor)
            name = name[:match.start()] + name[match.end():]
            name = re.sub(r"\s+", " ", name).strip()
    if flavors:
        return "-".join(flavors), name
    return None, name


def extract_product_type(name, rules):
    """Detect and remove product type. Scope: CATEGORY. Rules from product_types.json.

    Returns (product_type, remaining_name). Removes ALL matching patterns but keeps first type.
    """
    detected_type = None
    for pattern, ptype in rules:
        match = pattern.search(name)
        if match:
            if detected_type is None:
                detected_type = ptype
            name = name[:match.start()] + name[match.end():]
            name = re.sub(r"\s+", " ", name).strip()
    return detected_type, name


def extract_sugar_free(name, rules):
    """Extract sugar-free indicator. Scope: CATEGORY. Rules from sugar_free.json.

    Returns (is_sugar_free, remaining_name).
    """
    for pattern, value in rules:
        match = pattern.search(name)
        if match:
            remaining = name[:match.start()] + name[match.end():]
            remaining = re.sub(r"\s+", " ", remaining).strip()
            return value, remaining
    return None, name


def extract_product_line(name, rules):
    """Extract product line / sub-brand. Scope: CATEGORY. Rules from product_lines.json.

    Returns (product_line, remaining_name).
    """
    for pattern, canonical in rules:
        match = pattern.search(name)
        if match:
            remaining = name[:match.start()] + name[match.end():]
            remaining = re.sub(r"\s+", " ", remaining).strip()
            return canonical, remaining
    return None, name


# ── Fallback: color words as flavor ──────────────────────────────

_COLOR_PATTERNS = [
    (re.compile(r"\bqırmızı\b|\bqirmizi\b|\bred\b", re.IGNORECASE), "Qırmızı"),
    (re.compile(r"\byaşıl\b|\byasil\b|\bgreen\b", re.IGNORECASE), "Yaşıl"),
    (re.compile(r"\bsarı\b|\bsari\b|\byellow\b", re.IGNORECASE), "Sarı"),
    (re.compile(r"\bqara\b|\bblack\b", re.IGNORECASE), "Qara"),
    (re.compile(r"\bağ\b|\bwhite\b", re.IGNORECASE), "Ağ"),
    (re.compile(r"\bblue\b", re.IGNORECASE), "Blue"),
    (re.compile(r"\bpink\b", re.IGNORECASE), "Pink"),
    (re.compile(r"\bgold\b", re.IGNORECASE), "Gold"),
]


def _extract_color_as_flavor(remaining):
    """If no flavor was found, check remaining text for color words.

    Colors in beverage names often indicate flavor/variant (e.g., "Red" = red fruits).
    Returns (color_as_flavor, updated_remaining).
    """
    for pattern, color in _COLOR_PATTERNS:
        match = pattern.search(remaining)
        if match:
            updated = remaining[:match.start()] + remaining[match.end():]
            updated = re.sub(r"\s+", " ", updated).strip()
            return color, updated
    return None, remaining


# ── Main parser ────────────────────────────────────────────────────

def parse_product_name(name, rule_loader):
    """Parse a product name into structured fields using rules from RuleLoader.

    General rules (brands, sizes) always apply.
    Category-specific rules (packaging, sparkling, flavor, etc.) only if available.
    """
    warnings = []
    name = clean_text(name)

    # Remove common suffixes
    name = re.sub(r"\(\d+\+\)", "", name)  # (18+)
    name = re.sub(r"\s+", " ", name).strip()

    # ── General: Extract brand ──
    brand, name = extract_brand(name, rule_loader)
    if not brand:
        warnings.append("brand_not_found")

    # ── General: Extract size/unit ──
    size, unit, pack_size, name = extract_size(name)
    if size is None:
        warnings.append("size_not_found")

    # ── Category: Sanity check size ──
    sanity_fn = rule_loader.get_sanity_checker()
    if sanity_fn and size and unit:
        size, unit = sanity_fn(size, unit)

    # ── Category: Extract packaging ──
    packaging_rules = rule_loader.get_packaging_rules()
    packaging, name = extract_packaging(name, packaging_rules)

    # ── Category: Extract sparkling/still ──
    sparkling_rules = rule_loader.get_sparkling_rules()
    is_sparkling, name = extract_sparkling(name, sparkling_rules)

    # ── Category: Extract sugar-free indicator ──
    sugar_free_rules = rule_loader.get_sugar_free_rules()
    is_sugar_free, name = extract_sugar_free(name, sugar_free_rules)

    # ── Category: Extract product line / sub-brand ──
    product_line_rules = rule_loader.get_product_line_rules()
    product_line, name = extract_product_line(name, product_line_rules)

    # ── Category: Detect and remove product type (before flavor) ──
    product_type_rules = rule_loader.get_product_type_rules()
    product_type, name = extract_product_type(name, product_type_rules)

    # ── Category: Extract flavor ──
    flavor_rules = rule_loader.get_flavor_rules()
    flavor, name = extract_flavor(name, flavor_rules)

    # ── Clean remaining text ──
    remaining = re.sub(r"\(\s*\)", "", name)
    # General: remove piece counts
    remaining = PIECE_COUNT_RE.sub("", remaining)
    # Category: remove stop phrases and words
    stop_phrases, stop_word_re = rule_loader.get_stop_words()
    for pattern in stop_phrases:
        remaining = pattern.sub("", remaining)
    if stop_word_re:
        remaining = stop_word_re.sub("", remaining)
    remaining = re.sub(r"\s+", " ", remaining).strip()
    remaining = remaining.strip(" .,;:-–—/\\*")
    remaining = re.sub(r"\b\d{5,}\b", "", remaining)  # long numeric codes
    remaining = re.sub(r"\s+", " ", remaining).strip()
    remaining = remaining.strip(" .,;:-–—/\\*") or None

    # ── Fallback: if no flavor found, check remaining for color words as flavor ──
    if not flavor and remaining:
        color_flavor, remaining = _extract_color_as_flavor(remaining)
        if color_flavor:
            flavor = color_flavor
            remaining = remaining.strip(" .,;:-–—/\\*") or None

    # Build normalized name for matching
    if brand:
        full_name = f"{brand} {remaining}".strip() if remaining else brand
    else:
        full_name = remaining or ""

    return {
        "brand": brand,
        "product_name": remaining,
        "remaining_data": remaining,
        "size": size,
        "unit": unit,
        "pack_size": pack_size,
        "packaging": packaging,
        "is_sparkling": is_sparkling,
        "is_sugar_free": is_sugar_free,
        "product_line": product_line,
        "flavor": flavor,
        "product_type": product_type,
        "normalized_brand": normalize_for_matching(brand) if brand else None,
        "normalized_name": normalize_for_matching(full_name),
        "parse_warnings": warnings,
    }
