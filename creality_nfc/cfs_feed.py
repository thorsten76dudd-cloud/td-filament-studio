"""CFS-Zufuhr / Filament-Status (K2 WebSocket feedInOrOut)."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from creality_nfc.cfs_adopt import (
    CfsSlotInfo,
    _boxes_for_slots,
    _find_boxs_info,
    _material_boxes,
    _slot_id_from_material,
    parse_cfs_meta,
    parse_cfs_slots,
)
from creality_nfc.printer_control import PrinterControlError

_GCODE_FILAMENT_HINTS = ("PETG", "PLA", "ABS", "TPU", "ASA", "PC", "NYLON", "PA")


def get_cfs_material(state: dict[str, Any], slot_index: int) -> dict[str, Any] | None:
    """Rohdaten eines CFS-Slots (materials[id] auf der CFS-Box type 0)."""
    bi = _find_boxs_info(state)
    if not isinstance(bi, dict):
        return None
    for box in _boxes_for_slots(_material_boxes(bi, state)):
        if box.get("type") != 0:
            continue
        mats = box.get("materials") or []
        if not isinstance(mats, list):
            continue
        for idx, mat in enumerate(mats):
            if not isinstance(mat, dict):
                continue
            sid = _slot_id_from_material(mat, idx)
            if sid == slot_index:
                return mat
    return None


def find_loaded_slot_index(state: dict[str, Any]) -> int | None:
    """Slot mit Filament im Extruder (state==2 / loaded_index), sonst None."""
    meta = parse_cfs_meta(state)
    if meta.loaded_index is not None and 0 <= meta.loaded_index < 4:
        return meta.loaded_index
    for sid in range(4):
        mat = get_cfs_material(state, sid)
        if not mat:
            continue
        try:
            if int(mat.get("state", 0) or 0) == 2:
                return sid
        except (TypeError, ValueError):
            continue
    return None


def filament_ready_in_extruder(state: dict[str, Any], slot_index: int) -> bool:
    """True wenn Filament im Extruder für diesen Slot (auch nach Zufuhr in Creality-App)."""
    if int(state.get("materialStatus", 0) or 0) == 1:
        return False
    loaded = find_loaded_slot_index(state)
    if loaded is not None:
        return loaded == slot_index
    mat = get_cfs_material(state, slot_index)
    if not mat:
        return False
    if int(mat.get("selected", 0) or 0) == 1:
        return True
    if int(mat.get("state", 0) or 0) == 2:
        return True
    meta = parse_cfs_meta(state)
    return meta.active_index == slot_index


def infer_slot_from_gcode(gcode_path: str, slots: list[CfsSlotInfo]) -> int | None:
    """PETG/PLA im Dateinamen → passenden CFS-Slot wählen."""
    name = gcode_path.replace("\\", "/").rsplit("/", 1)[-1].upper()
    for hint in _GCODE_FILAMENT_HINTS:
        if hint not in name:
            continue
        for i, slot in enumerate(slots):
            if slot.empty:
                continue
            mtype = (slot.material_type or "").upper()
            if hint in mtype or (hint == "PLA" and "PLA" in mtype):
                return i
    return None


def wait_filament_ready(
    slot_index: int,
    state_provider: Callable[[], dict[str, Any]],
    *,
    timeout_s: float = 90.0,
) -> None:
    """Nach feedInOrOut warten, bis Filament im Extruder (oder Timeout)."""
    deadline = time.monotonic() + max(5.0, timeout_s)
    while time.monotonic() < deadline:
        state = state_provider()
        if filament_ready_in_extruder(state, slot_index):
            return
        time.sleep(0.45)
    state = state_provider()
    if find_loaded_slot_index(state) == slot_index:
        return
    raise PrinterControlError(
        "Filament-Zufuhr: Zeitüberschreitung.\n"
        "Filament in Creality Print laden (Zufuhr) oder in der App Slot 1A–1D wählen und erneut drucken.\n"
        "Fehler FR0121: CFS-Filament im Extruder, Job aber für Spulenhalter gesliced → CFS zurückziehen "
        "oder im Slicer „CFS aktivieren“."
    )
