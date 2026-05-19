"""Installationspfade (Entwicklung + PyInstaller-EXE)."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


APP_DIR = app_dir()
DATA_DIR = APP_DIR / "data"


def ensure_data_dir() -> None:
    """data/ neben der EXE anlegen; Standarddateien aus dem Bundle kopieren."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not getattr(sys, "frozen", False):
        return
    bundle = Path(sys._MEIPASS) / "data"
    if not bundle.is_dir():
        return
    for src in bundle.iterdir():
        dest = DATA_DIR / src.name
        if dest.exists():
            continue
        if src.is_dir():
            shutil.copytree(src, dest)
        else:
            shutil.copy2(src, dest)
