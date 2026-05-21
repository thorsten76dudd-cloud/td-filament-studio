"""STL einlesen (ASCII/Binär) für die eingebaute Vorschau."""

from __future__ import annotations

import struct
from pathlib import Path

Triangle = tuple[
    tuple[float, float, float],
    tuple[float, float, float],
    tuple[float, float, float],
]

_MAX_TRIANGLES = 12_000


def load_stl_triangles(path: Path) -> list[Triangle]:
    path = path.resolve()
    if not path.is_file():
        return []
    raw = path.read_bytes()
    if len(raw) < 84:
        return []
    head = raw[:200].lstrip()
    if head.lower().startswith(b"solid"):
        try:
            text = raw.decode("utf-8", errors="replace")
        except OSError:
            return []
        return _load_ascii(text)
    return _load_binary(raw)


def _load_binary(data: bytes) -> list[Triangle]:
    if len(data) < 84:
        return []
    count = struct.unpack_from("<I", data, 80)[0]
    tris: list[Triangle] = []
    offset = 84
    for _ in range(count):
        if offset + 50 > len(data):
            break
        vals = struct.unpack_from("<12f", data, offset)
        offset += 50
        tris.append(
            (
                (vals[0], vals[1], vals[2]),
                (vals[3], vals[4], vals[5]),
                (vals[6], vals[7], vals[8]),
            )
        )
    return _subsample(tris)


def _load_ascii(text: str) -> list[Triangle]:
    tris: list[Triangle] = []
    verts: list[tuple[float, float, float]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        low = line.lower()
        if low.startswith("vertex"):
            parts = line.split()
            if len(parts) >= 4:
                try:
                    verts.append((float(parts[1]), float(parts[2]), float(parts[3])))
                except ValueError:
                    pass
        elif low.startswith("endloop") or low.startswith("endfacet"):
            if len(verts) >= 3:
                for i in range(1, len(verts) - 1):
                    tris.append((verts[0], verts[i], verts[i + 1]))
            verts = []
        elif low.startswith("facet") and "normal" in low:
            verts = []
    return _subsample(tris)


def _subsample(tris: list[Triangle]) -> list[Triangle]:
    if len(tris) <= _MAX_TRIANGLES:
        return tris
    step = max(1, len(tris) // _MAX_TRIANGLES)
    return tris[::step]


def triangle_bounds(tris: list[Triangle]) -> tuple[tuple[float, float, float], float]:
    if not tris:
        return (0.0, 0.0, 0.0), 1.0
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    for a, b, c in tris:
        for x, y, z in (a, b, c):
            xs.append(x)
            ys.append(y)
            zs.append(z)
    cx = (min(xs) + max(xs)) / 2
    cy = (min(ys) + max(ys)) / 2
    cz = (min(zs) + max(zs)) / 2
    radius = max(
        max(abs(x - cx) for x in xs),
        max(abs(y - cy) for y in ys),
        max(abs(z - cz) for z in zs),
        1e-6,
    )
    return (cx, cy, cz), radius
