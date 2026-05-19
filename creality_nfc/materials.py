"""Load Creality material_database JSON (from CFS-RFID or printer)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


def normalize_filament_id(filament_id: str) -> str:
    """5-stellige Creality-ID (06001, 101001 → letzte 5 Ziffern vergleichbar)."""
    fid = str(filament_id or "").strip()
    if len(fid) == 6 and fid.startswith("1"):
        fid = fid[1:]
    digits = "".join(ch for ch in fid if ch.isdigit())
    if not digits:
        return fid
    return digits.zfill(5)[-5:]


@dataclass
class FilamentProfile:
    filament_id: str
    brand: str
    name: str
    material_type: str
    printer: str


def load_database_from_data(data: dict) -> list[FilamentProfile]:
    items = data.get("result", {}).get("list", [])
    out: list[FilamentProfile] = []
    for item in items:
        base = item.get("base", {})
        fid = str(base.get("id", "")).strip()
        brand = str(base.get("brand", "")).strip()
        name = str(base.get("name", "")).strip()
        mtype = str(base.get("meterialType", base.get("materialType", ""))).strip()
        printer = str(item.get("printerIntName", "")).strip()
        if not fid or not name:
            continue
        out.append(
            FilamentProfile(
                filament_id=fid,
                brand=brand,
                name=name,
                material_type=mtype,
                printer=printer,
            )
        )
    out.sort(key=lambda p: (p.brand.lower(), p.name.lower()))
    return out


def load_database(path: Path, printer_filter: str | None = None) -> list[FilamentProfile]:
    data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    return load_database_from_data(data)


def builtin_profiles() -> list[FilamentProfile]:
    """Fallback wenn keine material_database.json vorhanden."""
    return [
        FilamentProfile("01001", "Creality", "Generic PLA", "PLA", "K2"),
        FilamentProfile("01002", "Creality", "Generic PETG", "PETG", "K2"),
        FilamentProfile("01003", "Creality", "Generic ABS", "ABS", "K2"),
        FilamentProfile("101001", "Creality", "Hyper PLA", "PLA", "K2"),
        FilamentProfile("101002", "Creality", "Hyper PETG", "PETG", "K2"),
    ]


def find_database_files(root: Path) -> list[Path]:
    return sorted(root.glob("**/material_database/*.json")) + sorted(
        root.glob("**/k2*.json")
    )
