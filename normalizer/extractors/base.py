from abc import ABC, abstractmethod
from datetime import datetime, timezone


class BaseExtractor(ABC):
    """Abstract base for marketplace-specific product extractors."""

    @abstractmethod
    def extract(self, raw_product, category_mapping):
        """Extract normalized product from raw product document.

        Args:
            raw_product: The raw MongoDB document.
            category_mapping: Dict of {marketplace_category: canonical_category_id}.

        Returns:
            Dict with normalized product fields, or None if product should be skipped.
        """
        ...

    @staticmethod
    def _build_result(parsed, *, product_id, marketplace, source_type, branch,
                      original_name, canonical_category_id, original_category,
                      barcode=None, price=None, discount_price=None,
                      currency="AZN", image=None, **extra):
        """Build normalized product dict from parsed fields + source-specific fields.

        Copies all parser output fields (brand, size, flavor, etc.) automatically.
        Source-specific fields (price, barcode, image) passed as keyword args.
        Any additional fields can be passed via **extra (e.g., website_barcode).
        """
        result = {
            "product_id": product_id,
            "marketplace": marketplace,
            "source_type": source_type,
            "branch": branch,
            "original_name": original_name,
            "canonical_category_id": canonical_category_id,
            "original_category": original_category,
            "barcode": barcode,
            "price": price,
            "discount_price": discount_price,
            "currency": currency,
            "image": image,
            "normalized_at": datetime.now(timezone.utc),
        }
        # Copy all parsed fields (brand, size, flavor, packaging, etc.)
        _SKIP = {"parse_warnings"}
        for key, value in parsed.items():
            if key not in _SKIP and key not in result:
                result[key] = value
        result["parse_warnings"] = parsed.get("parse_warnings", [])
        if extra:
            result.update(extra)
        return result
