"""Dominante Filamentfarbe aus einem Foto schätzen."""

from __future__ import annotations

from pathlib import Path


def color_from_image_path(path: str | Path) -> str:
    """Liefert Hex RGB (6 Zeichen) aus Bilddatei."""
    from PIL import Image

    img = Image.open(path).convert("RGB")
    img.thumbnail((160, 160))

    buckets: dict[tuple[int, int, int], int] = {}
    for r, g, b in img.getdata():
        lum = (r + g + b) / 3
        if lum < 25 or lum > 245:
            continue
        # Grobe Quantisierung — ähnliche Töne zusammenfassen
        key = (r // 16 * 16 + 8, g // 16 * 16 + 8, b // 16 * 16 + 8)
        buckets[key] = buckets.get(key, 0) + 1

    if not buckets:
        for r, g, b in img.getdata():
            key = (r // 32 * 32 + 16, g // 32 * 32 + 16, b // 32 * 32 + 16)
            buckets[key] = buckets.get(key, 0) + 1

    r, g, b = max(buckets, key=buckets.get)
    return f"{r:02X}{g:02X}{b:02X}"
