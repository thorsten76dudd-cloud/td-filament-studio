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

)

from creality_nfc.cfs_slot_index import flat_slot_index, slot_ref_at_flat

from creality_nfc.printer_control import PrinterControlError



_GCODE_FILAMENT_HINTS = ("PETG", "PLA", "ABS", "TPU", "ASA", "PC", "NYLON", "PA")





def get_cfs_material(

    state: dict[str, Any],

    slot_index: int,

    *,

    box_id: int = 1,

) -> dict[str, Any] | None:

    """Rohdaten eines CFS-Slots (materials[id] auf der CFS-Box type 0)."""

    bi = _find_boxs_info(state)

    if not isinstance(bi, dict):

        return None

    bid = int(box_id or 1)

    for box in _boxes_for_slots(_material_boxes(bi, state)):

        if box.get("type") != 0:

            continue

        try:

            if int(box.get("id", 1) or 1) != bid:

                continue

        except (TypeError, ValueError):

            if bid != 1:

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





def find_loaded_slot_ref(state: dict[str, Any]) -> tuple[int, int] | None:

    """(box_id, material_id 0–3) — Filament im Extruder."""

    meta = parse_cfs_meta(state)

    if meta.loaded_index is not None and 0 <= meta.loaded_index <= 3:

        return (meta.loaded_box_id or 1, meta.loaded_index)

    for box_id in range(1, 5):

        for sid in range(4):

            mat = get_cfs_material(state, sid, box_id=box_id)

            if not mat:

                continue

            try:

                if int(mat.get("state", 0) or 0) == 2:

                    return (box_id, sid)

            except (TypeError, ValueError):

                continue

    return None





def find_loaded_slot_index(state: dict[str, Any]) -> int | None:

    """material_id 0–3 der geladenen Spule (Kompatibilität, bevorzugt Box 1)."""

    ref = find_loaded_slot_ref(state)

    return ref[1] if ref else None





def find_loaded_flat_index(

    state: dict[str, Any],

    slots: list[CfsSlotInfo],

) -> int | None:

    ref = find_loaded_slot_ref(state)

    if ref is None:

        return None

    return flat_slot_index(slots, ref[0], ref[1])





def resolve_live_filament_slot_index(

    state: dict[str, Any],

    gcode_path: str,

    slots: list[CfsSlotInfo],

) -> int | None:

    """

    Flacher Index in ``slots`` (all_slots) für Live-Anzeige.

    G-Code-Farbe/Verbrauch vor falschem loaded_index der Firmware.

    """

    loaded = find_loaded_flat_index(state, slots) if slots else None

    if loaded is None:

        ref = find_loaded_slot_ref(state)

        if ref and slots:

            loaded = flat_slot_index(slots, ref[0], ref[1])

    path = (gcode_path or "").strip()

    if not path or not slots:

        return loaded

    try:

        from creality_nfc.gcode_filament import (

            build_slot_usage_plan,

            find_gcode_file_info,

        )

    except ImportError:

        return loaded



    entry = find_gcode_file_info(state, path)

    plans = build_slot_usage_plan(state, path, slots, file_entry=entry)

    if not plans:
        inferred = infer_slot_from_gcode(path, slots)
        if inferred is not None:
            return inferred
        return loaded

    primary = max(plans, key=lambda p: (p.grams, -p.slot_index))

    primary_idx = primary.slot_index

    plan_slots = {p.slot_index for p in plans}

    if loaded is None:

        return primary_idx

    if loaded not in plan_slots:

        return primary_idx

    loaded_plan = next((p for p in plans if p.slot_index == loaded), None)

    if loaded_plan is None:

        return primary_idx

    if primary.grams >= 2 and primary.grams > int(loaded_plan.grams or 0) * 1.5:

        return primary_idx

    return loaded





def filament_ready_in_extruder(

    state: dict[str, Any],

    slot_index: int,

    *,

    box_id: int = 1,

) -> bool:

    """True wenn Filament im Extruder für diesen Slot (auch nach Zufuhr in Creality-App)."""

    if int(state.get("materialStatus", 0) or 0) == 1:

        return False

    ref = find_loaded_slot_ref(state)

    if ref is not None:

        return ref == (int(box_id or 1), int(slot_index))

    mat = get_cfs_material(state, slot_index, box_id=box_id)

    if not mat:

        return False

    if int(mat.get("selected", 0) or 0) == 1:

        return True

    if int(mat.get("state", 0) or 0) == 2:

        return True

    meta = parse_cfs_meta(state)

    return (

        meta.active_index == slot_index

        and (meta.active_box_id or 1) == int(box_id or 1)

    )





def infer_slot_from_gcode(gcode_path: str, slots: list[CfsSlotInfo]) -> int | None:

    """Flacher Index: PETG/PLA im Dateinamen → passenden CFS-Slot."""

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

    box_id: int = 1,

) -> None:

    """Nach feedInOrOut warten, bis Filament im Extruder (oder Timeout)."""

    deadline = time.monotonic() + max(5.0, timeout_s)

    bid = int(box_id or 1)

    while time.monotonic() < deadline:

        state = state_provider()

        if filament_ready_in_extruder(state, slot_index, box_id=bid):

            return

        time.sleep(0.45)

    state = state_provider()

    ref = find_loaded_slot_ref(state)

    if ref == (bid, slot_index):

        return

    raise PrinterControlError(

        "Filament-Zufuhr: Zeitüberschreitung.\n"

        "Filament in Creality Print laden (Zufuhr) oder in der App den richtigen Slot wählen "

        "(z. B. 2A) und erneut drucken.\n"

        "Fehler FR0121: CFS-Filament im Extruder, Job aber für Spulenhalter gesliced → CFS zurückziehen "

        "oder im Slicer „CFS aktivieren“."

    )





def active_slot_label(slots: list[CfsSlotInfo], flat_index: int | None) -> str:

    if flat_index is None:

        return "—"

    ref = slot_ref_at_flat(slots, flat_index)

    if ref is None:

        return "—"

    from creality_nfc.cfs_layout import cfs_slot_label



    return cfs_slot_label(ref[0], ref[1])


