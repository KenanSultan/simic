import re

from normalizer.extractors.base import BaseExtractor
from normalizer.parser import parse_product_name


class NeptunWebsiteExtractor(BaseExtractor):
    """Extracts normalized products from Neptun website raw documents.

    Handles Neptun-specific ALL CAPS naming and abbreviations (S/Q, PL/Q, T/P, D/Q).
    """

    def __init__(self, marketplace, rule_loader):
        self.marketplace = marketplace
        self.rule_loader = rule_loader
        self._abbreviation_patterns = self._compile_abbreviations()

    def _compile_abbreviations(self):
        abbreviations = self.rule_loader.get_abbreviations()
        patterns = []
        for abbr in abbreviations:
            regex = re.compile(
                r"\b" + re.escape(abbr["pattern"]) + r"\b", re.IGNORECASE
            )
            patterns.append((regex, abbr["expansion"]))
        return patterns

    def _to_title_case(self, name):
        """Convert ALL CAPS to title case, handling hyphens and numbers."""
        parts = name.split()
        result = []
        for part in parts:
            if "-" in part:
                # Handle hyphenated words: COCA-COLA -> Coca-Cola
                subparts = part.split("-")
                result.append("-".join(s.capitalize() for s in subparts))
            else:
                result.append(part.capitalize())
        return " ".join(result)

    def _preprocess_name(self, name):
        """Title case + abbreviation expansion before parsing."""
        name = self._to_title_case(name)
        for pattern, expansion in self._abbreviation_patterns:
            name = pattern.sub(expansion, name)
        return name

    def extract(self, raw_doc, category_assigner):
        product = raw_doc.get("product", {})
        product_id = raw_doc.get("product_id", str(product.get("product_id", "")))

        meta = product.get("_meta", {})
        category_title = meta.get("category_title", "")
        name = product.get("name", "")

        canonical_category_id = category_assigner.assign(category_title, name)
        if canonical_category_id is None:
            return None

        if not name:
            return None

        # Pre-process: title case + abbreviation expansion
        processed_name = self._preprocess_name(name)

        parsed = parse_product_name(processed_name, self.rule_loader)

        # Apply category-specific inference rules (may correct category)
        inference_fn = self.rule_loader.get_inference_fn()
        if inference_fn:
            inference_fn(parsed, canonical_category_id, original_name=name)
            if parsed.get("_skip"):
                return None
            if "_corrected_category_id" in parsed:
                canonical_category_id = parsed.pop("_corrected_category_id")

        # Price: stored as float in Neptun website data (already AZN)
        price = product.get("price")
        discount_price = None
        old_price = product.get("old_price")
        if old_price is not None and price is not None:
            if old_price > price:
                discount_price = old_price

        # Image: single URL string
        image = product.get("image")

        return self._build_result(
            parsed,
            product_id=product_id,
            marketplace=self.marketplace,
            source_type="website",
            branch=None,
            original_name=name,
            canonical_category_id=canonical_category_id,
            original_category=category_title,
            price=price,
            discount_price=discount_price,
            image=image,
        )
