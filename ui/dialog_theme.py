"""Apply SpoolTag theme to dialog windows."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

from ui.rounded_widgets import rounded_button
from ui.theme import BG, apply_theme


def theme_dialog(win: tk.Misc) -> None:
    """ttk-Panels und Toplevels: Styles vom Hauptfenster übernehmen."""
    apply_theme(win)


def center_toplevel(win: tk.Toplevel, *, width: int | None = None, height: int | None = None) -> None:
    """Dialog mittig auf dem Bildschirm positionieren."""
    win.update_idletasks()
    w = width or win.winfo_width() or win.winfo_reqwidth()
    h = height or win.winfo_height() or win.winfo_reqheight()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    x = max(0, (sw - w) // 2)
    y = max(0, (sh - h) // 2)
    win.geometry(f"{w}x{h}+{x}+{y}")


def prepare_toplevel(
    win: tk.Toplevel,
    parent: tk.Misc | None = None,
    *,
    width: int | None = None,
    height: int | None = None,
    modal: bool = True,
) -> None:
    """Theme + optional modal + zentriert auf dem Monitor."""
    theme_dialog(win)
    if parent is not None:
        win.transient(parent)
    if modal:
        try:
            win.grab_set()
        except tk.TclError:
            pass
    win.after_idle(lambda: center_toplevel(win, width=width, height=height))


def add_dialog_footer(
    dlg: tk.Toplevel,
    *,
    on_ok: Callable[[], None],
    on_cancel: Callable[[], None] | None = None,
    ok_text: str = "OK",
    cancel_text: str = "Abbrechen",
) -> tk.Frame:
    """Lesbare OK/Abbrechen-Buttons (tk, kompakt) — Footer zuerst packen."""
    cancel = on_cancel or dlg.destroy
    footer = tk.Frame(dlg, bg=BG)
    footer.pack(side="bottom", fill="x", padx=14, pady=12)
    rounded_button(footer, cancel_text, cancel, variant="secondary", compact=True).pack(
        side="right", padx=(8, 0)
    )
    rounded_button(footer, ok_text, on_ok, variant="accent", compact=True).pack(side="right")
    return footer
