"""Spulendaten → Filament-Profil (Tag schreiben)."""

from __future__ import annotations

from creality_nfc.materials import FilamentProfile, normalize_filament_id
from creality_nfc.spool_inventory import Spool


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
