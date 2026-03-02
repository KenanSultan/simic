from django.db import models
from core.models import BaseModel


class Category(BaseModel):
    name = models.CharField(max_length=128)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
    )

    def __str__(self):
        return self.name
