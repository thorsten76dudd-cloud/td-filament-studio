"""Windows-DPI / Skalierung für Padding und Mindestgrößen."""

from __future__ import annotations

import tkinter as tk


def ui_scale(widget: tk.Misc | None = None) -> float:
    """1.0 = 96 DPI; 1.25 / 1.5 bei Windows-Skalierung."""
    try:
        w = widget or tk._default_root
        if w is None:
            return 1.0
        return max(1.0, float(w.winfo_fpixels("1i")) / 96.0)
    except (tk.TclError, AttributeError, TypeError, ValueError):
        return 1.0


def scale_px(base: int, widget: tk.Misc | None = None) -> int:
    return max(base, int(round(base * ui_scale(widget))))
