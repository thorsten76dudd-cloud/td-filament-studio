"""Kleine Farbfelder für Treeview und Formulare."""

from __future__ import annotations

import tkinter as tk


def normalize_hex(color: str) -> str:
    """6-stelliges RRGGBB für Tk/PIL (nie #eff o. Ä.)."""
    h = str(color or "").strip().lstrip("#").upper()
    h = "".join(c for c in h if c in "0123456789ABCDEF")
    if len(h) >= 6:
        return h[-6:]
    if len(h) == 3:
        return "".join(ch * 2 for ch in h)
    if 0 < len(h) < 6:
        return h.rjust(6, "0")
    return "FFFFFF"


def color_from_tag_field(raw: str) -> str:
    """Creality-Tag-Farbfeld (7 Zeichen) → RRGGBB (nicht .lstrip('0') — erzeugt sonst „eff“)."""
    digits = "".join(
        c for c in str(raw or "").strip().lstrip("#").upper() if c in "0123456789ABCDEF"
    )
    if len(digits) >= 6:
        return digits[-6:]
    if digits:
        return digits.rjust(6, "0")
    return "FFFFFF"


def make_swatch_photo(
    master: tk.Misc,
    color: str,
    *,
    size: tuple[int, int] = (26, 18),
    cache: dict[str, tk.PhotoImage] | None = None,
) -> tk.PhotoImage:
    """Farbfeld als PhotoImage (Referenz in cache halten!)."""
    key = normalize_hex(color)
    if cache is not None and key in cache:
        return cache[key]

    w, h = size
    try:
        from PIL import Image, ImageDraw, ImageTk

        r = int(key[0:2], 16)
        g = int(key[2:4], 16)
        b = int(key[4:6], 16)
        img = Image.new("RGB", (w, h), "#ffffff")
        draw = ImageDraw.Draw(img)
        draw.rectangle((1, 1, w - 2, h - 2), fill=(r, g, b), outline="#5a6069", width=1)
        photo = ImageTk.PhotoImage(img, master=master)
    except Exception:
        photo = tk.PhotoImage(width=w, height=h, master=master)
        try:
            photo.put(f"#{key}", to=(1, 1, w - 2, h - 2))
        except tk.TclError:
            pass

    if cache is not None:
        cache[key] = photo
    return photo


def apply_preview_label(label: tk.Label, color: str) -> None:
    """Tk-Label als Farbvorschau (Hintergrund = Farbe)."""
    key = normalize_hex(color)
    label.config(bg=f"#{key}", text="")
