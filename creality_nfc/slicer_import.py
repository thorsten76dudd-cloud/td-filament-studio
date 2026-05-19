"""OrcaSlicer / Creality-Print Filament-Profile in material_database.json importieren."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from creality_nfc.db_store import add_or_update_item, find_item, new_filament_item
from creality_nfc.materials import normalize_filament_id

_METADATA_RE = re.compile(
    r'\{\s*"id"\s*:\s*["\']?(\d{4,6})["\']?\s*,\s*"vendor"\s*:\s*"([^"]*)"\s*,\s*"type"\s*:\s*"([^"]*)"\s*,\s*"name"\s*:\s*"([^"]*)"\s*\}',
    re.I,
)


@dataclass
class SlicerProfileImport:
    filament_id: str
    brand: str
    name: str
    material_type: str
    min_temp: int
    max_temp: int
    source: str


def _first_list_val(val: Any) -> Any:
    if isinstance(val, list) and val:
        return val[0]
    return val


def _temp_from_profile(data: dict[str, Any], key: str, default: int) -> int:
    raw = _first_list_val(data.get(key))
    if raw is None:
        return default
    try:
        v = int(round(float(raw)))
        if v > 500:
            return v // 100
        return v
    except (TypeError, ValueError):
        return default


def _material_type_from_data(data: dict[str, Any], fallback: str = "PLA") -> str:
    for key in ("filament_type", "material_type", "type"):
        raw = _first_list_val(data.get(key))
        if raw and str(raw).strip():
            return str(raw).strip().upper()
    return fallback.upper()


def _scan_text_for_metadata(text: str) -> dict[str, str] | None:
    if not text:
        return None
    m = _METADATA_RE.search(text)
    if m:
        return {
            "id": m.group(1),
            "vendor": m.group(2).strip(),
            "type": m.group(3).strip(),
            "name": m.group(4).strip(),
        }
    for blob in re.findall(r"\{[^{}]+\}", text):
        try:
            d = json.loads(blob)
        except json.JSONDecodeError:
            continue
        if not isinstance(d, dict):
            continue
        fid = str(d.get("id") or "").strip()
        if fid:
            return {
                "id": fid,
                "vendor": str(d.get("vendor") or "").strip(),
                "type": str(d.get("type") or "").strip(),
                "name": str(d.get("name") or "").strip(),
            }
    return None


def parse_slicer_filament_json(
    data: dict[str, Any],
    *,
    source: str = "",
) -> SlicerProfileImport | None:
    """Ein Orca-/Creality-Filament-JSON-Profil."""
    if not isinstance(data, dict):
        return None
    ftype = str(data.get("type") or "").lower()
    if ftype and ftype not in ("filament", "filament_profile"):
        return None

    meta: dict[str, str] | None = None
    for key in ("description", "filament_notes", "notes", "text", "name"):
        raw = data.get(key)
        if isinstance(raw, str):
            meta = _scan_text_for_metadata(raw)
            if meta:
                break
    if meta is None:
        meta = _scan_text_for_metadata(json.dumps(data, ensure_ascii=False)[:4000])

    brand = ""
    name = ""
    material_type = "PLA"
    filament_id = ""

    if meta:
        filament_id = meta["id"]
        brand = meta["vendor"]
        name = meta["name"]
        material_type = meta["type"] or "PLA"
    else:
        brand = str(
            _first_list_val(data.get("filament_vendor"))
            or data.get("brand")
            or ""
        ).strip()
        name = str(data.get("name") or "").strip()
        material_type = _material_type_from_data(data, "PLA")
        if not name:
            return None

    if not filament_id:
        digits = "".join(c for c in name if c.isdigit())
        if len(digits) >= 4:
            filament_id = digits[-5:].zfill(5)
        else:
            filament_id = str(abs(hash(f"{brand}|{name}|{material_type}")) % 100000).zfill(5)

    filament_id = normalize_filament_id(filament_id)
    if not filament_id:
        return None

    min_t = _temp_from_profile(data, "nozzle_temperature", 200)
    max_t = _temp_from_profile(data, "nozzle_temperature_range_high", min_t + 10)
    if max_t < min_t:
        max_t = min_t + 15
    bed = _temp_from_profile(data, "bed_temperature", 60)

    return SlicerProfileImport(
        filament_id=filament_id,
        brand=brand or "Custom",
        name=name,
        material_type=material_type,
        min_temp=min_t,
        max_temp=max_t,
        source=source,
    )


def collect_slicer_profiles_from_paths(paths: list[Path]) -> list[SlicerProfileImport]:
    out: list[SlicerProfileImport] = []
    seen: set[tuple[str, str, str]] = set()
    for path in paths:
        if not path.is_file() or path.suffix.lower() != ".json":
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, json.JSONDecodeError):
            continue
        profiles: list[dict[str, Any]] = []
        if isinstance(data, dict):
            profiles.append(data)
        elif isinstance(data, list):
            profiles.extend(x for x in data if isinstance(x, dict))
        for item in profiles:
            parsed = parse_slicer_filament_json(item, source=path.name)
            if parsed is None:
                continue
            key = (parsed.filament_id, parsed.brand.lower(), parsed.name.lower())
            if key in seen:
                continue
            seen.add(key)
            out.append(parsed)
    return out


def merge_slicer_profiles_into_db(
    data: dict[str, Any],
    profiles: list[SlicerProfileImport],
    *,
    template_item: dict | None = None,
) -> tuple[dict[str, Any], int, int]:
    """(db, neu, aktualisiert)"""
    added = 0
    updated = 0
    for p in profiles:
        existing = find_item(data, p.filament_id, brand=p.brand, name=p.name)
        item = new_filament_item(
            p.filament_id,
            p.brand,
            p.name,
            p.material_type,
            p.min_temp,
            p.max_temp,
            template_item=template_item,
        )
        if existing:
            updated += 1
        else:
            added += 1
        data = add_or_update_item(data, item)
    return data, added, updated
