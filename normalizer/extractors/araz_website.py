from normalizer.extractors.base import BaseExtractor
from normalizer.parser import parse_product_name


class ArazWebsiteExtractor(BaseExtractor):
    """Extracts normalized products from Araz website raw documents."""

    def __init__(self, marketplace, rule_loader):
        self.marketplace = marketplace
        self.rule_loader = rule_loader

    def extract(self, raw_doc, category_assigner):
        product = raw_doc.get("product", {})
        product_id = raw_doc.get("product_id", str(product.get("id", "")))

        category_title = product.get("category_title", "")
        name = product.get("title", "")

        canonical_category_id = category_assigner.assign(category_title, name)
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

        # Price: stored as string in Araz website data
        price = None
        sales_price = product.get("sales_price")
        if sales_price is not None:
            try:
                price = float(str(sales_price).replace(",", "."))
            except (ValueError, TypeError):
                pass

        discount_price = None
        if product.get("is_discount"):
            dp = product.get("discount_price")
            if dp is not None:
                try:
                    dp_float = float(str(dp).replace(",", "."))
                    if price and dp_float < price:
                        discount_price = price
                        price = dp_float
                except (ValueError, TypeError):
                    pass

        # Barcode: internal SKU (NOT GTIN)
        website_barcode = product.get("barcode")
        if website_barcode is not None:
            website_barcode = str(website_barcode).strip() or None

        # Image
        images = product.get("images") or []
        image = images[0] if images else None

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
            website_barcode=website_barcode,
        )
