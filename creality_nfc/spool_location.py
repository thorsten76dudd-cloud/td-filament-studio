"""Spulen-Standort: welcher Drucker / welcher CFS-Slot."""

from __future__ import annotations

from typing import TYPE_CHECKING

from creality_nfc.cfs_adopt import CfsSlotInfo
from creality_nfc.cfs_layout import CfsLayout, cfs_slot_label
from creality_nfc.cfs_spool_link import find_spool_for_slot
from creality_nfc.materials import normalize_filament_id
from creality_nfc.spool_inventory import _now

if TYPE_CHECKING:
    from creality_nfc.spool_inventory import Spool, SpoolInventory


def update_last_seen_from_layout(
    inventory: SpoolInventory,
    layout: CfsLayout,
    *,
    printer_name: str,
) -> int:
    """Verknüpfte Spulen aktualisieren, wenn sie in CFS-Slots stecken. Anzahl Updates."""
    if not printer_name.strip():
        return 0
    count = 0
    ts = _now()
    for slot in layout.all_slots():
        if slot.empty:
            continue
        sp = find_spool_for_slot(inventory, slot)
        if sp is None and slot.rfid_id:
            want = normalize_filament_id(slot.rfid_id)
            for cand in inventory.spools:
                if cand.filament_id and normalize_filament_id(cand.filament_id) == want:
                    sp = cand
                    break
        if sp is None:
            continue
        lab = cfs_slot_label(getattr(slot, "box_id", 1) or 1, slot.index)
        sp.last_seen_printer = printer_name.strip()
        sp.last_seen_slot_label = lab
        sp.last_seen_at = ts
        sp.cfs_box_id = getattr(slot, "box_id", 1) or 1
        sp.cfs_slot = slot.index
        count += 1
    return count


def spools_at_printer(inventory: SpoolInventory, printer_name: str) -> list[Spool]:
    name = printer_name.strip().lower()
    if not name:
        return []
    out: list[Spool] = []
    for sp in inventory.all():
        loc = (sp.location_printer or sp.last_seen_printer or "").strip().lower()
        if loc == name:
            out.append(sp)
    return out


def spools_in_storage(inventory: SpoolInventory) -> list[Spool]:
    """Kein Drucker zugeordnet — „nur Lager“."""
    out: list[Spool] = []
    for sp in inventory.all():
        if not (sp.location_printer or sp.last_seen_printer or "").strip():
            out.append(sp)
    return out
