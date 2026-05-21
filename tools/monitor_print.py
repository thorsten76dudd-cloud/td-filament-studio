#!/usr/bin/env python3
"""Druck am K2 beobachten (WebSocket) — Log für längere Abwesenheit."""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from creality_nfc.printer_state import format_print_phase_log, print_job_phase, print_status
from creality_nfc.printer_ws import PrinterConnection

POLL_SEC = 120
MAX_HOURS = 6
INSTALL_DATA = Path.home() / "AppData/Local/Programs/TD Filament Studio/data"


def _load_host() -> str:
    for base in (INSTALL_DATA, ROOT / "data"):
        path = base / "printers.json"
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        printers = data.get("printers") or []
        if printers and printers[0].get("host"):
            return str(printers[0]["host"]).strip()
    raise SystemExit("Kein Drucker in printers.json")


def _log(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with path.open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] {line}\n")
    print(f"[{ts}] {line}")


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
    host = _load_host()
    log_path = ROOT / "data" / "print_monitor.log"
    _log(log_path, f"Monitor start — {host}")

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
                time.sleep(POLL_SEC)
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
                _log(
                    log_path,
                    f"{phase} | {fname or '?'} | {prog}% | Layer {layer}/{tot} | "
                    f"rest ~{left}s | {format_print_phase_log(snap, phase)} | "
                    f"{_gcode_summary(snap)}",
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

            time.sleep(POLL_SEC)
    finally:
        conn.stop()

    _log(log_path, "Monitor Zeitlimit erreicht.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
