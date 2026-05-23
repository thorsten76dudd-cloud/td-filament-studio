"""Apply SpoolTag theme to dialog windows."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from ui.app_icon import apply_window_icon
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
    geometry_key: str | None = None,
    min_width: int = 0,
    min_height: int = 0,
    modal: bool = True,
    remember_geometry: bool = True,
) -> None:
    """Theme + optional modal + gespeicherte oder zentrierte Geometrie."""
    from ui.window_geometry import get_window_geometry_manager

    theme_dialog(win)
    apply_window_icon(win)
    win.configure(bg=BG)
    if parent is not None:
        win.transient(parent)
    if modal:
        try:
            win.grab_set()
        except tk.TclError:
            pass
    mgr = get_window_geometry_manager()
    dw = width or 480
    dh = height or 360
    if remember_geometry and mgr and geometry_key:
        mgr.attach_toplevel(
            win,
            geometry_key,
            default_width=dw,
            default_height=dh,
            min_width=min_width,
            min_height=min_height,
        )
    elif width and height:
        win.minsize(max(0, min_width), max(0, min_height))
        win.after_idle(lambda: center_toplevel(win, width=width, height=height))


def dialog_root(parent: tk.Misc) -> tk.Misc:
    """Toplevel-Parent: immer Hauptfenster (Frame als Parent bricht Dialoge auf Windows)."""
    return parent.winfo_toplevel()


def begin_table_dialog(
    parent: tk.Misc,
    *,
    title: str,
    width: int,
    height: int,
    min_width: int = 640,
    min_height: int = 400,
) -> tuple[tk.Toplevel, ttk.Frame, tk.Frame]:
    """
    Tabellen-Dialog anlegen (versteckt), Inhalt per pack in body/footer einfügen,
    danach show_table_dialog() aufrufen.
    """
    root = dialog_root(parent)
    dlg = tk.Toplevel(root)
    dlg.withdraw()
    dlg.title(title)
    theme_dialog(dlg)
    apply_window_icon(dlg)
    dlg.configure(bg=BG)
    dlg.minsize(max(320, min_width), max(200, min_height))
    footer = tk.Frame(dlg, bg=BG)
    footer.pack(side="bottom", fill="x", padx=14, pady=12)
    body = ttk.Frame(dlg)
    body.pack(side="top", fill="both", expand=True)
    dlg._td_table_size = (width, height, min_width, min_height)  # type: ignore[attr-defined]
    return dlg, body, footer


def show_table_dialog(dlg: tk.Toplevel) -> None:
    """Nach dem Aufbau: Größe setzen und sichtbar machen."""
    width, height, min_width, min_height = getattr(  # type: ignore[misc]
        dlg, "_td_table_size", (820, 520, 640, 400)
    )
    dlg.update_idletasks()
    _apply_dialog_geometry(
        dlg, width=width, height=height, min_width=min_width, min_height=min_height
    )
    try:
        dlg.deiconify()
    except tk.TclError:
        pass
    dlg.lift()
    try:
        dlg.focus_force()
    except tk.TclError:
        pass


def pack_dialog_shell(
    dlg: tk.Toplevel,
    *,
    footer: tk.Frame | None = None,
) -> ttk.Frame:
    """
    Body oben (expand), Footer unten — per grid, damit der Inhalt nicht auf Höhe 0 fällt.
    """
    dlg.grid_rowconfigure(0, weight=1)
    dlg.grid_columnconfigure(0, weight=1)
    body = ttk.Frame(dlg)
    body.grid(row=0, column=0, sticky="nsew")
    if footer is not None:
        footer.grid(row=1, column=0, sticky="ew")
    return body


def finalize_dialog_size(
    dlg: tk.Toplevel,
    *,
    width: int,
    height: int,
    min_width: int = 0,
    min_height: int = 0,
) -> None:
    """Nach dem Aufbau: zu kleine oder zu große Geometrie korrigieren."""
    _apply_dialog_geometry(dlg, width=width, height=height, min_width=min_width, min_height=min_height)
    dlg.lift()
    try:
        dlg.focus_force()
    except tk.TclError:
        pass


def _apply_dialog_geometry(
    dlg: tk.Toplevel,
    *,
    width: int,
    height: int,
    min_width: int = 0,
    min_height: int = 0,
) -> None:
    dlg.update_idletasks()
    sw = dlg.winfo_screenwidth()
    sh = dlg.winfo_screenheight()
    margin = 48
    mw = max(320, min(min_width or width, sw - margin))
    mh = max(200, min(min_height or height, sh - margin))
    tw = max(mw, min(width, sw - margin))
    th = max(mh, min(height, sh - margin))
    try:
        dlg.minsize(mw, mh)
    except tk.TclError:
        pass
    center_toplevel(dlg, width=tw, height=th)
    dlg.update_idletasks()


def finalize_table_dialog(
    dlg: tk.Toplevel,
    *,
    width: int,
    height: int,
    min_width: int = 640,
    min_height: int = 400,
) -> None:
    """Tabellen-Dialog: Größe erzwingen (nach Map, falls Windows Layout verzögert)."""
    def _apply() -> None:
        _apply_dialog_geometry(
            dlg, width=width, height=height, min_width=min_width, min_height=min_height
        )
        dlg.lift()

    _apply()
    dlg.after_idle(_apply)
    dlg.after(80, _apply)


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
