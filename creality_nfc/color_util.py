"""Creality-Farbcodes (7-stellig / Hex) für die UI."""

from __future__ import annotations


def creality_color_to_hex(color: str | None) -> str | None:
    """0RRGGBB, RRGGBB oder #RRGGBB → #RRGGBB für Tk/HTML."""
    if not color:
        return None
    raw = str(color).strip().lstrip("#").upper()
    digits = "".join(ch for ch in raw if ch in "0123456789ABCDEF")
    if len(digits) < 6:
        return None
    rgb = digits[-6:]
    try:
        int(rgb, 16)
    except ValueError:
        return None
    return f"#{rgb}"
