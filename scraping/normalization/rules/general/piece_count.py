"""General piece count removal. Applies to ALL products."""

import re

# "1əd", "1 ədəd" — redundant (every product is 1 piece by default)
PIECE_COUNT_RE = re.compile(r"\b\d+\s*(?:ədəd|əd)\b\.?", re.IGNORECASE)
