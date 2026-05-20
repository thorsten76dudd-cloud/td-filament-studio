"""Multi-Größen-ICO (PNG eingebettet) — funktioniert zuverlässig unter Windows."""

from __future__ import annotations

import io
import struct
from pathlib import Path

from PIL import Image


def write_ico(path: Path, images: list[Image.Image]) -> None:
    """images: beliebige quadratische PIL-Bilder, Größen aus image.size."""
    png_blobs: list[bytes] = []
    for im in images:
        buf = io.BytesIO()
        im.convert("RGBA").save(buf, format="PNG", optimize=True)
        png_blobs.append(buf.getvalue())

    count = len(png_blobs)
    header = struct.pack("<HHH", 0, 1, count)
    offset = 6 + 16 * count
    entries = bytearray()
    data = bytearray()
    for im, blob in zip(images, png_blobs):
        w, h = im.size
        bw = w if w < 256 else 0
        bh = h if h < 256 else 0
        entries.extend(
            struct.pack(
                "<BBBBHHII",
                bw,
                bh,
                0,
                0,
                1,
                32,
                len(blob),
                offset,
            )
        )
        data.extend(blob)
        offset += len(blob)
    path.write_bytes(header + bytes(entries) + bytes(data))


def load_source_png() -> Image.Image:
    here = Path(__file__).resolve().parent
    for candidate in (
        here / "app_logo_128.png",
        Path(r"C:\Users\tdudd\.cursor\projects\c-Users-tdudd-Desktop-creality\assets\app_icon_source.png"),
    ):
        if candidate.is_file():
            src = Image.open(candidate).convert("RGBA")
            w, h = src.size
            side = min(w, h)
            return src.crop(((w - side) // 2, (h - side) // 2, (w + side) // 2, (h + side) // 2))
    raise FileNotFoundError("Icon-PNG fehlt")


def build_app_icon(out_dir: Path | None = None) -> Path:
    out_dir = out_dir or Path(__file__).resolve().parent
    src = load_source_png()
    sizes = (16, 24, 32, 48, 64, 128, 256)
    frames = [src.resize((s, s), Image.Resampling.LANCZOS) for s in sizes]
    ico_path = out_dir / "app_icon.ico"
    write_ico(ico_path, frames)
    for s in (32, 48, 128):
        frames[sizes.index(s)].save(out_dir / f"app_logo_{s}.png")
    return ico_path
