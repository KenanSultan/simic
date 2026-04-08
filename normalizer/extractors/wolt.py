from normalizer.extractors.base import BaseExtractor
from normalizer.parser import parse_product_name


class WoltExtractor(BaseExtractor):
    """Extracts normalized products from Wolt branch raw documents.

    Shared across all Wolt-sourced marketplaces (Araz, Bravo, Neptun).
    """

    def __init__(self, marketplace, rule_loader):
        self.marketplace = marketplace
        self.rule_loader = rule_loader

    def extract(self, raw_doc, category_assigner):
        product = raw_doc.get("product", {})
        branch = raw_doc.get("branch", "")
        product_id = raw_doc.get("product_id", "")

        original_category = product.get("category", "")
        name = product.get("name", "")

        canonical_category_id = category_assigner.assign(original_category, name)
        if canonical_category_id is None:
            return None

        if not name:
            return None

        parsed = parse_product_name(name, self.rule_loader)

        # Apply category-specific inference rules (may correct category)
        inference_fn = self.rule_loader.get_inference_fn()
        if inference_fn:
            inference_fn(parsed, canonical_category_id, original_name=name)
            if parsed.get("_skip"):
                return None
            if "_corrected_category_id" in parsed:
                canonical_category_id = parsed.pop("_corrected_category_id")

        # Price: Wolt stores in cents, convert to AZN
        price_cents = product.get("price")
        price = price_cents / 100.0 if price_cents is not None else None

        original_price_cents = product.get("original_price")
        discount_price = None
        if original_price_cents is not None and price_cents is not None:
            if original_price_cents > price_cents:
                discount_price = original_price_cents / 100.0

        # Barcode
        barcode = product.get("barcode_gtin")
        if barcode is not None:
            barcode = str(barcode).strip()
            if not barcode:
                barcode = None

        # Image
        images = product.get("images") or []
        image = images[0].get("url", "") if images else None

        return self._build_result(
            parsed,
            product_id=product_id,
            marketplace=self.marketplace,
            source_type="wolt",
            branch=branch,
            original_name=name,
            canonical_category_id=canonical_category_id,
            original_category=original_category,
            barcode=barcode,
            price=price,
            discount_price=discount_price,
            image=image,
        )
