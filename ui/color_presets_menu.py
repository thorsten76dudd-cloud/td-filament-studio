"""Popup-Menü mit Farbvoreinstellungen."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from creality_nfc.color_presets import COLOR_PRESETS


def show_color_presets(parent: tk.Misc, anchor_widget: tk.Widget, on_pick: Callable[[str], None]) -> None:
    menu = tk.Menu(parent, tearoff=0)
    for name, hex_code in COLOR_PRESETS:
        menu.add_command(
            label=f"  {name}  (#{hex_code})",
            command=lambda h=hex_code: on_pick(h),
        )
    try:
        x = anchor_widget.winfo_rootx()
        y = anchor_widget.winfo_rooty() + anchor_widget.winfo_height()
        menu.tk_popup(x, y)
    finally:
        menu.grab_release()
