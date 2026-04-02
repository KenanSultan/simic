"""General size/volume extraction rules. Applies to ALL products."""

import re

# Boundary after unit: treat case change (e.g. "lG" in "0.5lGrape") as a boundary.
# (?-i:...) locally disables IGNORECASE so [^a-z] only excludes lowercase letters.
_UNIT_BOUNDARY = r"(?-i:(?=[^a-z]|$))"

# Pack pattern: "4x500ml", "6 x 1.5l"
PACK_RE = re.compile(
    r"(\d+)\s*[xXхХ×]\s*(\d+(?:[.,]\d+)?)\s*(ml|l|lt|litr|cl|g|gr|qr|kg|kq)" + _UNIT_BOUNDARY,
    re.IGNORECASE,
)

# Single size: "500ml", "1.5l", "250gr"
SIZE_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(ml|l|lt|litr|cl|g|gr|qr|kg|kq)" + _UNIT_BOUNDARY,
    re.IGNORECASE,
)

# Fallback: bare decimal assumed liters ("0.33" → 330ml)
BARE_VOLUME_RE = re.compile(r"\b(0[.,]\d+|[12][.,]\d+)\b")

# Standardize unit names
UNIT_MAP = {
    "ml": "ml", "l": "l", "lt": "l", "litr": "l", "cl": "cl",
    "g": "g", "gr": "g", "qr": "g", "kg": "kg", "kq": "kg",
}

# Convert to base units
SIZE_NORMALIZERS = {
    "l": ("ml", 1000),
    "cl": ("ml", 10),
    "kg": ("g", 1000),
}
