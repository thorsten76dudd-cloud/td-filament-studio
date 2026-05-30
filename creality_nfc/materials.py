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


def _identity_from_item(item: dict) -> tuple[str, str, str, str]:
    """ID, Marke, Name, Typ — auch wenn Creality Felder außerhalb von base nutzt."""
    base = item.get("base") if isinstance(item.get("base"), dict) else {}
    meta = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    fid = str(
        base.get("id")
        or base.get("materialId")
        or item.get("filament_id")
        or item.get("materialId")
        or item.get("filamentId")
        or meta.get("id")
        or meta.get("materialId")
        or ""
    ).strip()
    name = str(
        base.get("name")
        or base.get("materialName")
        or item.get("name")
        or item.get("filamentName")
        or item.get("materialName")
        or meta.get("name")
        or ""
    ).strip()
    brand = str(
        base.get("brand")
        or base.get("vendor")
        or item.get("brand")
        or item.get("vendor")
        or meta.get("vendor")
        or meta.get("brand")
        or ""
    ).strip()
    mtype = str(
        base.get("meterialType")
        or base.get("materialType")
        or item.get("materialType")
        or item.get("meterialType")
        or meta.get("type")
        or ""
    ).strip()
    if not fid or not name:
        from creality_nfc.slicer_import import _scan_text_for_metadata

        texts: list[str] = []
        kv = item.get("kvParam") if isinstance(item.get("kvParam"), dict) else {}
        if not kv and isinstance(item.get("engine_data"), dict):
            kv = item["engine_data"]
        if isinstance(kv, dict):
            for key in ("filament_notes", "description", "notes", "name", "filament_name"):
                raw = kv.get(key)
                if isinstance(raw, str) and raw.strip():
                    texts.append(raw)
        for key in ("description", "filament_notes", "notes"):
            raw = item.get(key)
            if isinstance(raw, str) and raw.strip():
                texts.append(raw)
        for text in texts:
            parsed = _scan_text_for_metadata(text)
            if not parsed:
                continue
            fid = fid or str(parsed.get("id") or "").strip()
            brand = brand or str(parsed.get("vendor") or "").strip()
            name = name or str(parsed.get("name") or "").strip()
            mtype = mtype or str(parsed.get("type") or "").strip()
            if fid and name:
                break
    return fid, brand, name, mtype


def profile_list_stats(data: dict) -> tuple[int, int, int]:
    """(Einträge in JSON, davon anzeigbar, übersprungen ohne ID/Name)."""
    items = data.get("result", {}).get("list", [])
    if not isinstance(items, list):
        return 0, 0, 0
    raw = len(items)
    loaded = 0
    skipped = 0
    for item in items:
        if not isinstance(item, dict):
            skipped += 1
            continue
        fid, _brand, name, _mtype = _identity_from_item(item)
        if fid and name:
            loaded += 1
        else:
            skipped += 1
    return raw, loaded, skipped


def load_database_from_data(data: dict) -> list[FilamentProfile]:
    items = data.get("result", {}).get("list", [])
    out: list[FilamentProfile] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        fid, brand, name, mtype = _identity_from_item(item)
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
