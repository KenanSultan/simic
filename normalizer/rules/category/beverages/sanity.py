"""Beverage-specific sanity checks. Applies to category: Spirtsiz içkilər."""

# Max reasonable volume for a single beverage product
MAX_BEVERAGE_ML = 30000  # 30 liters


def sanity_check_size(size_val, unit):
    """If volume exceeds 30L, the unit was likely wrong (L used instead of ml)."""
    if unit == "ml" and size_val > MAX_BEVERAGE_ML:
        return size_val / 1000, unit
    return size_val, unit
