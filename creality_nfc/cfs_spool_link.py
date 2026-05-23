"""CFS-Slot ↔ lokale Spule (Zuordnung, Abgleich mit Drucker-RFID)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from creality_nfc.cfs_adopt import CfsSlotInfo, SLOT_LABELS
from creality_nfc.color_util import creality_color_to_hex
from creality_nfc.gcode_filament import (
    GcodeFilamentSpec,
    _color_distance,
    material_hint_from_gcode_path,
)
from creality_nfc.materials import normalize_filament_id

if TYPE_CHECKING:
    from creality_nfc.spool_inventory import Spool, SpoolInventory


def slot_label(index: int | None) -> str:
    if index is None or index < 0 or index > 3:
        return "—"
    return SLOT_LABELS[index]


def find_spool_for_slot(
    inventory: SpoolInventory,
    slot: CfsSlotInfo,
) -> Spool | None:
    """Passende Spule: expliziter CFS-Slot, Tag-UID, Filament-ID, Name."""
    slot_box = getattr(slot, "box_id", 1) or 1
    for sp in inventory.spools:
        key = sp.effective_cfs_key()
        if key and key == (slot_box, slot.index):
            return sp
        if sp.effective_cfs_slot() == slot.index and (sp.cfs_box_id or 1) == slot_box:
            return sp
    rfid = (slot.rfid_id or "").strip()
    if rfid:
        want = normalize_filament_id(rfid)
        for sp in inventory.spools:
            if sp.filament_id and normalize_filament_id(sp.filament_id) == want:
                return sp
            if sp.tag_uid and sp.tag_uid.upper() in rfid.upper():
                return sp
    name = (slot.name or "").strip().lower()
    vendor = (slot.vendor or "").strip().lower()
    if name or vendor:
        for sp in inventory.spools:
            pn = (sp.material_name or sp.label or "").strip().lower()
            pb = sp.brand.strip().lower()
            if name and pn == name:
                return sp
            if vendor and name and pb == vendor and name in pn:
                return sp
    return None


def _spool_allowed_for_slot(
    sp: Spool,
    slot_index: int,
    *,
    cfs_slots: list[CfsSlotInfo] | None = None,
) -> bool:
    """slot_index = flacher Index in cfs_slots (Multi-CFS) oder material_id 0–3."""
    if cfs_slots and 0 <= slot_index < len(cfs_slots):
        slot = cfs_slots[slot_index]
        key = sp.effective_cfs_key()
        if key:
            return key == (
                getattr(slot, "box_id", 1) or 1,
                slot.index,
            )
        eff = sp.effective_cfs_slot()
        if eff is None:
            return True
        return eff == slot.index and (sp.cfs_box_id or 1) == (getattr(slot, "box_id", 1) or 1)
    eff = sp.effective_cfs_slot()
    if eff is None:
        return True
    return eff == slot_index


def find_spool_for_deduct(
    inventory: SpoolInventory,
    cfs_slots: list[CfsSlotInfo],
    slot_index: int,
    spec: GcodeFilamentSpec | None = None,
    *,
    gcode_path: str = "",
) -> Spool | None:
    """Spule für Abzug: nur passender CFS-Slot, nicht „irgendeine“ verknüpfte Spule."""
    if 0 <= slot_index < len(cfs_slots):
        sp = find_spool_for_slot(inventory, cfs_slots[slot_index])
        if sp is not None and _spool_allowed_for_slot(
            sp, slot_index, cfs_slots=cfs_slots
        ):
            return sp
    elif 0 <= slot_index <= 3:
        sp = inventory.find_by_cfs_slot(slot_index)
        if sp is not None:
            return sp
    hint = material_hint_from_gcode_path(gcode_path)
    want_mat = (hint or (spec.material_type if spec else "") or "").strip().upper()
    if want_mat:
        for candidate in inventory.spools:
            if not _spool_allowed_for_slot(
                candidate, slot_index, cfs_slots=cfs_slots
            ):
                continue
            blob = f"{candidate.material_name} {candidate.label} {candidate.brand}".upper()
            if want_mat == "PLA" and "PLA" not in blob:
                continue
            if want_mat != "PLA" and want_mat not in blob:
                continue
            if want_mat == "PETG" and "PLA" in blob and "PETG" not in blob:
                continue
            return candidate
    want_hex = creality_color_to_hex(spec.color_hex) if spec and spec.color_hex else None
    if want_hex and not hint:
        best: Spool | None = None
        best_d = 1e9
        for candidate in inventory.spools:
            if not _spool_allowed_for_slot(
                candidate, slot_index, cfs_slots=cfs_slots
            ):
                continue
            sp_hex = creality_color_to_hex(candidate.color_hex)
            if sp_hex:
                d = _color_distance(want_hex, sp_hex)
                if d < best_d:
                    best_d = d
                    best = candidate
        if best is not None and best_d <= 80:
            return best
    return None


def bind_slot(inventory: SpoolInventory, spool_id: str, slot_index: int | None) -> None:
    """Spule einem CFS-Slot zuweisen (0–3); andere Spulen an diesem Slot lösen."""
    sp = inventory.get(spool_id)
    if not sp:
        return
    if slot_index is not None and not (0 <= slot_index <= 3):
        slot_index = None
    for other in inventory.spools:
        if other.id != spool_id and other.cfs_slot == slot_index and slot_index is not None:
            other.cfs_slot = None
    sp.cfs_slot = slot_index
    inventory.update(sp)


def spool_at_active_slot(inventory: SpoolInventory, active_index: int | None) -> Spool | None:
    if active_index is None or not (0 <= active_index <= 3):
        return None
    for sp in inventory.spools:
        if sp.cfs_slot == active_index:
            return sp
    return None
