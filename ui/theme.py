"""TD Filament Studio — modern UI theme (ttk + tk)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

# —— Dunkles UI (Creality-Print-Nähe), grüner Akzent, gut lesbare Buttons ——
BG = "#1a1c22"
BG_SUBTLE = "#23252b"
CARD = "#2d3039"
HEADER = "#12151a"
HEADER_SURFACE = "#1e2229"
SURFACE_DARK = "#353944"

ACCENT = "#4ade9a"
ACCENT_DARK = "#22c55e"
ACCENT_LIGHT = "#6ee7b7"
ACCENT_SOFT = "#1a3d2e"
ACCENT_TD = "#86efac"
# Primär-Buttons: weiße Schrift auf sattem Grün
ACCENT_BTN_BG = "#2a9d6a"
ACCENT_BTN_TEXT = "#ffffff"
ACCENT_BTN_BORDER = "#34b87a"
BTN_SECONDARY_BG = "#4a5260"
BTN_SECONDARY_HOVER = "#5a6370"

TEXT = "#e8eaed"
TEXT_SECONDARY = "#c4c8ce"
MUTED = "#9aa0a6"
BORDER = "#454a54"
BORDER_STRONG = "#5a6069"
INPUT_FOCUS = ACCENT

OK = "#4ade9a"
WARN = "#f5a623"
ERR = "#f87171"

ON_HEADER = "#f1f5f9"
ON_HEADER_SUB = "#cbd5e1"
ON_HEADER_MUTED = "#94a3b8"
ON_HEADER_OK = "#6ee7b7"
ON_HEADER_WARN = "#fcd34d"
ON_HEADER_ERR = "#fca5a5"

MSG_BG = "#1a1f2e"
CONFIRM_BG = "#252b3b"
LOG_BG = "#0d1117"
LOG_FG = "#d1d5db"

FONT = "Segoe UI"
F_TITLE = (FONT, 22, "bold")
F_HEADER_SUB = (FONT, 11)
F_HEAD = (FONT, 12, "bold")
F_SECTION = (FONT, 11, "bold")
F_BODY = (FONT, 11)
F_SMALL = (FONT, 10)
F_BADGE = (FONT, 10, "bold")
F_MONO = ("Consolas", 10)


def _safe_bg(widget: tk.Misc, color: str = BG) -> None:
    try:
        widget.configure(bg=color)
    except tk.TclError:
        pass


def apply_theme(root: tk.Misc) -> None:
    top = root.winfo_toplevel()
    _safe_bg(top)
    if root is not top:
        _safe_bg(root)

    try:
        top.option_add("*Font", F_BODY)
    except tk.TclError:
        pass

    style = ttk.Style(top)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(".", background=BG, foreground=TEXT, font=F_BODY)
    style.configure("TFrame", background=BG)
    style.configure("Card.TFrame", background=CARD)

    style.configure("TLabel", background=BG, foreground=TEXT, font=F_BODY)
    style.configure("Card.TLabel", background=CARD, foreground=TEXT)
    style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=F_SMALL)
    style.configure("CardMuted.TLabel", background=CARD, foreground=MUTED, font=F_SMALL)
    style.configure("Heading.TLabel", background=BG, foreground=TEXT, font=F_HEAD)
    style.configure("CardHeading.TLabel", background=CARD, foreground=TEXT, font=F_HEAD)

    style.configure(
        "TLabelframe",
        background=CARD,
        bordercolor=BORDER,
        relief="flat",
        borderwidth=1,
    )
    style.configure(
        "TLabelframe.Label",
        background=CARD,
        foreground=TEXT_SECONDARY,
        font=F_SECTION,
    )
    style.configure("Card.TLabelframe", background=CARD, bordercolor=BORDER)
    style.configure("Card.TLabelframe.Label", background=CARD, font=F_SECTION, foreground=TEXT)

    style.configure(
        "TButton",
        padding=(18, 11),
        font=F_BODY,
        background=BTN_SECONDARY_BG,
        foreground=TEXT,
        bordercolor=BORDER,
        focusthickness=0,
        focuscolor=ACCENT_SOFT,
    )
    style.map(
        "TButton",
        background=[("active", BTN_SECONDARY_HOVER), ("pressed", BORDER_STRONG)],
        bordercolor=[("active", BORDER_STRONG), ("focus", ACCENT)],
        foreground=[("disabled", MUTED), ("!disabled", TEXT)],
    )

    style.configure(
        "Accent.TButton",
        background=ACCENT_BTN_BG,
        foreground=ACCENT_BTN_TEXT,
        padding=(18, 11),
        font=(FONT, 11, "bold"),
        bordercolor=ACCENT_BTN_BORDER,
        focusthickness=0,
    )
    style.map(
        "Accent.TButton",
        background=[("active", ACCENT_LIGHT), ("pressed", ACCENT_DARK)],
        foreground=[("disabled", MUTED)],
        bordercolor=[("active", ACCENT_DARK)],
    )

    style.configure(
        "Secondary.TButton",
        padding=(18, 11),
        background=BTN_SECONDARY_BG,
        foreground=TEXT,
        bordercolor=BORDER,
        font=F_BODY,
        focusthickness=0,
    )
    style.map(
        "Secondary.TButton",
        background=[("active", BTN_SECONDARY_HOVER), ("pressed", BORDER_STRONG)],
        foreground=[("disabled", MUTED), ("!disabled", TEXT)],
        bordercolor=[("focus", ACCENT)],
    )

    style.configure(
        "Ghost.TButton",
        padding=(14, 8),
        font=F_SMALL,
        background=HEADER_SURFACE,
        foreground=ON_HEADER,
        bordercolor=HEADER_SURFACE,
    )
    style.map(
        "Ghost.TButton",
        background=[("active", "#252f3d"), ("pressed", "#2f3b4d")],
        foreground=[("disabled", ON_HEADER_MUTED)],
    )

    style.configure(
        "GhostMuted.TButton",
        padding=(12, 8),
        font=F_SMALL,
        background="#252f3d",
        foreground=ON_HEADER_MUTED,
        bordercolor="#252f3d",
    )
    style.map(
        "GhostMuted.TButton",
        background=[("active", "#2f3b4d")],
        foreground=[("active", ON_HEADER)],
    )

    style.configure(
        "FooterGhost.TButton",
        padding=(12, 8),
        font=F_SMALL,
        background=BTN_SECONDARY_BG,
        foreground=TEXT,
        bordercolor=BORDER,
        focusthickness=0,
    )
    style.map(
        "FooterGhost.TButton",
        background=[("active", BTN_SECONDARY_HOVER), ("pressed", BORDER_STRONG)],
        foreground=[("disabled", MUTED), ("!disabled", TEXT)],
        bordercolor=[("active", BORDER_STRONG)],
    )

    style.configure(
        "TNotebook",
        background=BG,
        borderwidth=0,
        tabmargins=(10, 8, 10, 0),
    )
    style.configure(
        "TNotebook.Tab",
        padding=(22, 14),
        font=(FONT, 11),
        background=BG_SUBTLE,
        foreground=MUTED,
        borderwidth=0,
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", CARD), ("active", BG_SUBTLE)],
        foreground=[("selected", ACCENT), ("active", TEXT)],
        expand=[("selected", [1, 1, 1, 0])],
    )

    style.configure(
        "TCombobox",
        padding=(10, 8),
        fieldbackground=CARD,
        background=CARD,
        arrowcolor=TEXT_SECONDARY,
        bordercolor=BORDER_STRONG,
        foreground=TEXT,
    )
    style.map(
        "TCombobox",
        fieldbackground=[
            ("readonly", CARD),
            ("disabled", BG_SUBTLE),
            ("!disabled", CARD),
        ],
        foreground=[("readonly", TEXT), ("disabled", MUTED)],
        background=[("readonly", CARD), ("!disabled", CARD)],
        bordercolor=[("focus", INPUT_FOCUS), ("active", BORDER_STRONG)],
    )

    style.configure(
        "TEntry",
        padding=(10, 8),
        fieldbackground=CARD,
        bordercolor=BORDER_STRONG,
        foreground=TEXT,
        insertcolor=ACCENT_DARK,
    )
    style.map(
        "TEntry",
        bordercolor=[("focus", INPUT_FOCUS), ("active", BORDER_STRONG)],
        fieldbackground=[("disabled", BG_SUBTLE), ("!disabled", CARD)],
        foreground=[("disabled", MUTED)],
    )

    style.configure(
        "TSpinbox",
        padding=(8, 6),
        fieldbackground=CARD,
        bordercolor=BORDER_STRONG,
        arrowcolor=TEXT_SECONDARY,
    )
    style.map("TSpinbox", bordercolor=[("focus", INPUT_FOCUS)])

    style.configure("TCheckbutton", background=BG, foreground=TEXT, font=F_BODY)
    style.configure("Card.TCheckbutton", background=CARD, foreground=TEXT, font=F_BODY)
    style.configure("TRadiobutton", background=BG, foreground=TEXT, font=F_BODY)
    style.map("TRadiobutton", background=[("active", BG)])

    style.configure("TPanedwindow", background=BG)
    style.configure("Sash", sashthickness=6, background=BORDER_STRONG)

    style.configure(
        "Vertical.TScrollbar",
        background=BORDER,
        troughcolor=BG_SUBTLE,
        bordercolor=BG_SUBTLE,
        arrowcolor=MUTED,
        width=12,
    )
    style.map("Vertical.TScrollbar", background=[("active", BORDER_STRONG)])

    style.configure("TSeparator", background=BORDER)

    style.configure(
        "Treeview",
        background=CARD,
        fieldbackground=CARD,
        foreground=TEXT,
        rowheight=32,
        bordercolor=BORDER,
        relief="flat",
        font=F_BODY,
    )
    style.configure(
        "Treeview.Heading",
        font=F_SECTION,
        background=BG_SUBTLE,
        foreground=TEXT,
        relief="flat",
        borderwidth=1,
    )
    style.map(
        "Treeview",
        background=[("selected", "#2a4a3c"), ("!selected", CARD)],
        foreground=[("selected", TEXT), ("!selected", TEXT)],
    )

    # Spulen-Liste: keine blaue System-Auswahl, klare Zeilen
    style.configure(
        "Spool.Treeview",
        background=CARD,
        fieldbackground=CARD,
        foreground=TEXT,
        rowheight=34,
        font=F_BODY,
        bordercolor=BORDER,
    )
    style.configure(
        "Spool.Treeview.Heading",
        background=BG_SUBTLE,
        foreground=TEXT,
        relief="flat",
        borderwidth=1,
    )
    style.map(
        "Spool.Treeview",
        background=[("selected", "#2a4a3c")],
        foreground=[("selected", TEXT)],
    )

    style.configure(
        "Horizontal.TScale",
        background=CARD,
        troughcolor=BG_SUBTLE,
        bordercolor=CARD,
    )

    style.configure(
        "Accent.Horizontal.TProgressbar",
        troughcolor=SURFACE_DARK,
        background=ACCENT_DARK,
        bordercolor=BORDER,
        lightcolor=ACCENT,
        darkcolor=ACCENT_DARK,
        thickness=12,
    )

    style.configure("Status.TFrame", background=HEADER)
    style.configure("Status.TLabel", background=HEADER, foreground=ON_HEADER, font=F_SMALL)
    style.configure("StatusOk.TLabel", background=HEADER, foreground=ON_HEADER_OK, font=F_SMALL)
    style.configure("StatusWarn.TLabel", background=HEADER, foreground=ON_HEADER_WARN, font=F_SMALL)
    style.configure("StatusErr.TLabel", background=HEADER, foreground=ON_HEADER_ERR, font=F_SMALL)

    style.configure("Footer.TFrame", background=BG_SUBTLE)
    style.configure("Footer.TLabel", background=BG_SUBTLE, foreground=TEXT_SECONDARY, font=F_SMALL)
    style.configure("FooterOk.TLabel", background=BG_SUBTLE, foreground=OK, font=F_SMALL)
    style.configure("FooterWarn.TLabel", background=BG_SUBTLE, foreground=WARN, font=F_SMALL)
    style.configure("FooterErr.TLabel", background=BG_SUBTLE, foreground=ERR, font=F_SMALL)

    style.configure("Header.TFrame", background=HEADER)
    style.configure("HeaderTitle.TLabel", background=HEADER, foreground="#ffffff", font=F_TITLE)
    style.configure("HeaderSub.TLabel", background=HEADER, foreground=ON_HEADER_SUB, font=F_HEADER_SUB)
    style.configure(
        "HeaderBadge.TLabel",
        background=ACCENT_SOFT,
        foreground=ACCENT_DARK,
        font=F_BADGE,
    )

    style.configure("Msg.TFrame", background=MSG_BG)
    style.configure("Msg.TLabel", background=MSG_BG, foreground=LOG_FG, font=F_SMALL)
    style.configure("Confirm.TFrame", background=CONFIRM_BG)
    style.configure("Confirm.TLabel", background=CONFIRM_BG, foreground=ON_HEADER, font=F_BODY)


def apply_text_area_style(widget: tk.Text, *, bg: str = CARD) -> None:
    """Tk-Text/ScrolledText an dunkles Theme anbinden (Standard ist weiß)."""
    widget.configure(
        bg=bg,
        fg=TEXT,
        insertbackground=TEXT,
        selectbackground=SURFACE_DARK,
        selectforeground=TEXT,
        relief="flat",
        highlightthickness=1,
        highlightbackground=BORDER,
        highlightcolor=BORDER,
        borderwidth=0,
    )
    try:
        widget.configure(disabledforeground=MUTED, disabledbackground=bg)
    except tk.TclError:
        pass
    vbar = getattr(widget, "vbar", None)
    if vbar is not None:
        try:
            vbar.configure(
                bg=BG_SUBTLE,
                troughcolor=bg,
                activebackground=SURFACE_DARK,
                highlightthickness=0,
                borderwidth=0,
            )
        except tk.TclError:
            pass
