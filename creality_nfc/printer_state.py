"""Telemetrie vom K2 normalisieren (verschiedene Firmware-Feldnamen)."""

from __future__ import annotations

from typing import Any


def _coerce_numbers(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in d.items():
        if isinstance(v, str):
            try:
                out[k] = float(v) if "." in v else int(v)
                continue
            except ValueError:
                pass
        out[k] = v
    return out


def _first(state: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in state and state[key] is not None:
            return state[key]
    return None


def normalize_telemetry(payload: dict[str, Any]) -> dict[str, Any]:
    """Flache WS-Nachricht; Zahlenstrings → Zahlen; Alias-Felder ergänzen."""
    flat: dict[str, Any] = {}
    if isinstance(payload, dict):
        flat.update(_coerce_numbers(payload))
        inner = payload.get("data") or payload.get("params") or payload.get("result")
        if isinstance(inner, dict):
            flat.update(_coerce_numbers(inner))

    out = dict(flat)
    cur_n = _first(flat, "nozzleTemp", "curNozzleTemp", "nozzle_temp")
    tgt_n = _first(flat, "targetNozzleTemp", "targetNozzleTemp0")
    if cur_n is not None:
        out.setdefault("curNozzleTemp", cur_n)
    if tgt_n is not None:
        out.setdefault("targetNozzleTemp", tgt_n)

    cur_b = _first(flat, "bedTemp0", "curBedTemp0", "bedTemp", "curBedTemp")
    tgt_b = _first(flat, "targetBedTemp0", "targetBedTemp")
    if cur_b is not None:
        out.setdefault("curBedTemp0", cur_b)
    if tgt_b is not None:
        out.setdefault("targetBedTemp0", tgt_b)

    cur_box = _first(flat, "boxTemp", "curBoxTemp", "chamberTemp")
    tgt_box = _first(flat, "targetBoxTemp", "targetChamberTemp")
    if cur_box is not None:
        out.setdefault("boxTemp", cur_box)
    if tgt_box is not None:
        out.setdefault("targetBoxTemp", tgt_box)

    layer = _first(flat, "layer", "curLayer", "currentLayer")
    total = _first(flat, "TotalLayer", "totalLayer", "totalLayers")
    if layer is not None:
        out.setdefault("curLayer", layer)
    if total is not None:
        out.setdefault("totalLayer", total)

    prog = _first(flat, "printProgress", "dProgress", "progress")
    if prog is not None:
        out.setdefault("printProgress", prog)

    cur_fan = _first(flat, "modelFanPct", "fan", "modelFan", "fanModel")
    case_fan = _first(flat, "caseFanPct", "fanCase", "caseFan")
    aux_fan = _first(flat, "auxiliaryFanPct", "fanAuxiliary", "auxiliaryFan", "sideFanPct")
    if cur_fan is not None:
        out.setdefault("modelFanPct", cur_fan)
    if case_fan is not None:
        out.setdefault("caseFanPct", case_fan)
    if aux_fan is not None:
        out.setdefault("auxiliaryFanPct", aux_fan)

    for key in (
        "boxsInfo",
        "retBoxsInfo",
        "retGcodeFileInfo",
        "retGcodeFileInfo2",
        "retGcodeFileInfo3",
        "fileInfo",
        "cfsConnect",
    ):
        if key in flat and isinstance(flat[key], (dict, list, str)):
            out[key] = flat[key]
        if isinstance(payload, dict) and key in payload and key not in out:
            val = payload[key]
            if isinstance(val, (dict, list, str)):
                out[key] = val
        inner = payload.get("data") if isinstance(payload, dict) else None
        if isinstance(inner, dict) and key in inner and key not in out:
            val = inner[key]
            if isinstance(val, (dict, list, str)):
                out[key] = val

    return out


def telemetry_temperatures(state: dict[str, Any]) -> tuple[Any, Any, Any, Any, Any, Any]:
    """(düse ist, düse soll, bett ist, bett soll, kammer ist, kammer soll)."""
    return (
        _first(state, "curNozzleTemp", "nozzleTemp", "nozzle_temp"),
        _first(state, "targetNozzleTemp", "targetNozzleTemp0"),
        _first(state, "curBedTemp0", "bedTemp0", "curBedTemp", "bedTemp"),
        _first(state, "targetBedTemp0", "targetBedTemp"),
        _first(state, "boxTemp", "curBoxTemp", "chamberTemp"),
        _first(state, "targetBoxTemp", "targetChamberTemp"),
    )


def temp_target_spinbox_value(
    current: int,
    reported: Any,
    *,
    locked: bool,
    job_active: bool = False,
) -> int | None:
    """Soll-Temperatur für UI-Spinbox; None = Wert nicht ändern."""
    if locked or reported is None:
        return None
    try:
        value = int(round(float(reported)))
    except (TypeError, ValueError):
        return None
    # K2 meldet bei CFS-Zufuhr/Druckstart oft target=0 — Spinbox nicht zurücksetzen.
    if value == 0 and (current > 0 or job_active):
        return None
    if current == value:
        return None
    return value


def telemetry_fans(state: dict[str, Any]) -> tuple[Any, Any, Any]:
    """Modell-, Gehäuse-, Hilfs-Lüfter in Prozent."""
    return (
        _first(state, "modelFanPct", "fan", "modelFan"),
        _first(state, "caseFanPct", "fanCase", "caseFan"),
        _first(state, "auxiliaryFanPct", "fanAuxiliary", "auxiliaryFan", "sideFanPct"),
    )


def payload_has_live_telemetry(payload: dict[str, Any]) -> bool:
    merged = normalize_telemetry(payload)
    for key in merged:
        kl = key.lower()
        if "temp" in kl or "fan" in kl:
            return True
    return False


def payload_has_live_ui_update(payload: dict[str, Any]) -> bool:
    """Temperatur, Fortschritt, CFS — alles was die Live-Ansicht braucht."""
    if payload_has_meaningful_refresh(payload):
        return True
    if not isinstance(payload, dict):
        return False
    merged = normalize_telemetry(payload)
    for key in merged:
        kl = key.lower()
        if any(
            token in kl
            for token in (
                "boxsinfo",
                "cfsconnect",
            )
        ):
            return True
    return False


def payload_has_print_refresh(payload: dict[str, Any]) -> bool:
    """Druckfortschritt / Job-Status (nicht nur Temperatur)."""
    if not isinstance(payload, dict):
        return False
    merged = normalize_telemetry(payload)
    for key in merged:
        kl = key.lower()
        if any(
            token in kl
            for token in (
                "printprogress",
                "dprogress",
                "deviceState",
                "printstate",
                "printfilename",
                "print_file_name",
                "curlayer",
                "totallayer",
                "printtimeleft",
                "printlefttime",
                "printusedtime",
                "printtotaltime",
            )
        ):
            return True
        if kl in ("state", "progress", "layer"):
            return True
    return False


def payload_has_meaningful_refresh(payload: dict[str, Any]) -> bool:
    """
    Echte Live-Aktualisierung (Temperatur/Lüfter oder Druckstatus).
    Nur CFS/material in Heartbeats zählt NICHT — sonst werden keine GETs mehr gesendet.
    """
    if payload_has_live_telemetry(payload) or payload_has_print_refresh(payload):
        return True
    return False


def _seconds_left(state: dict[str, Any]) -> float | None:
    left = _first(state, "printTimeLeft", "printLeftTime", "leftTime", "printLeft")
    if left is None:
        return None
    try:
        v = float(left)
        return v if v >= 0 else None
    except (TypeError, ValueError):
        return None


def _is_heating_for_print(state: dict[str, Any]) -> bool:
    """Düse/Bett heizen — oft vor neuem Druck, während Fortschritt noch 100 % ist."""
    n_cur, n_tgt, b_cur, b_tgt, _, _ = telemetry_temperatures(state)
    try:
        if n_tgt is not None and n_cur is not None and float(n_tgt) - float(n_cur) > 8:
            return True
        if b_tgt is not None and b_cur is not None and float(b_tgt) - float(b_cur) > 3:
            return True
    except (TypeError, ValueError):
        pass
    return False


def print_job_phase(state: dict[str, Any]) -> str:
    """
    Drucker-Job-Phase für Steuer-Buttons (K2 WebSocket state / deviceState).
    idle | printing | paused | complete | error
    """
    try:
        st = int(_first(state, "state", "deviceState", "printState") or 0)
    except (TypeError, ValueError):
        st = 0
    try:
        prog = int(round(float(_first(state, "printProgress", "dProgress", "progress") or 0)))
    except (TypeError, ValueError):
        prog = 0
    has_job = bool(
        str(_first(state, "printFileName", "print_file_name") or "").strip()
    )
    if int(state.get("aiPausePrint", 0) or 0) == 1 or st == 5:
        return "paused"
    if st == 3:
        return "error"

    # Firmware: aktiv druckend — vor „100 % = fertig“ prüfen
    if st == 1:
        return "printing"

    left_s = _seconds_left(state)
    if has_job and left_s is not None and left_s > 15:
        return "printing"

    try:
        cl = int(_first(state, "curLayer", "layer") or 0)
        tl = int(_first(state, "totalLayer", "totalLayers", "TotalLayer") or 0)
        if has_job and tl > 0 and cl < tl:
            return "printing"
    except (TypeError, ValueError):
        pass

    if has_job and _is_heating_for_print(state):
        return "printing"

    if st == 2:
        return "complete"

    if prog > 0 and prog < 100 and has_job:
        return "printing"

    if prog >= 100 and has_job:
        return "complete"

    return "idle"


def print_status(state: dict[str, Any]) -> dict[str, Any]:
    """Druck-Fortschritt für die Statusleiste."""
    prog = _first(state, "printProgress", "dProgress", "progress")
    try:
        prog_i = int(round(float(prog))) if prog is not None else None
    except (TypeError, ValueError):
        prog_i = None
    cur_l = _first(state, "curLayer", "layer")
    tot_l = _first(state, "totalLayer", "totalLayers", "TotalLayer")
    left = _first(state, "printTimeLeft", "printLeftTime", "leftTime")
    used = _first(state, "printUsedTime", "usedTime", "printJobTime")
    total = _first(state, "printTotalTime", "totalTime")
    fname = _first(state, "printFileName", "print_file_name") or ""
    return {
        "file": str(fname).strip(),
        "progress": prog_i,
        "cur_layer": cur_l,
        "total_layer": tot_l,
        "left_sec": left,
        "used": used,
        "total": total,
    }
