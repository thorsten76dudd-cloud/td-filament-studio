"""Mitgelieferte Dateien (3MF/STL) — Entwicklung und PyInstaller-Bundle."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from app.paths import app_dir

# Relativ zu assets/
CHIP_TAG_PLASTIC_3MF = Path("downloads") / "Chip-Tag.3mf"


def bundled_asset_path(relative: str | Path) -> Path:
    """Pfad zu einer Datei unter assets/ (Dev-Repo oder EXE-Bundle)."""
    rel = Path(relative)
    if getattr(sys, "frozen", False):
        bundle = Path(sys._MEIPASS) / "assets" / rel
        if bundle.is_file():
            return bundle
    local = app_dir() / "assets" / rel
    return local


def save_bundled_asset(
    parent,
    relative: str | Path,
    *,
    save_as_name: str | None = None,
    title: str = "Datei speichern",
) -> Path | None:
    """Nutzer wählt Zielordner — Kopie aus dem App-Bundle."""
    from tkinter import filedialog

    from ui.messaging import notify

    src = bundled_asset_path(relative)
    if not src.is_file():
        notify(parent, f"Datei fehlt im Programm:\n{relative}", "error")
        return None
    default_name = save_as_name or src.name
    dest = filedialog.asksaveasfilename(
        parent=parent,
        title=title,
        initialfile=default_name,
        defaultextension=src.suffix,
        filetypes=[("3MF-Modell", "*.3mf"), ("Alle Dateien", "*.*")],
    )
    if not dest:
        return None
    path = Path(dest)
    shutil.copy2(src, path)
    notify(parent, f"Gespeichert:\n{path}", "info")
    return path
