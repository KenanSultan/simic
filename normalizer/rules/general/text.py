"""General text normalization rules. Applies to ALL products, ALL categories, ALL markets."""

import re
import unicodedata

DIACRITICS_MAP = str.maketrans({
    "ə": "e", "Ə": "E",
    "ş": "s", "Ş": "S",
    "ö": "o", "Ö": "O",
    "ü": "u", "Ü": "U",
    "ç": "c", "Ç": "C",
    "ğ": "g", "Ğ": "G",
    "ı": "i", "İ": "I",
    "®": "",
})

# Collapse doubled consonants for matching (cappuccino → capucino)
DOUBLED_CONSONANT_RE = re.compile(r"([bcdfghjklmnpqrstvwxyz])\1+")


def normalize_for_matching(text):
    """Convert text to ASCII lowercase for matching purposes."""
    if not text:
        return ""
    text = text.translate(DIACRITICS_MAP)
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = DOUBLED_CONSONANT_RE.sub(r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean_text(text):
    """Strip whitespace, normalize unicode, remove control characters and quotes."""
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", text)
    text = re.sub(r'["""\'«»]', "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
