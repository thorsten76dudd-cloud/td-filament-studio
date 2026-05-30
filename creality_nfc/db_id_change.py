"""Material-ID in material_database.json ändern (ein Profil, inkl. Notizen-JSON)."""

from __future__ import annotations

import copy
import json
import re

from creality_nfc.materials import _identity_from_item, normalize_filament_id
from creality_nfc.slicer_import import _scan_text_for_metadata


def _validate_new_id(new_id: str) -> str:
    fid = normalize_filament_id(new_id.strip())
    digits = "".join(ch for ch in fid if ch.isdigit())
    if len(digits) != 5:
        raise ValueError("Die neue ID muss genau 5 Ziffern haben (z. B. 06099).")
    return digits.zfill(5)[-5:]


def _patch_notes_text(text: str, new_id: str) -> str:
    if not text or not text.strip():
        return text
    meta = _scan_text_for_metadata(text)
    if meta:
        meta["id"] = new_id
        return json.dumps(meta, ensure_ascii=False)
    return re.sub(
        r'("id"\s*:\s*["\']?)\d{4,6}(["\']?)',
        rf"\g<1>{new_id}\2",
        text,
        count=1,
        flags=re.I,
    )


def _patch_item_ids(item: dict, new_id: str) -> None:
    base = item.setdefault("base", {})
    base["id"] = new_id
    for key in ("materialId", "filamentId", "filament_id"):
        if key in base:
            base[key] = new_id
    meta = item.get("metadata")
    if isinstance(meta, dict):
        for key in ("id", "materialId"):
            if key in meta:
                meta[key] = new_id
    kv = item.get("kvParam")
    if not isinstance(kv, dict) and isinstance(item.get("engine_data"), dict):
        kv = item["engine_data"]
    if isinstance(kv, dict):
        for key in ("filament_notes", "description", "notes"):
            raw = kv.get(key)
            if isinstance(raw, str) and raw.strip():
                kv[key] = _patch_notes_text(raw, new_id)
    for key in ("description", "filament_notes", "notes"):
        raw = item.get(key)
        if isinstance(raw, str) and raw.strip():
            item[key] = _patch_notes_text(raw, new_id)


def find_profile_index(
    data: dict,
    *,
    filament_id: str,
    brand: str,
    name: str,
) -> int:
    want = normalize_filament_id(filament_id)
    brand_s = brand.strip()
    name_s = name.strip()
    lst = data.get("result", {}).get("list", [])
    if not isinstance(lst, list):
        raise ValueError("Ungültige Material-Datenbank.")
    for i, item in enumerate(lst):
        if not isinstance(item, dict):
            continue
        fid, b, n, _ = _identity_from_item(item)
        if normalize_filament_id(fid) != want:
            continue
        if brand_s and b.strip() != brand_s:
            continue
        if name_s and n.strip() != name_s:
            continue
        return i
    raise ValueError(
        f"Profil nicht gefunden: {brand_s} — {name_s} (ID {want}).\n"
        "Zuerst „Vom Drucker (SSH)“ laden oder Zeile in der Liste wählen."
    )


def id_collision(
    data: dict,
    new_id: str,
    *,
    brand: str,
    name: str,
) -> tuple[str, str] | None:
    """Anderes Profil mit gleicher neuer ID → (brand, name) oder None."""
    want = normalize_filament_id(new_id)
    brand_s = brand.strip()
    name_s = name.strip()
    for item in data.get("result", {}).get("list", []):
        if not isinstance(item, dict):
            continue
        fid, b, n, _ = _identity_from_item(item)
        if normalize_filament_id(fid) != want:
            continue
        if b.strip() == brand_s and n.strip() == name_s:
            continue
        return b.strip(), n.strip()
    return None


def change_profile_filament_id(
    data: dict,
    *,
    old_id: str,
    brand: str,
    name: str,
    new_id: str,
    allow_collision: bool = False,
) -> dict:
    """
    Ein Profil auf neue 5-stellige ID umstellen (base + Notizen-JSON).
    Ersetzt nicht andere Profile mit der alten ID.
    """
    new_norm = _validate_new_id(new_id)
    old_norm = normalize_filament_id(old_id)
    if old_norm == new_norm:
        raise ValueError("Neue ID ist identisch mit der alten.")

    data = copy.deepcopy(data)
    idx = find_profile_index(data, filament_id=old_id, brand=brand, name=name)
    hit = id_collision(data, new_norm, brand=brand, name=name)
    if hit and not allow_collision:
        raise ValueError(
            f"ID {new_norm} ist bereits belegt von „{hit[0]} — {hit[1]}“.\n"
            "Andere ID wählen oder das andere Profil zuerst umbenennen."
        )

    item = data["result"]["list"][idx]
    _patch_item_ids(item, new_norm)
    data["result"]["count"] = len(data["result"]["list"])
    return data
