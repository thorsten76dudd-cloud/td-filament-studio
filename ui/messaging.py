"""In-App-Meldungen statt messagebox-Popups."""

from __future__ import annotations

from typing import Callable


def root_app(widget) -> object | None:
    w = widget
    while w is not None:
        if hasattr(w, "notify"):
            return w
        w = getattr(w, "master", None)
    return None


def notify(widget, text: str, level: str = "info") -> None:
    app = root_app(widget)
    if app:
        app.notify(text, level)
    else:
        print(f"[{level}] {text}")


def alert(widget, text: str, level: str = "error", title: str | None = None) -> None:
    """Protokoll + sichtbarer Dialog (für Fehler, die sonst leicht übersehen werden)."""
    notify(widget, text, level)
    from tkinter import messagebox

    app = root_app(widget)
    parent = app if app else widget.winfo_toplevel() if widget else None
    dialog_title = title or "TD Filament Studio"
    if level == "error":
        messagebox.showerror(dialog_title, text, parent=parent)
    elif level == "warn":
        messagebox.showwarning(dialog_title, text, parent=parent)
    else:
        messagebox.showinfo(dialog_title, text, parent=parent)


def confirm(
    widget,
    text: str,
    on_yes: Callable[[], None],
    on_no: Callable[[], None] | None = None,
) -> None:
    app = root_app(widget)
    if app and hasattr(app, "ask_confirm"):
        app.ask_confirm(text, on_yes, on_no)
    elif on_yes:
        on_yes()
