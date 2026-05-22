"""Live-Schätzung Filamentverbrauch während des Drucks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from creality_nfc.cfs_adopt import CfsSlotInfo
from creality_nfc.cfs_layout import cfs_slot_label
from creality_nfc.gcode_filament import estimate_grams_for_slot, total_job_filament_grams


def _remaining_time_hint(state: dict[str, Any], progress_pct: int) -> str:
    """Restzeit aus Drucker-Telemetrie, falls vorhanden."""
    for key in ("printLeftTime", "print_left_time", "leftTime", "remaining_time"):
        raw = state.get(key)
        if raw is None:
            continue
        try:
            sec = int(float(raw))
        except (TypeError, ValueError):
            continue
        if sec <= 0:
            return ""
        if sec < 90:
            return f"noch ca. {sec} s"
        mins = sec // 60
        if mins < 120:
            return f"noch ca. {mins} min"
        return f"noch ca. {mins // 60} h {mins % 60} min"
    return ""


def format_live_filament_status(
    state: dict[str, Any],
    *,
    filename: str,
    progress_pct: int | None,
    active_slot: int | None,
    cfs_slots: list[CfsSlotInfo] | None,
    local_gcode: Path | None = None,
    spool_remaining_g: int | None = None,
    active_box_id: int = 1,
) -> str:
    """
    Kurztext für die Druck-Leiste (Monitor-Tab).
    """
    if not filename or progress_pct is None or progress_pct < 1:
        return ""
    entry = None
    try:
        from creality_nfc.gcode_filament import find_gcode_file_info

        entry = find_gcode_file_info(state, filename)
    except Exception:
        pass

    job = total_job_filament_grams(
        state,
        filename,
        file_entry=entry,
        local_path=local_gcode,
    )
    if not job:
        return "Filament: Schätzung aus G-Code nicht verfügbar"
    total_g, _src = job
    if total_g < 1:
        return ""
    pct = max(0, min(100, int(progress_pct)))
    used = int(round(total_g * pct / 100.0))
    left_job = max(0, total_g - used)

    parts = [f"ca. {used} g verbraucht", f"noch ca. {left_job} g bis Job-Ende"]

    eta = _remaining_time_hint(state, pct)
    if eta:
        parts.append(eta)

    if active_slot is not None and 0 <= active_slot <= 3:
        slot_est = estimate_grams_for_slot(
            state,
            filename,
            active_slot,
            cfs_slots,
            file_entry=entry,
            local_path=local_gcode,
        )
        lab = cfs_slot_label(active_box_id, active_slot)
        if slot_est:
            sg, _ = slot_est
            slot_used = int(round(sg * pct / 100.0))
            slot_left = max(0, sg - slot_used)
            parts.append(f"Slot {lab}: ca. {slot_used}/{sg} g (noch ca. {slot_left} g)")
        else:
            parts.append(f"aktiver Slot {lab}")

    if spool_remaining_g is not None:
        after = max(0, spool_remaining_g - used)
        parts.append(f"Rest Spule danach ca. {after} g")
        if left_job > 0 and spool_remaining_g < left_job:
            parts.append("⚠ Rest evtl. knapp für Job-Ende")

    return " · ".join(parts)
