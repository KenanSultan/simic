from django.db import models
from core.models import BaseModel
from market.models import Market, MarketBranch
from product.models import Product


class MarketProduct(BaseModel):
    market = models.ForeignKey(
        Market, on_delete=models.CASCADE, related_name="market_products"
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="market_products"
    )
    external_product_id = models.CharField(max_length=128)
    url = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["market", "external_product_id"],
                name="uniq_market_external_product",
            )
        ]

    def __str__(self):
        return f"{self.market.code} - {self.product.title}"


class Price(BaseModel):
    market_product = models.ForeignKey(
        MarketProduct, on_delete=models.CASCADE, related_name="prices"
    )
    market_branch = models.ForeignKey(
        MarketBranch, on_delete=models.CASCADE, related_name="prices"
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_price = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    currency = models.CharField(max_length=3, default="AZN")
    fetched_at = models.DateTimeField()

    class Meta:
        indexes = [
            models.Index(
                fields=["market_product", "market_branch", "-fetched_at"],
                name="price_lookup_idx",
            )
        ]

    def __str__(self):
        return f"{self.market_product} @ {self.price}"
