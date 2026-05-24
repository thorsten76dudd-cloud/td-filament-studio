"""App-Icon und Header-Logo (Fenster, Taskleiste, UI)."""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path

from app.paths import app_dir

_ICON_DIR = Path("icons")
_APP_ICON = _ICON_DIR / "app_icon.ico"
_LOGO_48 = _ICON_DIR / "app_logo_48.png"
_LOGO_32 = _ICON_DIR / "app_logo_32.png"


def _asset_path(relative: Path) -> Path:
    if getattr(sys, "frozen", False):
        bundle = Path(sys._MEIPASS) / "assets" / relative
        if bundle.is_file():
            return bundle
    return app_dir() / "assets" / relative


def apply_window_icon(window: tk.Misc) -> None:
    """Taskleiste und Fenstertitel-Icon setzen."""
    ico = _asset_path(_APP_ICON)
    if not ico.is_file():
        return
    try:
        window.iconbitmap(default=str(ico))
    except tk.TclError:
        pass
    try:
        from PIL import Image, ImageTk

        png = _asset_path(_LOGO_48)
        if png.is_file():
            im = Image.open(png).convert("RGBA")
            photo = ImageTk.PhotoImage(im, master=window)
            window.iconphoto(True, photo)
            window._td_app_icon_photo = photo  # noqa: SLF001 — Referenz halten
    except Exception:
        pass


def load_tray_pil_image():
    """32×32 PNG für System-Tray (pystray)."""
    path = _asset_path(_LOGO_32)
    if not path.is_file():
        path = _asset_path(_LOGO_48)
    if not path.is_file():
        return None
    try:
        from PIL import Image

        im = Image.open(path).convert("RGBA")
        if im.size != (32, 32):
            im = im.resize((32, 32), Image.Resampling.LANCZOS)
        return im
    except Exception:
        return None


def load_header_logo(master: tk.Misc, *, size: int = 48) -> tk.PhotoImage | None:
    """Logo für die Kopfzeile (48 px)."""
    rel = _LOGO_48 if size >= 40 else _LOGO_32
    path = _asset_path(rel)
    if not path.is_file():
        return None
    try:
        from PIL import Image, ImageTk

        im = Image.open(path).convert("RGBA")
        if im.size[0] != size:
            im = im.resize((size, size), Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(im, master=master)
    except Exception:
        return None
