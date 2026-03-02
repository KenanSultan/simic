from django.db import models
from core.models import BaseModel


class Market(BaseModel):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=128)
    website = models.URLField(blank=True, null=True)
    logo = models.URLField(blank=True, null=True)

    def __str__(self):
        return self.name


class MarketBranch(BaseModel):
    market = models.ForeignKey(
        Market, on_delete=models.CASCADE, related_name="branches"
    )
    code = models.CharField(max_length=64, blank=True, null=True)
    name = models.CharField(max_length=128)
    address = models.TextField()
    city = models.CharField(max_length=64)
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, blank=True, null=True
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, blank=True, null=True
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["market", "code"],
                condition=models.Q(code__isnull=False),
                name="uniq_market_branch_code",
            )
        ]

    def __str__(self):
        return f"{self.market.code} - {self.name}"
