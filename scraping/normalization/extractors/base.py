from abc import ABC, abstractmethod


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
