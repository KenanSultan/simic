"""Re-exports from rules.general.text for backward compatibility."""

from scraping.normalization.rules.general.text import (
    normalize_for_matching,
    clean_text,
    DIACRITICS_MAP,
)

__all__ = ["normalize_for_matching", "clean_text", "DIACRITICS_MAP"]
