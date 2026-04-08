import re

from normalizer.extractors.base import BaseExtractor
from normalizer.parser import parse_product_name


# Turkish-style pack count suffixes: 6LI, 6 LI, 4-LU, 4LÜ, etc.
_PACK_COUNT_RE = re.compile(
    r"\b(\d+)\s*[-]?\s*(?:LI|Lİ|LU|LÜ|Lı|Li|Lu|Lü)\b",
    re.IGNORECASE,
)


class BazarstoreWebsiteExtractor(BaseExtractor):
    """Extracts normalized products from Bazarstore website raw documents.

    Handles Bazarstore-specific Shopify format, ALL CAPS naming,
    abbreviations (TP, BAN., M.ŞİRƏSİ), and Turkish pack count suffixes (6LI).
    """

    def __init__(self, marketplace, rule_loader):
        self.marketplace = marketplace
        self.rule_loader = rule_loader
        self._abbreviation_patterns = self._compile_abbreviations()

    def _compile_abbreviations(self):
        abbreviations = self.rule_loader.get_abbreviations()
        patterns = []
        for abbr in abbreviations:
            regex = re.compile(abbr["pattern"], re.IGNORECASE)
            patterns.append((regex, abbr["expansion"]))
        return patterns

    def _to_title_case(self, name):
        """Convert ALL CAPS to title case, handling hyphens."""
        parts = name.split()
        result = []
        for part in parts:
            if "-" in part:
                subparts = part.split("-")
                result.append("-".join(s.capitalize() for s in subparts))
            else:
                result.append(part.capitalize())
        return " ".join(result)

    def _extract_pack_count(self, name):
        """Extract Turkish pack count suffix (6LI, 4-LU) before parsing.

        Returns (pack_size, cleaned_name).
        """
        match = _PACK_COUNT_RE.search(name)
        if match:
            pack_size = int(match.group(1))
            name = name[:match.start()] + name[match.end():]
            name = re.sub(r"\s{2,}", " ", name).strip()
            return pack_size, name
        return None, name

    def _preprocess_name(self, name):
        """Abbreviation expansion on ALL CAPS, then title case.

        Expanding abbreviations first avoids Turkish İ/i Unicode issues
        where re.IGNORECASE doesn't map İ↔i correctly.
        """
        for pattern, expansion in self._abbreviation_patterns:
            name = pattern.sub(expansion, name)
        name = self._to_title_case(name)
        return name

    def extract(self, raw_doc, category_assigner):
        product = raw_doc.get("product", {})
        product_id = raw_doc.get("product_id", str(product.get("id", "")))

        meta = product.get("_meta", {})
        category_title = meta.get("category_title", "")
        name = product.get("title", "")

        canonical_category_id = category_assigner.assign(category_title, name)
        if canonical_category_id is None:
            return None

        if not name:
            return None

        # Extract pack count before preprocessing (works better on ALL CAPS)
        pack_count, name = self._extract_pack_count(name)

        # Pre-process: title case + abbreviation expansion
        processed_name = self._preprocess_name(name)

        parsed = parse_product_name(processed_name, self.rule_loader)

        # If we extracted a pack count and parser didn't find one, use ours
        if pack_count and not parsed["pack_size"]:
            parsed["pack_size"] = pack_count

        # Apply category-specific inference rules (may correct category)
        inference_fn = self.rule_loader.get_inference_fn()
        if inference_fn:
            inference_fn(parsed, canonical_category_id, original_name=name)
            if parsed.get("_skip"):
                return None
            if "_corrected_category_id" in parsed:
                canonical_category_id = parsed.pop("_corrected_category_id")

        # Brand: prefer vendor field if parser didn't find one
        vendor = product.get("vendor", "")
        if not parsed["brand"] and vendor and vendor != "Bazarstore":
            parsed["brand"] = vendor
            from normalizer.rules.general.text import normalize_for_matching
            parsed["normalized_brand"] = normalize_for_matching(vendor)
            # Remove brand_not_found warning since we have vendor
            if "brand_not_found" in parsed["parse_warnings"]:
                parsed["parse_warnings"].remove("brand_not_found")

        # Price: from first variant (all beverages have exactly 1 variant)
        price = None
        discount_price = None
        variants = product.get("variants", [])
        if variants:
            variant = variants[0]
            try:
                price = float(variant.get("price", "0"))
            except (ValueError, TypeError):
                pass
            compare = variant.get("compare_at_price")
            if compare:
                try:
                    compare_float = float(compare)
                    if compare_float > 0 and price and compare_float > price:
                        discount_price = compare_float
                except (ValueError, TypeError):
                    pass

        # Image: first image src
        images = product.get("images", [])
        image = images[0].get("src") if images else None

        return self._build_result(
            parsed,
            product_id=product_id,
            marketplace=self.marketplace,
            source_type="website",
            branch=None,
            original_name=product.get("title", ""),
            canonical_category_id=canonical_category_id,
            original_category=category_title,
            price=price,
            discount_price=discount_price,
            image=image,
        )
