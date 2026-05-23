#!/usr/bin/env python3
"""Einmaliger Druck-Status (WebSocket)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.paths import GCODE_CACHE_DIR
from creality_nfc.cfs_adopt import parse_cfs_slots
from creality_nfc.cfs_feed import resolve_live_filament_slot_index
from creality_nfc.live_filament import format_live_filament_status
from creality_nfc.printer_state import format_print_phase_log, print_job_phase, print_status
from creality_nfc.printer_ws import PrinterConnection


def main() -> int:
    host = sys.argv[1] if len(sys.argv) > 1 else "192.168.178.136"
    conn = PrinterConnection(host)
    conn.start()
    for _ in range(40):
        time.sleep(0.25)
        if conn.connected and conn.has_received():
            break
    if not conn.connected:
        print("nicht verbunden:", conn.last_error)
        return 1
    snap = conn.snapshot()
    ps = print_status(snap)
    phase = print_job_phase(snap)
    fname = Path(str(ps.get("file") or "")).name
    prog = ps.get("progress")
    slots = parse_cfs_slots(snap)
    slot = resolve_live_filament_slot_index(snap, fname, slots)
    local = GCODE_CACHE_DIR / fname
    live = format_live_filament_status(
        snap,
        filename=fname,
        progress_pct=int(prog or 0),
        active_slot=slot,
        cfs_slots=slots,
        local_gcode=local if local.is_file() else None,
    )
    print(f"phase={phase} file={fname} progress={prog}% layer={ps.get('cur_layer')}/{ps.get('total_layer')} left={ps.get('left_sec')}s")
    print(f"fw={format_print_phase_log(snap, phase)}")
    print(f"live={live or '-'}")
    conn.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
