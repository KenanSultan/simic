from django.db import models
from core.models import BaseModel
from catalog.models import Category


class Product(BaseModel):
    barcode = models.CharField(max_length=32, unique=True)
    title = models.CharField(max_length=255)
    brand = models.CharField(max_length=128, blank=True, null=True)
    size = models.CharField(max_length=64, blank=True, null=True)
    unit = models.CharField(max_length=16, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    image = models.URLField(blank=True, null=True)

    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, related_name="products"
    )

    product_type = models.CharField(max_length=32)
    packaging_material = models.CharField(max_length=32)

    def __str__(self):
        return self.title
