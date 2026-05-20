"""Spulendaten → Filament-Profil (Tag schreiben)."""

from __future__ import annotations

import json
from typing import Any

from creality_nfc.color_util import creality_color_to_hex
from creality_nfc.db_store import find_item
from creality_nfc.materials import FilamentProfile, normalize_filament_id
from creality_nfc.spool_inventory import Spool

try:
    from ui.color_swatch import normalize_hex
except ImportError:

    def normalize_hex(color: str) -> str:  # pragma: no cover
        h = str(color or "").strip().lstrip("#").upper()
        h = "".join(c for c in h if c in "0123456789ABCDEF")
        if len(h) >= 6:
            return h[-6:]
        return "FFFFFF"


def _kv_from_item(item: dict) -> dict[str, Any]:
    raw = item.get("kvParam") or item.get("engine_data") or {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    return {}


def profile_color_from_db(data: dict | None, profile: FilamentProfile) -> str:
    """Profilfarbe aus kvParam (default_filament_colour), falls in der DB vorhanden."""
    if not data:
        return ""
    item = find_item(
        data,
        profile.filament_id,
        brand=profile.brand,
        name=profile.name,
    )
    if not item:
        return ""
    kv = _kv_from_item(item)
    raw = kv.get("default_filament_colour") or kv.get("filament_colour") or ""
    if isinstance(raw, (list, tuple)) and raw:
        raw = raw[0]
    hx = creality_color_to_hex(str(raw))
    return normalize_hex(hx.lstrip("#")) if hx else ""


def format_spool_label(brand: str, name: str) -> str:
    """Einheitliche Bezeichnung wie nach RFID-Sync: „Marke — Material“."""
    b = (brand or "").strip()
    n = (name or "").strip()
    if b and n:
        return f"{b} — {n}"
    return n or b or "Spule"


def spool_fields_from_profile(
    profile: FilamentProfile,
    data: dict | None = None,
    *,
    current_label: str = "",
) -> dict[str, str]:
    """Felder für Spulen-Formular aus Material-DB-Profil."""
    try:
        from app.constants import printer_int_to_display
    except ImportError:
        printer_int_to_display = lambda x: (x or "").strip() or "K2 Pro"  # pragma: no cover

    fid = normalize_filament_id(profile.filament_id) or profile.filament_id
    label = format_spool_label(profile.brand, profile.name)
    color = profile_color_from_db(data, profile)
    return {
        "label": label[:80],
        "brand": profile.brand,
        "material_name": profile.name,
        "filament_id": fid,
        "color_hex": color,
        "printer": printer_int_to_display(profile.printer),
    }


def resolve_filament_profile(
    spool: Spool,
    profiles: list[FilamentProfile],
    *,
    default_printer: str = "K2 Pro",
) -> FilamentProfile | None:
    """DB-Treffer oder synthetisches Profil, wenn filament_id auf der Spule steht."""
    if spool.filament_id:
        want = normalize_filament_id(spool.filament_id)
        matches = [
            p for p in profiles if normalize_filament_id(p.filament_id) == want
        ]
        if spool.brand or spool.material_name:
            for p in matches:
                if spool.brand and p.brand != spool.brand:
                    continue
                if spool.material_name and p.name != spool.material_name:
                    continue
                return p
        if len(matches) == 1:
            return matches[0]
        if want:
            return FilamentProfile(
                filament_id=spool.filament_id,
                brand=spool.brand or "Creality",
                name=spool.material_name or spool.label or "Filament",
                material_type="",
                printer=spool.printer or default_printer,
            )
    brand = (spool.brand or "").strip()
    name = (spool.material_name or spool.label or "").strip()
    if brand and name:
        exact = [p for p in profiles if p.brand == brand and p.name == name]
        if len(exact) == 1:
            return exact[0]
        loose = [
            p for p in profiles if p.brand == brand and name.lower() in p.name.lower()
        ]
        if len(loose) == 1:
            return loose[0]
    return None
