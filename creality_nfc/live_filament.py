"""Live-Schätzung Filamentverbrauch während des Drucks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from creality_nfc.cfs_adopt import CfsSlotInfo, SLOT_LABELS
from creality_nfc.gcode_filament import estimate_grams_for_slot, total_job_filament_grams


def format_live_filament_status(
    state: dict[str, Any],
    *,
    filename: str,
    progress_pct: int | None,
    active_slot: int | None,
    cfs_slots: list[CfsSlotInfo] | None,
    local_gcode: Path | None = None,
    spool_remaining_g: int | None = None,
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

    if active_slot is not None and 0 <= active_slot <= 3:
        slot_est = estimate_grams_for_slot(
            state,
            filename,
            active_slot,
            cfs_slots,
            file_entry=entry,
            local_path=local_gcode,
        )
        lab = SLOT_LABELS[active_slot]
        if slot_est:
            sg, _ = slot_est
            slot_used = int(round(sg * pct / 100.0))
            parts.append(f"Slot {lab}: ca. {slot_used}/{sg} g")
        else:
            parts.append(f"aktiver Slot {lab}")

    if spool_remaining_g is not None:
        after = max(0, spool_remaining_g - used)
        parts.append(f"Rest Spule danach ca. {after} g")

    return " · ".join(parts)
