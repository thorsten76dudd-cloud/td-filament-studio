"""Lokale material_database.json lesen/schreiben."""

from __future__ import annotations

import json
from pathlib import Path

from .materials import FilamentProfile, normalize_filament_id


def db_path_for_printer(data_dir: Path, printer_label: str) -> Path:
    safe = printer_label.lower().replace(" ", "_")
    return data_dir / f"{safe}.json"


def save_database(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def load_database_raw(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8", errors="replace"))


def profiles_from_db(data: dict) -> list[FilamentProfile]:
    from .materials import load_database_from_data

    return load_database_from_data(data)


def list_items_for_id(data: dict, filament_id: str) -> list[dict]:
    want = normalize_filament_id(filament_id)
    if not want:
        return []
    out: list[dict] = []
    for item in data.get("result", {}).get("list", []):
        base = item.get("base", {})
        if normalize_filament_id(str(base.get("id", ""))) == want:
            out.append(item)
    return out


def find_item(
    data: dict,
    filament_id: str,
    *,
    brand: str | None = None,
    name: str | None = None,
) -> dict | None:
    """DB-Eintrag finden; bei mehreren gleichen IDs Marke+Name zur Eindeutigkeit."""
    matches = list_items_for_id(data, filament_id)
    if not matches:
        return None
    brand_s = (brand or "").strip()
    name_s = (name or "").strip()
    if brand_s and name_s:
        for item in matches:
            base = item.get("base", {})
            if str(base.get("brand", "")).strip() == brand_s and str(
                base.get("name", "")
            ).strip() == name_s:
                return item
    if len(matches) == 1:
        return matches[0]
    return matches[0]


def add_or_update_item(data: dict, item: dict) -> dict:
    lst = data.setdefault("result", {}).setdefault("list", [])
    base = item.get("base", {})
    fid = str(base.get("id", "")).strip()
    brand = str(base.get("brand", "")).strip()
    name = str(base.get("name", "")).strip()
    want = normalize_filament_id(fid)
    replaced = False
    for i, existing in enumerate(lst):
        eb = existing.get("base", {})
        if normalize_filament_id(str(eb.get("id", ""))) != want:
            continue
        if brand and name:
            if str(eb.get("brand", "")).strip() != brand or str(eb.get("name", "")).strip() != name:
                continue
        lst[i] = item
        replaced = True
        break
    if not replaced:
        lst.append(item)
    data["result"]["count"] = len(lst)
    return data


def new_filament_item(
    filament_id: str,
    brand: str,
    name: str,
    material_type: str,
    min_temp: int,
    max_temp: int,
    template_item: dict | None = None,
) -> dict:
    if template_item:
        import copy

        item = copy.deepcopy(template_item)
        base = item.setdefault("base", {})
    else:
        item = {
            "engineVersion": "1.0",
            "printerIntName": "F008",
            "nozzleDiameter": ["0.4"],
            "kvParam": {},
            "base": {
                "id": filament_id,
                "brand": brand,
                "name": name,
                "meterialType": material_type,
                "minTemp": min_temp,
                "maxTemp": max_temp,
                "isSoluble": False,
                "isSupport": False,
                "colors": ["#ffffff"],
            },
        }
        base = item["base"]

    base["id"] = filament_id.zfill(5)[-5:]
    base["brand"] = brand
    base["name"] = name
    base["meterialType"] = material_type
    base["minTemp"] = min_temp
    base["maxTemp"] = max_temp
    return item
