"""ICO mit allen Windows-Größen erzeugen (16–256 px). Einmal ausführen nach Icon-Änderung."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from ico_write import build_app_icon

HERE = Path(__file__).resolve().parent


def build() -> None:
    ico_path = build_app_icon(HERE)
    with Image.open(ico_path) as check:
        n = 0
        try:
            while True:
                check.seek(n)
                print(f"  {n}: {check.size}")
                n += 1
        except EOFError:
            pass
        print(f"OK {ico_path} ({n} Größen, {ico_path.stat().st_size} bytes)")


if __name__ == "__main__":
    build()
