"""Pfade aus Windows/macOS Drag & Drop (tkinterdnd2) auslesen."""

from __future__ import annotations

from pathlib import Path


def parse_dnd_file_list(data: str) -> list[Path]:
    """{C:\\Pfad mit Leerzeichen\\a.stl} C:\\b.stl → Liste von Path."""
    if not data or not str(data).strip():
        return []
    text = str(data).strip()
    paths: list[str] = []
    if text.startswith("{"):
        i = 0
        while i < len(text):
            if text[i] == "{":
                end = text.find("}", i + 1)
                if end < 0:
                    break
                paths.append(text[i + 1 : end])
                i = end + 1
            else:
                i += 1
    else:
        paths = text.split()
    return [Path(p) for p in paths if p.strip()]
