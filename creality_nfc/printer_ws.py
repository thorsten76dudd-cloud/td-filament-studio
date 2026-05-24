"""Dauer-WebSocket zum K2 (Port 9999) — Telemetrie + Befehle."""

from __future__ import annotations

import json
import queue
import threading
import time
from collections.abc import Callable
from typing import Any

from creality_nfc.printer_camera import normalize_host
from creality_nfc.printer_state import (
    normalize_telemetry,
    payload_has_live_telemetry,
    payload_has_live_ui_update,
    payload_has_meaningful_refresh,
    payload_has_print_refresh,
    print_state_signature,
)

WS_PORT = 9999
GET_PRINTER_PARA_SEC = 0.3
GET_PRINT_OBJECTS_SEC = 0.4
GET_PRINT_PROGRESS_SEC = 0.3
GET_BOXS_INFO_SEC = 3.0
GET_LIVE_COMBINED_SEC = 2.0
PRINT_STALE_NUDGE_SEC = 4.0
RECV_STALE_SEC = 15.0

_LIVE_GET_PARAMS = {"ReqPrinterPara": 1, "reqPrintObjects": 1}


class PrinterWsError(RuntimeError):
    pass


class PrinterConnection:
    """Hält WS-Verbindung im Hintergrund; Status thread-safe abrufbar."""

    def __init__(self, host: str) -> None:
        self.host = normalize_host(host)
        self._state: dict[str, Any] = {}
        self._lock = threading.Lock()
        self._cmd_queue: queue.Queue[dict[str, Any]] = queue.Queue()
        self._get_queue: queue.Queue[dict[str, Any]] = queue.Queue()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._connected = False
        self._last_error = ""
        self._listeners: list[Callable[[dict[str, Any]], None]] = []
        self._listener_lock = threading.Lock()
        self._ws_lock = threading.Lock()
        self._ws: Any = None
        self._last_recv_at = 0.0
        self._last_state_at = 0.0
        self._last_meaningful_at = 0.0
        self._last_print_at = 0.0
        self._print_signature: tuple[Any, ...] | None = None

    @property
    def connected(self) -> bool:
        return self._connected

    def recv_idle_seconds(self) -> float:
        if self._last_recv_at <= 0:
            return 0.0
        return time.monotonic() - self._last_recv_at

    def state_age_seconds(self) -> float:
        """Alter der letzten inhaltlichen Telemetrie (nicht nur Heartbeat)."""
        return self.meaningful_idle_seconds()

    def meaningful_idle_seconds(self) -> float:
        if self._last_meaningful_at <= 0:
            return 999.0
        return time.monotonic() - self._last_meaningful_at

    def print_idle_seconds(self) -> float:
        if self._last_print_at <= 0:
            return 999.0
        return time.monotonic() - self._last_print_at

    def has_received(self) -> bool:
        return self._last_recv_at > 0

    def wait_for_live_telemetry(self, timeout: float = 8.0) -> bool:
        """Warten bis Temperatur/Lüfter in der WS-Antwort sind."""
        deadline = time.monotonic() + max(0.3, timeout)
        while time.monotonic() < deadline and not self._stop.is_set():
            if payload_has_live_telemetry(self.snapshot()):
                return True
            if self._connected:
                self.request_get(ReqPrinterPara=1, reqPrintObjects=1)
            time.sleep(0.18)
        return payload_has_live_telemetry(self.snapshot())

    @property
    def last_error(self) -> str:
        return self._last_error

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            out = dict(self._state)
        bi = out.get("boxsInfo")
        if isinstance(bi, str):
            merged = self._merge_boxs_info(None, bi)
            if isinstance(merged, dict):
                out["boxsInfo"] = merged
        return out

    def has_boxs_info(self) -> bool:
        from creality_nfc.cfs_adopt import parse_cfs_slots

        snap = self.snapshot()
        return any(not slot.empty for slot in parse_cfs_slots(snap))

    def wait_for_boxs_info(self, timeout: float = 4.0) -> bool:
        deadline = time.monotonic() + max(0.2, timeout)
        while time.monotonic() < deadline:
            if self.has_boxs_info():
                return True
            time.sleep(0.12)
        return self.has_boxs_info()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run_loop, name="k2-ws", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._connected = False
        with self._ws_lock:
            ws = self._ws
        if ws is not None:
            try:
                ws.close()
            except OSError:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.5)
        self._thread = None

    def send_set(self, **params: Any) -> None:
        self._cmd_queue.put(params)

    def request_get(self, **params: Any) -> None:
        self._get_queue.put(params)

    def merge_external(self, payload: dict[str, Any]) -> None:
        """Kurz-WebSocket-Abfrage (eigene Verbindung) in den laufenden Status."""
        if isinstance(payload, dict) and payload:
            self._update_state(payload)

    def add_listener(self, callback: Callable[[dict[str, Any]], None]) -> None:
        with self._listener_lock:
            if callback not in self._listeners:
                self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[dict[str, Any]], None]) -> None:
        with self._listener_lock:
            try:
                self._listeners.remove(callback)
            except ValueError:
                pass

    def _notify_listeners(self, *, live: bool = False) -> None:
        if not live or not self._listeners:
            return
        snap = self.snapshot()
        with self._listener_lock:
            listeners = list(self._listeners)
        for cb in listeners:
            try:
                cb(snap)
            except Exception:
                pass

    @staticmethod
    def _deep_merge_dict(prev: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
        out = dict(prev)
        for key, val in new.items():
            if key in out and isinstance(out[key], dict) and isinstance(val, dict):
                out[key] = PrinterConnection._deep_merge_dict(out[key], val)
            else:
                out[key] = val
        return out

    @staticmethod
    def _materials_list_has_data(mats: list) -> bool:
        for mat in mats:
            if not isinstance(mat, dict):
                continue
            for key in ("name", "vendor", "type", "color", "rfid"):
                v = mat.get(key)
                if v is not None and str(v).strip() not in ("", "0", "?", "—", "-"):
                    return True
        return False

    @staticmethod
    def _merge_materials_list(prev: list, new: list) -> list:
        if not PrinterConnection._materials_list_has_data(new):
            return list(prev) if prev else new
        by_id: dict[int, dict[str, Any]] = {}
        for idx, mat in enumerate(prev):
            if not isinstance(mat, dict):
                continue
            try:
                mid = int(mat.get("id", idx))
            except (TypeError, ValueError):
                mid = idx
            by_id[mid] = dict(mat)
        for idx, mat in enumerate(new):
            if not isinstance(mat, dict):
                continue
            try:
                mid = int(mat.get("id", idx))
            except (TypeError, ValueError):
                mid = idx
            if mid not in by_id:
                by_id[mid] = dict(mat)
                continue
            merged = dict(by_id[mid])
            for fk, fv in mat.items():
                if fk in ("name", "vendor", "type", "color", "rfid") and (
                    fv is None or str(fv).strip() in ("", "0", "?")
                ):
                    if str(merged.get(fk, "")).strip() not in ("", "0", "?"):
                        continue
                merged[fk] = fv
            by_id[mid] = merged
        return [by_id[k] for k in sorted(by_id)]

    @staticmethod
    def _merge_material_box(prev: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
        out = dict(prev)
        for key, val in new.items():
            if key == "materials" and isinstance(val, list):
                if not PrinterConnection._materials_list_has_data(val):
                    continue
                prev_m = out.get("materials")
                if isinstance(prev_m, list) and prev_m:
                    out["materials"] = PrinterConnection._merge_materials_list(prev_m, val)
                else:
                    out["materials"] = val
            else:
                out[key] = val
        return out

    @staticmethod
    def _merge_material_boxes(prev: list, new: list) -> list:
        by_id: dict[int, dict[str, Any]] = {}
        for box in prev:
            if not isinstance(box, dict):
                continue
            try:
                bid = int(box.get("id", 0))
            except (TypeError, ValueError):
                continue
            by_id[bid] = dict(box)
        for box in new:
            if not isinstance(box, dict):
                continue
            try:
                bid = int(box.get("id", 0))
            except (TypeError, ValueError):
                continue
            if bid in by_id:
                by_id[bid] = PrinterConnection._merge_material_box(by_id[bid], box)
            else:
                by_id[bid] = dict(box)
        return [by_id[k] for k in sorted(by_id)]

    @staticmethod
    def _merge_boxs_info_dict(prev: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
        out = dict(prev)
        for key, val in new.items():
            if key == "materialBoxs" and isinstance(val, list):
                prev_boxes = out.get("materialBoxs")
                if isinstance(prev_boxes, list) and prev_boxes:
                    out["materialBoxs"] = PrinterConnection._merge_material_boxes(prev_boxes, val)
                else:
                    out["materialBoxs"] = val
            elif key == "materialBoxes" and isinstance(val, list):
                prev_boxes = out.get("materialBoxes")
                if isinstance(prev_boxes, list) and prev_boxes:
                    out["materialBoxes"] = PrinterConnection._merge_material_boxes(prev_boxes, val)
                else:
                    out["materialBoxes"] = val
            elif isinstance(val, dict) and isinstance(out.get(key), dict):
                out[key] = PrinterConnection._merge_boxs_info_dict(out[key], val)
            else:
                out[key] = val
        return out

    @staticmethod
    def _boxs_info_from_payload(payload: dict[str, Any]) -> Any:
        for key in ("boxsInfo", "boxsinfo", "retBoxsInfo", "ret_boxs_info"):
            if key in payload:
                return payload[key]
        return None

    @staticmethod
    def _merge_boxs_info(prev: Any, new: Any) -> Any:
        if isinstance(new, str):
            text = new.strip()
            if text.startswith("{") or text.startswith("["):
                try:
                    new = json.loads(text)
                except json.JSONDecodeError:
                    return prev if prev is not None else new
        if isinstance(prev, str):
            try:
                prev = json.loads(prev.strip())
            except json.JSONDecodeError:
                prev = None
        if isinstance(new, dict) and isinstance(prev, dict):
            return PrinterConnection._merge_boxs_info_dict(prev, new)
        if isinstance(new, dict):
            return new
        if new is not None:
            return new
        return prev

    def _update_state(self, payload: dict[str, Any]) -> None:
        if not isinstance(payload, dict):
            return
        merged = normalize_telemetry(payload)
        merge_dict_keys = (
            "boxsInfo",
            "retGcodeFileInfo",
            "retGcodeFileInfo2",
            "retGcodeFileInfo3",
        )
        with self._lock:
            for key, val in merged.items():
                if key == "boxsInfo":
                    prev = self._state.get("boxsInfo")
                    self._state["boxsInfo"] = self._merge_boxs_info(prev, val)
                elif key in merge_dict_keys and isinstance(val, dict):
                    prev = self._state.get(key)
                    if isinstance(prev, dict):
                        self._state[key] = self._deep_merge_dict(prev, val)
                    else:
                        self._state[key] = val
                elif key in merge_dict_keys and isinstance(val, list) and val:
                    self._state[key] = val
                else:
                    self._state[key] = val
            raw_boxs = self._boxs_info_from_payload(payload)
            if raw_boxs is not None:
                prev = self._state.get("boxsInfo")
                self._state["boxsInfo"] = self._merge_boxs_info(prev, raw_boxs)
            for alt_key in ("retBoxsInfo",):
                alt_val = merged.get(alt_key)
                if alt_val is not None:
                    prev = self._state.get("boxsInfo")
                    self._state["boxsInfo"] = self._merge_boxs_info(prev, alt_val)
        now = time.monotonic()
        self._last_state_at = now
        if payload_has_meaningful_refresh(merged):
            self._last_meaningful_at = now
        if payload_has_print_refresh(merged):
            sig = print_state_signature(self.snapshot())
            if sig != self._print_signature:
                self._last_print_at = now
                self._print_signature = sig
        self._notify_listeners(live=True)

    def _mark_recv(self) -> None:
        self._last_recv_at = time.monotonic()

    @staticmethod
    def _is_recv_timeout(exc: BaseException) -> bool:
        name = type(exc).__name__
        if name in ("WebSocketTimeoutException", "TimeoutError"):
            return True
        return "timed out" in str(exc).lower()

    def _run_loop(self) -> None:
        try:
            import websocket
        except ImportError:
            self._last_error = "websocket-client fehlt (pip install websocket-client)"
            return

        url = f"ws://{self.host}:{WS_PORT}"
        while not self._stop.is_set():
            try:
                ws = websocket.create_connection(url, timeout=10)
                ws.settimeout(0.25)
                with self._ws_lock:
                    self._ws = ws
                self._connected = True
                self._last_error = ""
                self._mark_recv()
                last_live = last_cfs = last_gcode = last_prog = last_print_nudge = 0.0
                # Sofort Telemetrie + wartende GETs aus connect() (nicht erst in der Schleife).
                self._flush_get(
                    ws,
                    ReqPrinterPara=1,
                    reqPrintObjects=1,
                    boxsInfo=1,
                    reqGcodeList=1,
                    reqGcodeFile=1,
                    reqGcodeFileInfo2=1,
                )
                for _ in range(4):
                    if self._stop.is_set():
                        break
                    try:
                        raw = ws.recv()
                    except Exception as exc:
                        if not self._is_recv_timeout(exc):
                            break
                        continue
                    self._mark_recv()
                    if raw == "ok":
                        continue
                    if isinstance(raw, bytes):
                        raw = raw.decode("utf-8", "ignore")
                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(data, dict):
                        if data.get("ModeCode") == "heart_beat":
                            try:
                                ws.send("ok")
                            except OSError:
                                pass
                            inner = data.get("data")
                            if isinstance(inner, dict) and inner:
                                if payload_has_live_ui_update(inner):
                                    self._update_state(inner)
                        else:
                            self._update_state(data)
                    if payload_has_meaningful_refresh(self.snapshot()):
                        break
                    ws.send(
                        json.dumps(
                            {"method": "get", "params": {"ReqPrinterPara": 1}},
                            separators=(",", ":"),
                        )
                    )

                while not self._stop.is_set():
                    self._flush_commands(ws)
                    now = time.monotonic()
                    if now - last_live >= GET_LIVE_COMBINED_SEC:
                        self._send_get(ws, dict(_LIVE_GET_PARAMS))
                        last_live = now
                    print_idle = self.print_idle_seconds()
                    if (
                        print_idle >= PRINT_STALE_NUDGE_SEC
                        and now - last_print_nudge >= PRINT_STALE_NUDGE_SEC
                    ):
                        self._flush_get(ws, **_LIVE_GET_PARAMS)
                        last_print_nudge = now
                        last_live = now
                    try:
                        st = int(self._state.get("state", 0))
                    except (TypeError, ValueError):
                        st = 0
                    printing = st == 1
                    if printing and now - last_prog >= GET_PRINT_PROGRESS_SEC:
                        ws.send(
                            json.dumps(
                                {"method": "get", "params": {"reqPrintObjects": 1}},
                                separators=(",", ":"),
                            )
                        )
                        last_prog = now
                    if now - last_cfs >= GET_BOXS_INFO_SEC:
                        ws.send(
                            json.dumps(
                                {"method": "get", "params": {"boxsInfo": 1}},
                                separators=(",", ":"),
                            )
                        )
                        last_cfs = now
                    if (
                        self._last_recv_at > 0
                        and time.monotonic() - self._last_recv_at >= RECV_STALE_SEC
                    ):
                        break
                    if now - last_gcode >= 15.0:
                        ws.send(
                            json.dumps(
                                {
                                    "method": "get",
                                    "params": {"reqGcodeList": 1, "reqGcodeFile": 1},
                                },
                                separators=(",", ":"),
                            )
                        )
                        last_gcode = now

                    try:
                        raw = ws.recv()
                    except Exception as exc:
                        if not self._is_recv_timeout(exc):
                            break
                        continue

                    self._mark_recv()
                    if raw == "ok":
                        continue
                    if isinstance(raw, bytes):
                        raw = raw.decode("utf-8", "ignore")
                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(data, dict):
                        continue
                    if data.get("ModeCode") == "heart_beat":
                        try:
                            ws.send("ok")
                        except OSError:
                            pass
                        inner = data.get("data")
                        if isinstance(inner, dict) and inner:
                            if payload_has_live_ui_update(inner):
                                self._update_state(inner)
                        elif payload_has_live_ui_update(data):
                            self._update_state(data)
                        continue
                    self._update_state(data)

                try:
                    ws.close()
                except OSError:
                    pass
                finally:
                    with self._ws_lock:
                        if self._ws is ws:
                            self._ws = None
            except Exception as exc:
                self._connected = False
                self._last_error = str(exc)
                with self._ws_lock:
                    self._ws = None
                if not self._stop.is_set():
                    time.sleep(1.0)

    def _drain_get_queue(self) -> dict[str, Any]:
        batch: dict[str, Any] = {}
        while True:
            try:
                batch.update(self._get_queue.get_nowait())
            except queue.Empty:
                break
        return batch

    @staticmethod
    def _send_get(ws, params: dict[str, Any]) -> None:
        if params:
            ws.send(json.dumps({"method": "get", "params": params}, separators=(",", ":")))

    def _flush_get(self, ws, **params: Any) -> None:
        batch = self._drain_get_queue()
        batch.update(params)
        if batch:
            self._send_get(ws, batch)

    def _flush_commands(self, ws) -> None:
        batch = self._drain_get_queue()
        if batch:
            self._flush_get(ws, **batch)
        while True:
            try:
                params = self._cmd_queue.get_nowait()
            except queue.Empty:
                break
            msg = json.dumps({"method": "set", "params": params}, separators=(",", ":"))
            ws.send(msg)


def fetch_ws_snapshot(host: str, timeout: float = 5.0, **get_params: Any) -> dict[str, Any]:
    """WebSocket kurz öffnen, GET senden und alle Antworten bis timeout zusammenführen."""
    try:
        import websocket
    except ImportError as exc:
        raise PrinterWsError("websocket-client fehlt") from exc

    host = normalize_host(host)
    url = f"ws://{host}:{WS_PORT}"
    params = get_params or {"boxsInfo": 1, "ReqPrinterPara": 1, "reqPrintObjects": 1}
    payload = json.dumps({"method": "get", "params": params}, separators=(",", ":"))
    state: dict[str, Any] = {}
    ws = websocket.create_connection(url, timeout=timeout)
    try:
        ws.send(payload)
        ws.settimeout(0.35)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                raw = ws.recv()
            except Exception:
                continue
            if raw == "ok":
                continue
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", "ignore")
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict):
                continue
            if data.get("ModeCode") == "heart_beat":
                try:
                    ws.send("ok")
                except OSError:
                    pass
                continue
            merged = normalize_telemetry(data)
            state.update(merged)
            raw_boxs = PrinterConnection._boxs_info_from_payload(data)
            if raw_boxs is not None:
                prev = state.get("boxsInfo")
                state["boxsInfo"] = PrinterConnection._merge_boxs_info(prev, raw_boxs)
            for alt_key in ("retBoxsInfo", "boxsInfo"):
                alt_val = merged.get(alt_key)
                if alt_val is not None:
                    prev = state.get("boxsInfo")
                    state["boxsInfo"] = PrinterConnection._merge_boxs_info(prev, alt_val)
    finally:
        ws.close()
    return state


def request_get_once(host: str, timeout: float = 8.0, **params: Any) -> None:
    """Einmalige GET-Anfrage (z. B. G-Code-Liste)."""
    try:
        import websocket
    except ImportError as exc:
        raise PrinterWsError("websocket-client fehlt") from exc

    host = normalize_host(host)
    url = f"ws://{host}:{WS_PORT}"
    payload = json.dumps({"method": "get", "params": params}, separators=(",", ":"))
    ws = websocket.create_connection(url, timeout=timeout)
    try:
        ws.send(payload)
        ws.settimeout(1.0)
        for _ in range(5):
            try:
                raw = ws.recv()
                if raw == "ok":
                    continue
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8", "ignore")
                data = json.loads(raw)
                if isinstance(data, dict) and data.get("ModeCode") == "heart_beat":
                    ws.send("ok")
            except Exception:
                break
    finally:
        ws.close()


def send_set_once(host: str, timeout: float = 8.0, **params: Any) -> None:
    """Einmaliger Befehl ohne Dauer-Verbindung."""
    try:
        import websocket
    except ImportError as exc:
        raise PrinterWsError("websocket-client fehlt") from exc

    host = normalize_host(host)
    url = f"ws://{host}:{WS_PORT}"
    payload = json.dumps({"method": "set", "params": params}, separators=(",", ":"))
    ws = websocket.create_connection(url, timeout=timeout)
    try:
        ws.send(payload)
        ws.settimeout(1.0)
        for _ in range(3):
            try:
                raw = ws.recv()
                if raw == "ok":
                    continue
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8", "ignore")
                data = json.loads(raw)
                if isinstance(data, dict) and data.get("ModeCode") == "heart_beat":
                    ws.send("ok")
            except Exception:
                break
    finally:
        ws.close()
