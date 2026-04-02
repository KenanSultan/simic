from django import template

register = template.Library()


@register.filter
def pct(value, total):
    """Calculate percentage: {{ value|pct:total }} -> "12.3" """
    try:
        value = float(value)
        total = float(total)
        if total == 0:
            return "0"
        result = value / total * 100
        if result == 0:
            return "0"
        if result < 0.1:
            return "0.1"
        if result < 1:
            return f"{result:.1f}"
        return f"{result:.1f}".rstrip("0").rstrip(".")
    except (ValueError, TypeError, ZeroDivisionError):
        return "0"


@register.filter
def bar_width(value, total):
    """Bar width percentage, minimum 1% when value > 0: {{ value|bar_width:total }} -> "1" """
    try:
        value = float(value)
        total = float(total)
        if total == 0 or value == 0:
            return "0"
        result = value / total * 100
        return str(max(1, round(result)))
    except (ValueError, TypeError, ZeroDivisionError):
        return "0"


@register.filter
def local_or_cdn(obj):
    """Return local_image if set, else fall back to original image URL."""
    if isinstance(obj, dict):
        return obj.get("local_image") or obj.get("image") or ""
    return ""


@register.filter
def img_src(img_dict):
    """For image gallery dicts: prefer local_image over url."""
    if isinstance(img_dict, dict):
        return img_dict.get("local_image") or img_dict.get("url") or ""
    return ""


@register.filter
def bar_color(value, total):
    """Return quality bar CSS modifier based on percentage threshold."""
    try:
        value = float(value)
        total = float(total)
        if total == 0:
            return "good"
        pct = value / total * 100
        if pct > 15:
            return "danger"
        if pct > 5:
            return "warning"
        return "good"
    except (ValueError, TypeError, ZeroDivisionError):
        return "good"
