"""K2 Steuerbefehle (WebSocket Port 9999)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from creality_nfc.printer_ws import PrinterConnection

from creality_nfc.printer_camera import normalize_host
from creality_nfc.printer_ws import PrinterWsError, request_get_once, send_set_once

WS_PORT = 9999


class PrinterControlError(PrinterWsError):
    pass


def _set(host: str, **params: Any) -> None:
    try:
        send_set_once(host, **params)
    except Exception as exc:
        raise PrinterControlError(str(exc)) from exc


def light_on(host: str) -> None:
    _set(host, lightSw=1)


def light_off(host: str) -> None:
    _set(host, lightSw=0)


def pause_print(host: str, *, state: dict | None = None) -> None:
    _set(host, pause=1)


def resume_print(host: str, *, state: dict | None = None) -> None:
    """Fortsetzen — wie Creality Print (pause:0 oder repoPlrStatus bei Filament-Fehler)."""
    snap = state or {}
    if int(snap.get("repoPlrStatus", 0) or 0) == 1 or int(snap.get("materialStatus", 0) or 0) == 1:
        _set(host, repoPlrStatus=1)
    else:
        _set(host, pause=0)


def send_print_params(
    host: str,
    params: dict,
    conn: "PrinterConnection | None" = None,
    *,
    wait_flush: bool = False,
) -> None:
    """Befehl über Dauer-WS (bevorzugt) oder Einzelverbindung."""
    import time

    if conn is not None and getattr(conn, "connected", False):
        conn.send_set(**params)
        if wait_flush:
            time.sleep(0.35)
        return
    send_set_once(host, timeout=15.0, **params)


def stop_print(host: str) -> None:
    _set(host, stop=1)


def feed_filament(
    host: str,
    box_id: int,
    material_id: int,
    conn: "PrinterConnection | None" = None,
) -> None:
    """Filament aus CFS-Slot in den Extruder laden (Creality: feedInOrOut)."""
    send_print_params(
        host,
        {"feedInOrOut": {"boxId": int(box_id), "materialId": int(material_id), "isFeed": 1}},
        conn,
    )


def retract_filament(
    host: str,
    box_id: int,
    material_id: int,
    conn: "PrinterConnection | None" = None,
) -> None:
    send_print_params(
        host,
        {"feedInOrOut": {"boxId": int(box_id), "materialId": int(material_id), "isFeed": 0}},
        conn,
    )


def clear_filament_error(host: str, conn: "PrinterConnection | None" = None) -> None:
    """Filament-Fehler (TR0116 / materialStatus) zurücksetzen."""
    send_print_params(host, {"repoPlrStatus": 0}, conn)


def set_fan(host: str, channel: int, percent: int) -> None:
    pct = max(0, min(100, int(percent)))
    s_val = int(round(255 * (pct / 100.0)))
    _set(host, gcodeCmd=f"M106 P{channel} S{s_val}")


# Wie Creality Print Geräte-Tab (Silent / Stabil / Standard / Ultrafast)
PRINT_SPEED_PRESETS: tuple[tuple[int, str], ...] = (
    (25, "Silent"),
    (50, "Stabil 50%"),
    (100, "Standard 100%"),
    (125, "Ultrafast 125%"),
)


def set_print_speed(host: str, percent: int) -> None:
    """K2: 25 % = speedMode 1; sonst speedMode 0 + setFeedratePct (Creality Print LAN)."""
    v = int(percent)
    if v == 25:
        _set(host, speedMode=1)
    else:
        _set(host, speedMode=0, setFeedratePct=v)


def start_gcode_print(
    host: str,
    path: str,
    *,
    self_test: bool = False,
    state: dict | None = None,
    slot_index: int | None = None,
) -> None:
    from creality_nfc.print_cfs import send_print_start
    from creality_nfc.printer_ws import fetch_ws_snapshot

    snap = state if state is not None else fetch_ws_snapshot(host, timeout=6.0, boxsInfo=1)
    send_print_start(
        lambda **kw: _set(host, **kw),
        path,
        snap,
        slot_index=slot_index,
        enable_self_test=1 if self_test else 0,
        host=host,
        conn=None,
    )


def delete_gcode_file(host: str, remote_path: str, conn: "PrinterConnection | None" = None) -> None:
    """G-Code auf dem Drucker löschen (Creality: opGcodeFile deleteprt:…)."""
    path = remote_path.strip().replace("\\", "/")
    if path.startswith("deleteprt:"):
        path = path[len("deleteprt:") :]
    if not path.startswith("/"):
        path = f"/usr/data/printer_data/gcodes/{path.lstrip('/')}"
    send_print_params(host, {"opGcodeFile": f"deleteprt:{path}"}, conn)


def request_gcode_list(host: str) -> None:
    request_get_once(
        host,
        reqGcodeList=1,
        reqGcodeFile=1,
        reqGcodeFileInfo=1,
        reqGcodeFileInfo2=1,
    )



def set_nozzle_temp(host: str, celsius: int) -> None:
    _set(host, nozzleTempControl=int(celsius))


def set_bed_temp(host: str, celsius: int, bed_index: int = 0) -> None:
    _set(host, bedTempControl={"num": bed_index, "val": int(celsius)})


def set_chamber_temp(host: str, celsius: int) -> None:
    _set(host, boxTempControl=int(celsius))


def home_xy(host: str) -> None:
    _set(host, autohome="X Y")


def home_z(host: str) -> None:
    _set(host, autohome="Z")
