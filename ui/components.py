"""Gemeinsame UI-Bausteine."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from ui.rounded_widgets import rounded_button, style_to_variant
from ui.theme import BG, BORDER, CARD, MUTED, TEXT_SECONDARY
from ui.tooltip import tip


def section(parent: tk.Misc, title: str) -> ttk.LabelFrame:
    return ttk.LabelFrame(parent, text=f"  {title}  ", padding=8)


def labeled_row(
    parent: tk.Misc,
    label: str,
    widget: tk.Misc,
    *,
    label_width: int = 18,
) -> ttk.Frame:
    row = ttk.Frame(parent)
    ttk.Label(row, text=label, style="Muted.TLabel", width=label_width).pack(side="left")
    widget.pack(in_=row, side="left", fill="x", expand=True, padx=8)
    return row


def scrollable_tab(parent: tk.Misc) -> tuple[tk.Canvas, ttk.Frame]:
    canvas = tk.Canvas(parent, bg=BG, highlightthickness=0, borderwidth=0)
    scroll = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
    inner = ttk.Frame(canvas)
    inner.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
    )
    win = canvas.create_window((0, 0), window=inner, anchor="nw")
    canvas.configure(yscrollcommand=scroll.set)

    def _on_canvas_configure(event) -> None:
        canvas.itemconfig(win, width=event.width)

    canvas.bind("<Configure>", _on_canvas_configure)
    canvas.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")

    def _wheel(event) -> None:
        if canvas.winfo_containing(event.x_root, event.y_root) is not None:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _bind_wheel(_event=None) -> None:
        canvas.bind("<MouseWheel>", _wheel)

    def _unbind_wheel(_event=None) -> None:
        canvas.unbind("<MouseWheel>")

    canvas.bind("<Enter>", _bind_wheel)
    canvas.bind("<Leave>", _unbind_wheel)
    return canvas, inner


def button_grid(
    parent: tk.Misc,
    items: list[tuple[str, Callable[[], None], str, str | None]],
    *,
    columns: int = 3,
    pad: int = 6,
    rounded: bool = True,
) -> tk.Frame | ttk.Frame:
    """
    Buttons in einem Raster (kein Abschneiden bei schmalem Fenster).
    items: (text, command, style, tooltip)
    """
    try:
        bg = parent.cget("bg")
    except tk.TclError:
        bg = BG
    frame = tk.Frame(parent, bg=bg)
    for i, (text, cmd, btn_style, help_txt) in enumerate(items):
        r, c = divmod(i, columns)
        if rounded:
            variant = style_to_variant(btn_style)
            font = ("Segoe UI", 10, "bold") if variant == "accent" else ("Segoe UI", 10)
            b = rounded_button(frame, text, cmd, variant=variant, font=font)
            sticky = "w"
        else:
            b = ttk.Button(frame, text=text, command=cmd, style=btn_style)
            sticky = "ew"
        b.grid(row=r, column=c, sticky=sticky, padx=pad, pady=pad)
        if help_txt:
            tip(b, help_txt)
    if not rounded:
        for c in range(columns):
            frame.columnconfigure(c, weight=1)
    return frame
