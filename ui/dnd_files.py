"""Pfade aus Windows/macOS Drag & Drop (tkinterdnd2) auslesen."""

from __future__ import annotations

import re
from pathlib import Path


def parse_dnd_file_list(data: str) -> list[Path]:
    """Explorer-Drop: einzelne Pfade und Ordner (auch mit Leerzeichen)."""
    if not data or not str(data).strip():
        return []
    text = str(data).strip()
    paths: list[str] = []

    if "{" in text:
        i = 0
        while i < len(text):
            ch = text[i]
            if ch == "{":
                end = text.find("}", i + 1)
                if end < 0:
                    break
                segment = text[i + 1 : end].strip()
                if segment:
                    paths.append(segment)
                i = end + 1
            elif ch.isspace():
                i += 1
            else:
                j = i
                while j < len(text) and text[j] not in "{}":
                    j += 1
                segment = text[i:j].strip()
                if segment:
                    paths.append(segment)
                i = j
    elif "\n" in text or "\r" in text:
        paths = [p.strip() for p in re.split(r"[\r\n]+", text) if p.strip()]
    else:
        # Ein Pfad ohne Klammern — nicht an Leerzeichen splitten (Ordner mit Leerzeichen)
        paths = [text]

    out: list[Path] = []
    for raw in paths:
        cleaned = raw.strip().strip('"').rstrip("\\/")
        if cleaned:
            out.append(Path(cleaned))
    return out
