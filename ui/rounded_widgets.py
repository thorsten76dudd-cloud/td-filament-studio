"""Weiche Buttons & Karten (tk, gut lesbar auf dunklem Hintergrund)."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from ui.theme import (
    ACCENT_DARK,
    ACCENT_LIGHT,
    BG,
    BORDER,
    CARD,
    F_BODY,
    F_SECTION,
    MUTED,
    SURFACE_DARK,
    TEXT,
)

# Kontrastreiche Button-Farben (helle Schrift auf dunklem Grund)
BTN_SECONDARY_BG = "#4a5260"
BTN_SECONDARY_HOVER = "#5a6370"
BTN_SECONDARY_FG = "#f3f4f6"

BTN_ACCENT_BG = "#2a9d6a"
BTN_ACCENT_HOVER = "#34b87a"
BTN_ACCENT_FG = "#ffffff"

BTN_DANGER_BG = "#6b3a3a"
BTN_DANGER_HOVER = "#7d4545"
BTN_DANGER_FG = "#fecaca"

RADIUS_PAD = (18, 11)  # großzügiges Padding = weichere Optik


def _variant_colors(variant: str) -> dict[str, str]:
    if variant == "accent":
        return {
            "bg": BTN_ACCENT_BG,
            "fg": BTN_ACCENT_FG,
            "activebackground": BTN_ACCENT_HOVER,
            "activeforeground": BTN_ACCENT_FG,
        }
    if variant == "danger":
        return {
            "bg": BTN_DANGER_BG,
            "fg": BTN_DANGER_FG,
            "activebackground": BTN_DANGER_HOVER,
            "activeforeground": "#ffffff",
        }
    return {
        "bg": BTN_SECONDARY_BG,
        "fg": BTN_SECONDARY_FG,
        "activebackground": BTN_SECONDARY_HOVER,
        "activeforeground": "#ffffff",
    }


def style_to_variant(style: str) -> str:
    if "Stop" in style:
        return "danger"
    if "Accent" in style and "Progress" not in style:
        return "accent"
    return "secondary"


def rounded_button(
    parent: tk.Misc,
    text: str,
    command: Callable[[], None] | None = None,
    *,
    variant: str = "secondary",
    font: tuple = F_BODY,
    width: int | None = None,
    compact: bool = False,
) -> tk.Button:
    """Flacher tk-Button mit hohem Kontrast (Windows: weicher als eckiges ttk)."""
    colors = _variant_colors(variant)
    pad = (12, 8) if compact else RADIUS_PAD
    try:
        parent_bg = str(parent.cget("bg"))
    except tk.TclError:
        parent_bg = BG
    kw: dict = {
        "text": text,
        "command": command,
        "font": font,
        "relief": "flat",
        "bd": 0,
        "highlightthickness": 0,
        "highlightbackground": parent_bg,
        "highlightcolor": parent_bg,
        "cursor": "hand2",
        "padx": pad[0],
        "pady": pad[1],
        **colors,
    }
    if width is not None:
        kw["width"] = width
    btn = tk.Button(parent, **kw)
    try:
        btn.configure(disabledforeground="#8b939e")
    except tk.TclError:
        pass
    return btn


def rounded_card(parent: tk.Misc, title: str | None = None, *, pad: int = 12) -> tk.Frame:
    """Karten-Container mit Titel (ohne eckigen ttk-Rahmen)."""
    wrap = tk.Frame(parent, bg=BG)
    if title:
        tk.Label(
            wrap,
            text=title,
            bg=BG,
            fg=MUTED,
            font=F_SECTION,
            anchor="w",
        ).pack(fill="x", padx=4, pady=(0, 6))
    card = tk.Frame(wrap, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
    card.pack(fill="both", expand=True)
    inner = tk.Frame(card, bg=CARD, padx=pad, pady=pad)
    inner.pack(fill="both", expand=True)
    return inner


def rounded_notebook_tab_padding() -> dict:
    return {"padding": (18, 12)}
