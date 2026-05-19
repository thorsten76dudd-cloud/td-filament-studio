"""Drucker-Tab: Printer.*-Styles (basiert auf globalem Dunkel-Theme)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ui import theme as T

P_BG = T.BG
P_BG_ELEVATED = T.BG_SUBTLE
P_CARD = T.CARD
P_CARD_ALT = T.SURFACE_DARK
P_BORDER = T.BORDER
P_TEXT = T.TEXT
P_MUTED = T.MUTED
P_ACCENT = T.ACCENT_DARK
P_WARN = T.WARN

P_FONT = T.FONT
P_F_TITLE = T.F_SECTION
P_F_HEAD = T.F_SECTION
P_F_BODY = T.F_BODY
P_F_SMALL = T.F_SMALL
P_F_TEMP = (P_FONT, 16, "bold")
P_F_TEMP_SUB = T.F_SMALL


def apply_printer_tab_theme(root: tk.Misc) -> None:
    T.apply_theme(root)
    style = ttk.Style(root)

    style.configure("Printer.TFrame", background=T.BG)
    style.configure("Printer.TLabel", background=T.BG, foreground=T.TEXT, font=T.F_BODY)
    style.configure("Printer.Muted.TLabel", background=T.BG, foreground=T.MUTED, font=T.F_SMALL)
    style.configure("Printer.Card.TFrame", background=T.CARD)
    style.configure("Printer.Card.TLabel", background=T.CARD, foreground=T.TEXT, font=T.F_BODY)
    style.configure("Printer.CardHeading.TLabel", background=T.CARD, foreground=T.TEXT, font=T.F_SECTION)
    style.configure("Printer.CardMuted.TLabel", background=T.CARD, foreground=T.MUTED, font=T.F_SMALL)
    style.configure("Printer.Temp.TLabel", background=T.SURFACE_DARK, foreground=T.TEXT, font=P_F_TEMP)
    style.configure("Printer.TempSub.TLabel", background=T.SURFACE_DARK, foreground=T.MUTED, font=T.F_SMALL)
    style.configure("Printer.Hint.TLabel", background=T.CARD, foreground=T.ACCENT, font=T.F_SMALL)

    style.configure("Printer.TLabelframe", background=T.CARD, bordercolor=T.BORDER, relief="solid", borderwidth=1)
    style.configure("Printer.TLabelframe.Label", background=T.CARD, foreground=T.MUTED, font=T.F_SECTION)

    style.configure(
        "Printer.TButton",
        padding=(18, 11),
        background=T.BTN_SECONDARY_BG,
        foreground=T.TEXT,
        bordercolor=T.BORDER,
        font=T.F_BODY,
        focusthickness=0,
    )
    style.map(
        "Printer.TButton",
        background=[("active", T.BTN_SECONDARY_HOVER)],
        foreground=[("!disabled", T.TEXT)],
    )

    style.configure(
        "Printer.Accent.TButton",
        background=T.ACCENT_BTN_BG,
        foreground=T.ACCENT_BTN_TEXT,
        bordercolor=T.ACCENT_BTN_BORDER,
        font=(T.FONT, 10, "bold"),
        padding=(18, 11),
        focusthickness=0,
    )
    style.map(
        "Printer.Accent.TButton",
        background=[("active", T.ACCENT_BTN_BORDER), ("pressed", T.ACCENT_DARK)],
        foreground=[("disabled", T.MUTED), ("!disabled", T.ACCENT_BTN_TEXT)],
    )

    style.configure(
        "Printer.Secondary.TButton",
        padding=(18, 11),
        background=T.BTN_SECONDARY_BG,
        foreground=T.TEXT,
        bordercolor=T.BORDER,
        focusthickness=0,
    )
    style.map(
        "Printer.Secondary.TButton",
        background=[("active", T.BTN_SECONDARY_HOVER)],
        foreground=[("!disabled", T.TEXT)],
    )

    style.configure("Printer.Stop.TButton", background="#4a3030", foreground="#fca5a5", bordercolor="#6b4040")

    style.configure("Printer.TNotebook", background=T.BG, borderwidth=0, tabmargins=(4, 4, 4, 0))
    style.configure(
        "Printer.TNotebook.Tab",
        background=T.BG_SUBTLE,
        foreground=T.MUTED,
        padding=(14, 10),
        font=T.F_BODY,
    )
    style.map(
        "Printer.TNotebook.Tab",
        background=[("selected", T.CARD)],
        foreground=[("selected", T.ACCENT)],
    )

    style.configure(
        "Printer.Accent.Horizontal.TProgressbar",
        troughcolor=T.SURFACE_DARK,
        background=T.ACCENT_DARK,
        bordercolor=T.BORDER,
        lightcolor=T.ACCENT,
        darkcolor=T.ACCENT_DARK,
        thickness=12,
    )

    try:
        style.layout("Horizontal.Printer.TScale", style.layout("Horizontal.TScale"))
    except tk.TclError:
        pass
    style.configure(
        "Horizontal.Printer.TScale",
        background=T.CARD,
        troughcolor=T.SURFACE_DARK,
        bordercolor=T.BORDER,
    )

    style.configure(
        "Printer.TSpinbox",
        fieldbackground=T.SURFACE_DARK,
        foreground=T.TEXT,
        background=T.SURFACE_DARK,
        bordercolor=T.BORDER,
        arrowcolor=T.MUTED,
    )
    style.configure("Printer.TRadiobutton", background=T.CARD, foreground=T.TEXT, font=T.F_SMALL)
    style.map("Printer.TRadiobutton", foreground=[("selected", T.ACCENT)])
    style.configure("Printer.TCheckbutton", background=T.CARD, foreground=T.TEXT, font=T.F_BODY)
    style.configure(
        "Printer.Vertical.TScrollbar",
        background=T.BORDER,
        troughcolor=T.SURFACE_DARK,
        bordercolor=T.SURFACE_DARK,
        arrowcolor=T.MUTED,
    )

    try:
        root.configure(style="Printer.TFrame")
    except tk.TclError:
        pass


def style_listbox(lb: tk.Listbox) -> None:
    lb.configure(
        bg=T.SURFACE_DARK,
        fg=T.TEXT,
        selectbackground=T.ACCENT_DARK,
        selectforeground=T.ACCENT_BTN_TEXT,
        highlightthickness=0,
        borderwidth=0,
        activestyle="none",
        font=T.F_BODY,
    )


def style_scrollbar(sb: ttk.Scrollbar) -> None:
    try:
        sb.configure(style="Printer.Vertical.TScrollbar")
    except tk.TclError:
        pass
