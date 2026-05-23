"""Druckstart mit CFS — wie Creality Print (colorMatch, dann Druckbefehl)."""

from __future__ import annotations

import time
from typing import Any, Callable

from creality_nfc.cfs_adopt import CfsSlotInfo, SLOT_LABELS, _find_boxs_info, parse_cfs_meta, parse_cfs_slots
from creality_nfc.cfs_feed import (
    filament_ready_in_extruder,
    find_loaded_slot_index,
    infer_slot_from_gcode,
    wait_filament_ready,
)
from creality_nfc.gcode_filament import (
    GcodeFilamentSpec,
    build_preheat_params,
    find_gcode_file_info,
    gcode_uses_external_spool,
    merge_gcode_filament_info,
    resolve_slots_from_gcode,
)
from creality_nfc.printer_gcode import entry_remote_path
from creality_nfc.printer_control import PrinterControlError

_WAIT_FILAMENT_KEY = "__wait_filament__"

GCODE_PREFIXES = ("/mnt/UDISK/printer_data/gcodes/", "/usr/data/printer_data/gcodes/")


def normalize_gcode_path(path: str) -> str:
    path = path.strip().replace("\\", "/")
    if not path:
        raise PrinterControlError("Kein G-Code-Pfad.")
    if path.startswith("printprt:"):
        path = path[len("printprt:") :]
    if not path.startswith("/"):
        path = f"/mnt/UDISK/printer_data/gcodes/{path.lstrip('/')}"
    return path


def resolve_gcode_print_path(gcode_path: str, file_entry: dict[str, Any] | None = None) -> str:
    """Vollständigen Drucker-Pfad (wie in der Dateiliste / Creality Print)."""
    if file_entry:
        raw = str(file_entry.get("path") or "").strip().replace("\\", "/")
        if raw:
            if raw.startswith("printprt:"):
                raw = raw[len("printprt:") :]
            if raw.startswith("/"):
                return raw
        try:
            return entry_remote_path(file_entry)
        except ValueError:
            pass
    return normalize_gcode_path(gcode_path)


def cfs_connected(state: dict[str, Any]) -> bool:
    if int(state.get("cfsConnect") or 0) == 1:
        return True
    bi = _find_boxs_info(state)
    if isinstance(bi, dict) and int(bi.get("enable") or 0) == 1:
        return True
    for box in _material_boxes_raw(bi, state):
        if box.get("type") == 0 and int(box.get("state") or 0) == 1:
            return True
    return False


def _material_boxes_raw(bi: dict[str, Any] | None, state: dict[str, Any]) -> list[dict[str, Any]]:
    from creality_nfc.cfs_adopt import _material_boxes

    if isinstance(bi, dict):
        return _material_boxes(bi, state)
    return []


def get_cfs_box_id(state: dict[str, Any]) -> int:
    bi = _find_boxs_info(state)
    if isinstance(bi, dict):
        for box in _material_boxes_raw(bi, state):
            if box.get("type") == 0:
                try:
                    return int(box.get("id", 1))
                except (TypeError, ValueError):
                    return 1
    return 1


def _normalize_color(color: str) -> str:
    c = (color or "").strip()
    if not c:
        return "#FFFFFF"
    if not c.startswith("#"):
        c = f"#{c}"
    return c


def slot_color_match_entry(
    slot_index: int,
    slot: CfsSlotInfo,
    *,
    box_id: int = 1,
    gcode_spec: GcodeFilamentSpec | None = None,
) -> dict[str, Any]:
    """Eintrag für colorMatch.list — Format wie Creality Print (id, boxId, materialId)."""
    letter = SLOT_LABELS[slot_index][-1] if 0 <= slot_index < len(SLOT_LABELS) else chr(65 + slot_index)
    gcode_color = gcode_spec.color_hex if gcode_spec else None
    gcode_type = (gcode_spec.material_type or "").strip() if gcode_spec else ""
    color = _normalize_color(gcode_color or slot.color_raw)
    ftype = gcode_type or (slot.material_type or "PLA").strip()
    entry: dict[str, Any] = {
        "id": f"T{box_id}{letter}",
        "boxId": box_id,
        "materialId": slot_index,
    }
    if ftype:
        entry["type"] = ftype
    if color and color != "#FFFFFF":
        entry["color"] = color
        entry["matchColor"] = color
    return entry


def pick_filament_slot(
    slots: list[CfsSlotInfo],
    *,
    preferred: int | None = None,
    active_index: int | None = None,
) -> int | None:
    if preferred is not None and 0 <= preferred < len(slots) and not slots[preferred].empty:
        return preferred
    if active_index is not None and 0 <= active_index < len(slots) and not slots[active_index].empty:
        return active_index
    for i, slot in enumerate(slots):
        if not slot.empty:
            return i
    return None


def build_color_match_list(
    state: dict[str, Any],
    gcode_path: str,
    slot_index: int,
    slot: CfsSlotInfo,
    *,
    box_id: int | None = None,
    gcode_mappings: list[tuple[int, GcodeFilamentSpec]] | None = None,
) -> list[dict[str, Any]]:
    """Farbe aus G-Code → CFS-Slot (ein- oder mehrfarbig)."""
    from creality_nfc.cfs_layout import parse_cfs_layout

    if box_id is None:
        box_id = getattr(slot, "box_id", None) or get_cfs_box_id(state)
    all_slots = parse_cfs_layout(state).all_slots()
    if gcode_mappings:
        out: list[dict[str, Any]] = []
        for flat_idx, spec in gcode_mappings:
            if 0 <= flat_idx < len(all_slots):
                s = all_slots[flat_idx]
                out.append(
                    slot_color_match_entry(
                        s.index,
                        s,
                        box_id=getattr(s, "box_id", None) or box_id,
                        gcode_spec=spec,
                    )
                )
        if out:
            return out
    spec = None
    if gcode_mappings:
        for flat_idx, sp in gcode_mappings:
            if flat_idx < len(all_slots) and all_slots[flat_idx].index == slot_index:
                spec = sp
                break
    return [slot_color_match_entry(slot_index, slot, box_id=box_id, gcode_spec=spec)]


def cfs_open(state: dict[str, Any]) -> bool:
    """CFS in Creality Print aktiv (open_cfs / enable)."""
    if int(state.get("cfsConnect") or 0) == 1:
        bi = _find_boxs_info(state)
        if isinstance(bi, dict):
            en = bi.get("enable")
            if en is not None and int(en) == 0:
                return False
        return True
    bi = _find_boxs_info(state)
    return isinstance(bi, dict) and int(bi.get("enable") or 0) == 1


def is_multicolor_device(state: dict[str, Any]) -> bool:
    """Wie Creality: boxColorInfo befüllt = Multicolor-Gerät."""
    bi = _find_boxs_info(state)
    if not isinstance(bi, dict):
        return False
    bci = bi.get("boxColorInfo")
    return isinstance(bci, list) and len(bci) > 0


def use_multicolor_print(state: dict[str, Any], match_list: list[dict[str, Any]]) -> bool:
    """
    multiColorPrint nur bei echt mehrfarbigem Job.
    Einfarbig am K2/CFS: colorMatch + opGcodeFile (printprt) — wie Creality Print.
    """
    del state  # reserviert für spätere Firmware-Heuristiken
    return len(match_list) > 1


def resolve_print_slot(
    state: dict[str, Any],
    *,
    preferred: int | None = None,
    gcode_path: str | None = None,
    file_entry: dict[str, Any] | None = None,
) -> tuple[int, CfsSlotInfo, list[tuple[int, GcodeFilamentSpec]]]:
    from creality_nfc.cfs_layout import parse_cfs_layout

    slots = parse_cfs_layout(state).all_slots()
    meta = parse_cfs_meta(state)
    gcode_maps: list[tuple[int, GcodeFilamentSpec]] = []
    if gcode_path:
        gcode_maps = resolve_slots_from_gcode(
            state, gcode_path, slots, file_entry=file_entry
        )
    gcode_idx = gcode_maps[0][0] if gcode_maps else None
    inferred: int | None = None
    if gcode_path and gcode_idx is None:
        inferred = infer_slot_from_gcode(gcode_path, slots)
    # Slicer-Farbe im G-Code hat Vorrang vor manuell angeklicktem Slot (wie Creality Print).
    if gcode_idx is not None:
        pick = gcode_idx
    elif preferred is not None:
        pick = preferred
    else:
        pick = inferred
    idx = pick_filament_slot(slots, preferred=pick, active_index=meta.active_index)
    if idx is None:
        raise PrinterControlError(
            "Kein Filament im CFS — Slot mit Material wählen (z. B. 1A oder 3B) oder Spule einlegen."
        )
    if not gcode_maps and gcode_path:
        gcode_maps = resolve_slots_from_gcode(
            state, gcode_path, slots, file_entry=file_entry
        )
    return idx, slots[idx], gcode_maps


def build_print_steps(
    gcode_path: str,
    state: dict[str, Any],
    *,
    slot_index: int | None = None,
    enable_self_test: int = 0,
    auto_feed: bool = False,
    file_entry: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], int, str, str]:
    """
    Druckbefehle in Reihenfolge (wie Creality Print).
    Rückgabe: (steps, slot_index, slot_label, mode) — mode „normal“ oder „multi“.
    """
    path = resolve_gcode_print_path(gcode_path, file_entry)
    info = merge_gcode_filament_info(state, path, file_entry=file_entry)
    if gcode_uses_external_spool(info, path):
        return (
            [{"opGcodeFile": f"printprt:{path}", "enableSelfTest": enable_self_test}],
            -1,
            "Spulenhalter",
            "external",
        )

    if not cfs_connected(state):
        return (
            [{"opGcodeFile": f"printprt:{path}", "enableSelfTest": enable_self_test}],
            -1,
            "—",
            "normal",
        )

    flat_idx, slot, gcode_maps = resolve_print_slot(
        state, preferred=slot_index, gcode_path=path, file_entry=file_entry
    )
    box_id = getattr(slot, "box_id", None) or get_cfs_box_id(state)
    material_id = slot.index
    steps: list[dict[str, Any]] = []
    if int(state.get("materialStatus", 0) or 0) == 1:
        steps.append({"repoPlrStatus": 0})

    need_feed = not filament_ready_in_extruder(state, material_id, box_id=box_id)
    if need_feed and auto_feed:
        steps.append(
            {
                "boxConfig": {
                    "cAutoFeed": 1,
                    "autoRefill": 1,
                    "cSelfTest": 0,
                }
            },
        )
    if need_feed:
        steps.extend(build_preheat_params(info, gcode_path=path))

    match_list = build_color_match_list(
        state, path, material_id, slot, box_id=box_id, gcode_mappings=gcode_maps
    )
    steps.append({"colorMatch": {"path": path, "list": match_list}})

    # G-Code heizt/druckt — lädt aber nicht von CFS in den Extruder; das macht feedInOrOut.
    if need_feed:
        steps.append(
            {
                "feedInOrOut": {
                    "boxId": box_id,
                    "materialId": material_id,
                    "isFeed": 1,
                }
            }
        )
        steps.append({_WAIT_FILAMENT_KEY: {"boxId": box_id, "materialId": material_id}})

    if use_multicolor_print(state, match_list):
        steps.append({"multiColorPrint": {"gcode": path, "enableSelfTest": enable_self_test}})
        mode = "multi"
    else:
        steps.append({"opGcodeFile": f"printprt:{path}", "enableSelfTest": enable_self_test})
        mode = "normal"

    return steps, flat_idx, slot.label, mode


def cfs_feed_required_before_print(
    state: dict[str, Any],
    slot_index: int,
    *,
    box_id: int = 1,
) -> bool:
    """True wenn Zufuhr aus CFS nötig ist (nicht im G-Code enthalten)."""
    if not cfs_connected(state):
        return False
    return not filament_ready_in_extruder(state, slot_index, box_id=box_id)


def execute_print_steps(
    host: str,
    steps: list[dict[str, Any]],
    *,
    delay_s: float = 0.85,
    conn: Any | None = None,
    state_provider: Callable[[], dict[str, Any]] | None = None,
) -> None:
    """Befehle nacheinander senden (Zufuhr abwarten, dann Druck)."""
    from creality_nfc.printer_control import send_print_params

    provider = state_provider or (lambda: {})

    for i, params in enumerate(steps):
        wait_slot = params.get(_WAIT_FILAMENT_KEY)
        if wait_slot is not None:
            if isinstance(wait_slot, dict):
                wait_filament_ready(
                    int(wait_slot.get("materialId", 0)),
                    provider,
                    timeout_s=90.0,
                    box_id=int(wait_slot.get("boxId", 1) or 1),
                )
            else:
                wait_filament_ready(int(wait_slot), provider, timeout_s=90.0)
            time.sleep(1.0)
            continue
        if conn is not None and getattr(conn, "connected", False):
            conn.send_set(**params)
            if "nozzleTempControl" in params or "bedTempControl" in params:
                time.sleep(0.35)
            else:
                time.sleep(0.55)
        else:
            send_print_params(host, params, None)
        if i + 1 < len(steps):
            nxt = steps[i + 1]
            if _WAIT_FILAMENT_KEY in nxt:
                time.sleep(0.5)
            elif "colorMatch" in params:
                time.sleep(max(delay_s, 1.2))
            else:
                time.sleep(delay_s)


def send_print_start(
    send: Callable[..., None],
    gcode_path: str,
    state: dict[str, Any],
    *,
    slot_index: int | None = None,
    enable_self_test: int = 0,
    auto_feed: bool = False,
    host: str | None = None,
    conn: Any | None = None,
    state_provider: Callable[[], dict[str, Any]] | None = None,
) -> tuple[int, str]:
    """
    Druck starten. Mit host: sequentiell wie Creality App; sonst über send()-Callback.
    """
    steps, idx, label, _mode = build_print_steps(
        gcode_path,
        state,
        slot_index=slot_index,
        enable_self_test=enable_self_test,
        auto_feed=auto_feed,
    )
    if host:
        provider = state_provider
        if provider is None and conn is not None:
            provider = conn.snapshot
        execute_print_steps(host, steps, conn=conn, state_provider=provider)
        return idx, label
    for params in steps:
        send(**params)
    return idx, label
