import hashlib
import logging
from pathlib import Path
from urllib.parse import urlparse

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

CONTENT_TYPE_TO_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

_session = None


def _get_session():
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
        })
    return _session


def _detect_extension(url, content_type=None):
    """Detect file extension from URL path, then Content-Type, default .jpg."""
    path = urlparse(url).path
    suffix = Path(path).suffix.lower().split("?")[0]
    if suffix in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        return ".jpg" if suffix == ".jpeg" else suffix

    if content_type:
        ct = content_type.split(";")[0].strip().lower()
        if ct in CONTENT_TYPE_TO_EXT:
            return CONTENT_TYPE_TO_EXT[ct]

    return ".jpg"


def download_product_image(image_url, market):
    """Download image and return local media URL path, or None on failure.

    Saves to media/products/{market}/{md5_of_url}.{ext}.
    Skips download if file already exists on disk (idempotent).
    Returns path like "/media/products/araz/a1b2c3.jpg".
    """
    if not image_url:
        return None

    url_hash = hashlib.md5(image_url.encode()).hexdigest()

    # Check if already downloaded (any extension)
    media_dir = Path(settings.MEDIA_ROOT) / "products" / market
    existing = list(media_dir.glob(f"{url_hash}.*")) if media_dir.exists() else []
    if existing:
        return f"{settings.MEDIA_URL}products/{market}/{existing[0].name}"

    # Download
    try:
        session = _get_session()
        resp = session.get(image_url, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning("Failed to download %s: %s", image_url, e)
        return None

    if not resp.content:
        logger.warning("Empty response for %s", image_url)
        return None

    ext = _detect_extension(image_url, resp.headers.get("Content-Type"))
    filename = f"{url_hash}{ext}"

    media_dir.mkdir(parents=True, exist_ok=True)
    filepath = media_dir / filename
    filepath.write_bytes(resp.content)

    return f"{settings.MEDIA_URL}products/{market}/{filename}"
