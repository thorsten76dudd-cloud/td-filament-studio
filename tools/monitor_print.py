#!/usr/bin/env python3
"""Druck am K2 beobachten (WebSocket) — Log für längere Abwesenheit."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from creality_nfc.cfs_adopt import parse_cfs_slots
from creality_nfc.cfs_feed import resolve_live_filament_slot_index
from creality_nfc.live_filament import format_live_filament_status
from creality_nfc.printer_state import format_print_phase_log, print_job_phase, print_status
from creality_nfc.printer_ws import PrinterConnection

POLL_SEC = 120
MAX_HOURS = 6
INSTALL_DATA = Path.home() / "AppData/Local/Programs/TD Filament Studio/data"


def _load_host(cli_host: str) -> str:
    if cli_host.strip():
        return cli_host.strip()
    for base in (INSTALL_DATA, ROOT / "data"):
        path = base / "printers.json"
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        printers = data.get("printers") or []
        if printers and printers[0].get("host"):
            return str(printers[0]["host"]).strip()
    raise SystemExit("Kein Drucker in printers.json (oder --host angeben)")


def _log(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with path.open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] {line}\n")
    print(f"[{ts}] {line}")


def _live_filament_line(state: dict, ps: dict) -> str:
    fname = Path(str(ps.get("file") or "")).name
    prog = ps.get("progress")
    if not fname or prog is None:
        return ""
    try:
        from app.paths import GCODE_CACHE_DIR
    except ImportError:
        GCODE_CACHE_DIR = ROOT / "data" / "gcode_cache"
    local = GCODE_CACHE_DIR / fname
    if not local.is_file():
        alt = GCODE_CACHE_DIR / fname.replace(".stl_", "_").replace("1A.stl", "1A")
        if alt.is_file():
            local = alt
        else:
            local = None
    slots = parse_cfs_slots(state)
    slot_idx = resolve_live_filament_slot_index(state, fname, slots)
    text = format_live_filament_status(
        state,
        filename=fname,
        progress_pct=int(prog),
        active_slot=slot_idx,
        cfs_slots=slots,
        local_gcode=local if local and local.is_file() else None,
    )
    return text or "(Live-Verbrauch noch nicht berechenbar)"


def _gcode_summary(state: dict) -> str:
    for key in ("retGcodeFileInfo2", "retGcodeFileInfo3", "retGcodeFileInfo"):
        entries = state.get(key)
        if not isinstance(entries, list) or not entries:
            continue
        e = entries[0] if isinstance(entries[0], dict) else {}
        name = e.get("name") or ""
        colors = e.get("materialColors") or ""
        fw = e.get("filamentWeight") or ""
        used = e.get("materialUsed") or ""
        return f"meta {key}: name={name!r} colors={colors!r} fw={fw!r} used={used!r}"
    return "meta: (keine retGcodeFileInfo)"


def main() -> int:
    ap = argparse.ArgumentParser(description="K2-Druck per WebSocket loggen")
    ap.add_argument("--host", default="", help="Drucker-IP (sonst printers.json)")
    ap.add_argument(
        "--interval",
        type=int,
        default=POLL_SEC,
        help=f"Sekunden zwischen Log-Zeilen (Standard {POLL_SEC})",
    )
    args = ap.parse_args()
    poll_sec = max(15, int(args.interval))
    host = _load_host(args.host)
    log_path = ROOT / "data" / "print_monitor.log"
    _log(log_path, f"Monitor start — {host} (alle {poll_sec} s)")

    conn = PrinterConnection(host)
    conn.start()
    deadline = time.monotonic() + MAX_HOURS * 3600
    last_phase = ""
    last_prog = -1

    try:
        while time.monotonic() < deadline:
            for _ in range(30):
                time.sleep(0.5)
                if conn.connected and conn.has_received():
                    break
            if not conn.connected:
                _log(log_path, f"WS nicht verbunden: {conn.last_error or 'unbekannt'}")
                time.sleep(poll_sec)
                continue

            snap = conn.snapshot()
            ps = print_status(snap)
            phase = print_job_phase(snap)
            fname = Path(str(ps.get("file") or "")).name
            prog = ps.get("progress")
            layer = ps.get("cur_layer")
            tot = ps.get("total_layer")
            left = ps.get("left_sec")

            if phase != last_phase or prog != last_prog:
                live = _live_filament_line(snap, ps)
                _log(
                    log_path,
                    f"{phase} | {fname or '?'} | {prog}% | Layer {layer}/{tot} | "
                    f"rest ~{left}s | {format_print_phase_log(snap, phase)} | "
                    f"live: {live} | {_gcode_summary(snap)}",
                )
                last_phase = phase
                last_prog = prog if prog is not None else last_prog

            if phase in ("complete", "idle") and prog is not None and int(prog) >= 99:
                _log(log_path, "Druck offenbar fertig — Monitor beendet.")
                _log(log_path, _gcode_summary(snap))
                return 0

            if phase == "idle" and last_phase == "printing" and (prog or 0) >= 95:
                _log(log_path, "Druck beendet (idle nach printing).")
                return 0

            time.sleep(poll_sec)
    finally:
        conn.stop()

    _log(log_path, "Monitor Zeitlimit erreicht.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
