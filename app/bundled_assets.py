"""Mitgelieferte Dateien (STL/3MF) — Entwicklung und PyInstaller-Bundle."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from app.paths import app_dir

# RFID-Tag-Halter für offizielle Creality-Kunststoffspulen (5 Teile)
CHIP_TAG_PLASTIC_HOLDER_DIR = Path("downloads") / "creality-plastic-tag-holder"
CHIP_TAG_PLASTIC_STL_NAMES: tuple[str, ...] = (
    "Grundkörper.stl",
    "1A.stl",
    "1B.stl",
    "1C.stl",
    "1D.stl",
)


def bundled_asset_path(relative: str | Path) -> Path:
    """Pfad zu einer Datei unter assets/ (Dev-Repo oder EXE-Bundle)."""
    rel = Path(relative)
    if getattr(sys, "frozen", False):
        bundle = Path(sys._MEIPASS) / "assets" / rel
        if bundle.is_file():
            return bundle
    local = app_dir() / "assets" / rel
    return local


def bundled_plastic_holder_stls() -> list[Path]:
    """Alle mitgelieferten STL-Teile des Kunststoff-Tag-Halters."""
    out: list[Path] = []
    for name in CHIP_TAG_PLASTIC_STL_NAMES:
        path = bundled_asset_path(CHIP_TAG_PLASTIC_HOLDER_DIR / name)
        if path.is_file():
            out.append(path)
    return out


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
        filetypes=[("3D-Modell", "*.stl;*.3mf"), ("STL", "*.stl"), ("3MF", "*.3mf"), ("Alle Dateien", "*.*")],
    )
    if not dest:
        return None
    path = Path(dest)
    shutil.copy2(src, path)
    notify(parent, f"Gespeichert:\n{path}", "info")
    return path


def save_bundled_plastic_holder_stls(parent) -> list[Path] | None:
    """Alle Halter-STL in einen vom Nutzer gewählten Ordner kopieren."""
    from tkinter import filedialog

    from ui.messaging import notify

    sources = bundled_plastic_holder_stls()
    if len(sources) != len(CHIP_TAG_PLASTIC_STL_NAMES):
        missing = [
            n
            for n in CHIP_TAG_PLASTIC_STL_NAMES
            if not bundled_asset_path(CHIP_TAG_PLASTIC_HOLDER_DIR / n).is_file()
        ]
        notify(
            parent,
            "Tag-Halter-STL fehlen im Programm:\n" + "\n".join(missing),
            "error",
        )
        return None
    dest_dir = filedialog.askdirectory(
        parent=parent,
        title="Ordner für Tag-Halter STL (Creality Kunststoffspule)",
    )
    if not dest_dir:
        return None
    folder = Path(dest_dir)
    saved: list[Path] = []
    for src in sources:
        target = folder / src.name
        shutil.copy2(src, target)
        saved.append(target)
    notify(
        parent,
        f"{len(saved)} STL gespeichert in:\n{folder}\n\n"
        + ", ".join(p.name for p in saved),
        "info",
    )
    return saved
