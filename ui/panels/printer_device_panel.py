"""Tab „Drucker“ — Steuerung wie Creality Print (K2 WebSocket)."""

from __future__ import annotations

import io
import queue
import shutil
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from typing import TYPE_CHECKING, Any

from creality_nfc.k2_camera_embed import EmbeddedEdgeCamera
from creality_nfc.k2_camera_live import K2CameraWorker, open_camera_app_window
from creality_nfc.printer_camera import fetch_image_urls, open_url
from creality_nfc.printer_klipper import best_ui_url, probe_klipper
from creality_nfc.print_cfs import get_cfs_box_id
from creality_nfc.printer_control import (
    PRINT_SPEED_PRESETS,
    PrinterControlError,
    delete_gcode_file,
    feed_filament,
    request_gcode_list,
    retract_filament,
    send_print_params,
    set_print_speed,
    stop_print,
)
from creality_nfc.cfs_adopt import SLOT_LABELS, CfsSlotInfo, parse_cfs_slots
from creality_nfc.cfs_feed import find_loaded_slot_index
from creality_nfc.gcode_filament import (
    find_gcode_file_info,
    gcode_uses_external_spool,
    merge_gcode_filament_info,
    parse_gcode_print_temps,
)
from creality_nfc.color_util import creality_color_to_hex
from creality_nfc.printer_gcode import (
    entry_remote_path,
    format_gcode_mtime,
    parse_gcode_files,
    thumbnail_urls_for_file,
)
from creality_nfc.printer_ws import fetch_ws_snapshot, send_set_once
from creality_nfc.printer_ssh import (
    default_password,
    delete_gcode_on_printer_ssh,
    download_gcode_from_printer,
    list_gcode_files_ssh,
    normalize_host,
    upload_gcode_to_printer,
)
from creality_nfc.printer_state import (
    build_print_phase_notification,
    print_job_phase,
    should_notify_print_phase_change,
    temp_target_spinbox_value,
    print_status,
    telemetry_fans,
    telemetry_temperatures,
)
from creality_nfc.printer_ws import PrinterConnection
from ui.dialog_theme import theme_dialog
from ui.panels.printer_dashboard_layout import build_creality_dashboard
from ui.messaging import confirm, notify
from ui.printer_tab_theme import apply_printer_tab_theme

if TYPE_CHECKING:
    from app.main_window import TDFilamentStudioApp

PREVIEW_MIN = (320, 240)
GCODE_PREVIEW_MAX_UPSCALE = 8.0


def _fmt_temp(cur, tgt) -> str:
    def n(v, *, decimals: bool = True) -> str:
        if v is None:
            return "—"
        try:
            f = float(v)
            if decimals:
                return f"{f:.1f}"
            return f"{int(round(f))}"
        except (TypeError, ValueError):
            return "—"

    return f"{n(cur)} / {n(tgt, decimals=False)} °C"


class PrinterDevicePanel(ttk.Frame):
    def __init__(self, parent: tk.Misc, app: TDFilamentStudioApp) -> None:
        super().__init__(parent)
        theme_dialog(self)
        apply_printer_tab_theme(parent)
        self.app = app
        self._conn: PrinterConnection | None = None
        self._photo = None
        self._preview_pil = None
        self._ui_lock = False
        self._speed_lock_until = 0.0
        self._speed_var = tk.IntVar(value=100)
        self._gcode_files: list[dict] = []
        self._last_gcode_entry: dict | None = None
        self._last_print_phase: str = "idle"
        self._print_phase_synced: bool = False
        self._last_print_progress: int = 0
        self._peak_print_progress: int = 0
        self._last_print_filename: str = ""
        self._cfs_active_index: int | None = None
        self._last_print_cfs_slot: int | None = None
        self._gcode_preview_hold = False
        self._poll_id: str | None = None
        self._was_connected = False
        self._cfs_slots: list[CfsSlotInfo] = []
        self._cfs_empty_polls = 0
        self._gcode_polls = 0
        self._gcode_ssh_tried = False
        self._live_snap_queue: queue.Queue[dict] = queue.Queue(maxsize=1)
        self._last_full_poll = 0.0
        self._last_telemetry_req = 0.0
        self._fan_drag = False
        self._cam_worker: K2CameraWorker | None = None
        self._edge_cam: EmbeddedEdgeCamera | None = None
        self._cam_fallback_after: str | None = None
        self._cam_photo = None
        self._last_cam_jpeg: bytes | None = None
        self._cam_resize_bound = False
        self._cam_active_host = ""
        self._cam_started_at = 0.0
        self._cam_start_scheduled = False
        self._cam_prefetch_pending = False
        self._cfs_fetch_pending = False
        self._reconnect_pending = False
        self._printer_tab_visited = False
        self._last_snap: dict[str, Any] = {}
        self._last_auto_burst = 0.0
        self._live_poll_id: str | None = None
        self._pull_pending = False

        outer = ttk.Frame(self, style="Printer.TFrame")
        outer.pack(fill="both", expand=True, padx=8, pady=8)
        build_creality_dashboard(self, outer)
        self.configure(style="Printer.TFrame")

        self._schedule_poll()
        self.after(600, self._try_auto_connect)

    def _host_quiet(self) -> str | None:
        host = normalize_host(self.app.ssh_host_var.get())
        return host or None

    def on_tab_shown(self) -> None:
        """Tab „Drucker“ aktiv — Verbindung und Live-Updates sicherstellen."""
        self._printer_tab_visited = True
        if not self._poll_id:
            self._schedule_poll()
        if self._last_cam_jpeg:
            self.after(50, self._paint_cam_frame)
        elif self._conn and self._conn.connected:
            # Nach App-Start lief die Kamera oft im Hintergrund ohne Bild — hier neu anstoßen.
            self.after(150, lambda: self._ensure_live_camera(force=True))
        host = self._host_quiet()
        if not host:
            return
        if not self._conn:
            self.connect()
            return
        if self._conn.connected:
            if self._conn.has_received() and self._conn.recv_idle_seconds() > 15.0:
                self._force_reconnect()
            else:
                self._soft_live_refresh()
                self._burst_refresh()
                self.after(80, self._refresh_print_strip)
                self.after(900, self._refresh_print_strip)
        elif not self._reconnect_pending:
            self._force_reconnect()

    def on_printer_subtab_shown(self) -> None:
        """Unter-Tabs Monitor/Steuerung/… — Druckzeile auch auf Monitor aktualisieren."""
        self._refresh_print_strip()
        if self._conn and self._conn.connected:
            self._conn.request_get(reqPrintObjects=1, ReqPrinterPara=1)
            self.after(600, self._refresh_print_strip)

    def _try_auto_connect(self) -> None:
        if self._host_quiet() and not self._conn:
            self.connect()
        elif self._conn and not self._conn.connected and not self._reconnect_pending:
            self._force_reconnect()

    def _soft_live_refresh(self) -> None:
        """Anfrage über die Dauer-Verbindung."""
        if not self._conn or not self._conn.connected:
            return
        self._last_telemetry_req = time.monotonic()
        self._conn.request_get(ReqPrinterPara=1, reqPrintObjects=1)

    def _pull_live_snapshot_async(self) -> None:
        """Eigene kurze WS-Abfrage — funktioniert auch wenn die Dauer-WS hängt."""
        if self._pull_pending or not self._conn or not self._conn.connected:
            return
        host = self._conn.host
        conn = self._conn
        self._pull_pending = True

        def work() -> None:
            try:
                snap = fetch_ws_snapshot(
                    host,
                    timeout=5.0,
                    ReqPrinterPara=1,
                    reqPrintObjects=1,
                )
                conn.merge_external(snap)
            except Exception:
                pass

            def ui() -> None:
                self._pull_pending = False
                if not self._conn:
                    return
                s = self._conn.snapshot()
                if s:
                    self._apply_live_status(s)
                    self._apply_state(s)
                    self._refresh_print_strip()
                from creality_nfc.printer_state import payload_has_live_telemetry

                if payload_has_live_telemetry(s or {}):
                    self.conn_var.set(f"Verbunden — {self._conn.host}")

            self.app.after(0, ui)

        threading.Thread(target=work, daemon=True).start()

    def _burst_refresh(self) -> None:
        if not self._conn:
            return
        self._last_telemetry_req = 0.0
        self._last_auto_burst = time.monotonic()
        self._conn.request_get(
            ReqPrinterPara=1,
            reqPrintObjects=1,
            boxsInfo=1,
            reqGcodeList=1,
            reqGcodeFile=1,
            reqGcodeFileInfo2=1,
        )

    def _schedule_live_poll(self) -> None:
        if self._live_poll_id:
            try:
                self.after_cancel(self._live_poll_id)
            except tk.TclError:
                pass
        if self._conn and self._conn.connected:
            self._pull_live_snapshot_async()
        self._live_poll_id = self.after(7000, self._schedule_live_poll)

    def _stop_live_poll(self) -> None:
        if self._live_poll_id:
            try:
                self.after_cancel(self._live_poll_id)
            except tk.TclError:
                pass
            self._live_poll_id = None

    def _schedule_connect_refresh(self, attempt: int = 0) -> None:
        """Temperatur/Lüfter nach Verbindung mehrfach anfordern (K2 antwortet oft verzögert)."""
        if not self._conn:
            return
        if self._conn.connected:
            self._burst_refresh()
            snap = self._conn.snapshot()
            if snap:
                self._apply_live_status(snap)
                self._apply_state(snap)
        if attempt >= 3:
            return
        delay = (400, 900, 1600)[attempt]
        self.after(delay, lambda a=attempt + 1: self._schedule_connect_refresh(a))

    def _force_reconnect(self) -> None:
        if self._reconnect_pending:
            return
        host = self._conn.host if self._conn else self._host_quiet()
        if not host:
            return
        self._reconnect_pending = True
        self.conn_var.set("Verbindung wird erneuert …")
        self.disconnect()

        def _again() -> None:
            self._reconnect_pending = False
            if self._host_quiet():
                self.connect()

        self.after(400, _again)

    def _host(self) -> str | None:
        host = normalize_host(self.app.ssh_host_var.get())
        if not host:
            notify(self, "Bitte Drucker-IP eintragen (Tab RFID-Tag oder Material-Datenbank).", "warn")
            return None
        return host

    def _ssh_password(self) -> str:
        printer = self.app.printer_var.get().strip() or "K2 Pro"
        return self.app.ssh_pass_var.get() or default_password(printer)

    def _finish_connect_status(self, *, wait_ok: bool | None = None) -> None:
        if not self._conn:
            return
        host = self._conn.host
        if wait_ok is True:
            self.conn_var.set(f"Verbunden — {host}")
        elif wait_ok is False and self._conn.connected:
            self.conn_var.set(
                f"Verbunden — {host} (Temperatur: Creality Print schließen?)"
            )
        elif self._conn.connected:
            from creality_nfc.printer_state import payload_has_live_telemetry

            snap = self._conn.snapshot()
            if payload_has_live_telemetry(snap or {}):
                self.conn_var.set(f"Verbunden — {host}")
            else:
                self.conn_var.set(f"Verbunden — {host} (Live-Daten laden …)")

    def _run_wait_telemetry(self) -> None:
        if not self._conn:
            return
        ok = self._conn.wait_for_live_telemetry(7.0)

        def _ui() -> None:
            if not self._conn:
                return
            snap = self._conn.snapshot()
            if snap:
                self._apply_live_status(snap)
                self._apply_state(snap)
            self._finish_connect_status(wait_ok=ok)

        self.app.after(0, _ui)

    def connect(self) -> None:
        host = self._host()
        if not host:
            return
        if (
            self._conn
            and self._conn.host == host
            and self._conn.connected
            and not self._reconnect_pending
        ):
            self.conn_var.set(f"Verbunden — {host} (aktualisiere …)")
            self._burst_refresh()
            self._pull_live_snapshot_async()
            self._schedule_connect_refresh(0)
            if not self._live_poll_id:
                self._schedule_live_poll()
            if not self._last_cam_jpeg:
                self._schedule_camera_start()
            threading.Thread(target=self._run_wait_telemetry, daemon=True).start()
            return
        self.disconnect()
        self._conn = PrinterConnection(host)
        self._conn.add_listener(self._on_ws_live)
        self._last_full_poll = 0.0
        self._last_telemetry_req = 0.0
        self._was_connected = False
        self._print_phase_synced = False
        self._conn.start()
        self.conn_var.set(f"Verbinde mit {host}:9999 …")
        self._gcode_polls = 0
        self._gcode_ssh_tried = False
        self._conn.request_get(
            ReqPrinterPara=1,
            reqPrintObjects=1,
            boxsInfo=1,
            reqGcodeList=1,
            reqGcodeFile=1,
            reqGcodeFileInfo=1,
            reqGcodeFileInfo2=1,
        )
        self._schedule_poll()
        self._schedule_connect_refresh(0)
        threading.Thread(target=self._run_wait_telemetry, daemon=True).start()
        self._schedule_live_poll()
        self.after(1200, self._pull_live_snapshot_async)
        self._schedule_camera_start()
        self.after(400, self._refresh_print_strip)
        self.after(1500, self._refresh_print_strip)
        self.after(500, self._refresh_gcode_list)
        self.after(600, self._fetch_cfs_snapshot_async)
        self.after(800, self._refresh_cfs)

    def _on_gcode_preview_resize(self) -> None:
        if self._gcode_preview_hold and self._preview_pil is not None:
            self._fit_gcode_preview_image()

    def _fit_gcode_preview_image(self) -> None:
        if self._preview_pil is None or not hasattr(self, "_gcode_preview_host"):
            return
        try:
            from PIL import Image, ImageTk

            host = self._gcode_preview_host
            host.update_idletasks()
            w = max(320, host.winfo_width())
            h = max(240, host.winfo_height())
            img = self._preview_pil.copy()
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGB")
            resample = getattr(Image, "Resampling", Image).LANCZOS
            iw, ih = img.size
            if iw > 0 and ih > 0:
                scale = min(GCODE_PREVIEW_MAX_UPSCALE, w / iw, h / ih)
                nw = max(1, int(iw * scale))
                nh = max(1, int(ih * scale))
                if nw != iw or nh != ih:
                    img = img.resize((nw, nh), resample)
            self._photo = ImageTk.PhotoImage(img)
            self.gcode_preview_label.config(image=self._photo, text="")
            self.gcode_preview_label.place(relx=0, rely=0, relwidth=1, relheight=1)
        except ImportError:
            notify(self, "Pillow fehlt — pip install pillow", "error")
        except Exception as exc:
            self._status_var.set(f"Bildanzeige fehlgeschlagen: {exc}")

    def _clear_gcode_preview(self) -> None:
        self._gcode_preview_hold = False
        self._preview_pil = None
        self._photo = None
        if hasattr(self, "gcode_preview_label"):
            self.gcode_preview_label.config(
                image="",
                text="Datei in der Liste wählen\n\n(Vorschaubild aus dem G-Code)",
            )
            self.gcode_preview_label.place(relx=0, rely=0, relwidth=1, relheight=1)

    def disconnect(self) -> None:
        if self._poll_id:
            self.after_cancel(self._poll_id)
            self._poll_id = None
        while True:
            try:
                self._live_snap_queue.get_nowait()
            except queue.Empty:
                break
        self._stop_live_camera()
        self._stop_live_poll()
        if self._conn:
            self._conn.remove_listener(self._on_ws_live)
            self._conn.stop()
            self._conn = None
        self.conn_var.set("Getrennt")
        self._gcode_preview_hold = False
        self._was_connected = False
        self._print_phase_synced = False
        self._gcode_polls = 0
        self._gcode_ssh_tried = False

    def _schedule_poll(self) -> None:
        if self._poll_id:
            self.after_cancel(self._poll_id)
        self._poll_id = self.after(450, self._poll)

    def _poll(self) -> None:
        now = time.monotonic()
        if self._conn:
            if self._conn.connected:
                recv_idle = self._conn.recv_idle_seconds()
                print_idle = self._conn.print_idle_seconds()
                if self._conn.has_received() and recv_idle > 15.0:
                    self.conn_var.set("Verbindung unterbrochen — verbinde neu …")
                    self._force_reconnect()
                    self._poll_id = self.after(450, self._poll)
                    return
                if print_idle > 6.0 and now - self._last_auto_burst > 6.0:
                    self._pull_live_snapshot_async()
                    self._last_auto_burst = now
                from creality_nfc.printer_state import payload_has_live_telemetry

                snap = self._drain_live_snap() or self._conn.snapshot()
                if payload_has_live_telemetry(snap or {}):
                    self.conn_var.set(f"Verbunden — {self._conn.host}")
                else:
                    self.conn_var.set(f"Verbunden — {self._conn.host} (Live-Daten laden …)")
                if not self._was_connected:
                    self._was_connected = True
                    self._burst_refresh()
                    self._schedule_connect_refresh(1)
                    self._gcode_polls = 0
                    self._gcode_ssh_tried = False
                    self.after(300, self._refresh_gcode_list)
                    if not self._last_cam_jpeg:
                        self.after(400, self._schedule_camera_start)
                    self.after(300, self._refresh_print_strip)
            elif self._conn.last_error:
                self.conn_var.set(f"Verbinde erneut… ({self._conn.last_error[:72]})")
            snap = self._drain_live_snap()
            if not snap and self._conn:
                snap = self._conn.snapshot()
            if self._conn and self._conn.connected:
                if now - self._last_telemetry_req >= 2.0:
                    self._last_telemetry_req = now
                    self._conn.request_get(ReqPrinterPara=1, reqPrintObjects=1)
            if self._conn.connected or snap:
                self._apply_live_status(snap or {})
            if self._conn.connected and now - self._last_full_poll >= 1.0:
                self._last_full_poll = now
                self._apply_state(snap or self._conn.snapshot())
        self._poll_id = self.after(450, self._poll)

    def _set_fan_drag(self, dragging: bool) -> None:
        self._fan_drag = dragging

    def _temp_spinboxes_locked(self) -> bool:
        return time.monotonic() < self._temp_lock_until

    def _lock_temp_spinboxes(self, seconds: float = 25.0) -> None:
        self._temp_lock_until = time.monotonic() + seconds

    def _on_temp_spin_focus(self, _event: tk.Event | None = None) -> None:
        self._lock_temp_spinboxes(30.0)

    def _sync_temp_target_var(
        self, var: tk.IntVar, reported: Any, *, job_active: bool = False
    ) -> None:
        new_val = temp_target_spinbox_value(
            var.get(),
            reported,
            locked=self._temp_spinboxes_locked(),
            job_active=job_active,
        )
        if new_val is not None:
            var.set(new_val)

    def _guard_temps_for_print(self, nozzle: int | None, bed: int | None) -> None:
        """Soll-Temp. während CFS-Zufuhr/Druckstart nicht auf 0 zurücksetzen."""
        self._lock_temp_spinboxes(180.0)
        if nozzle and nozzle > 0:
            self.nozzle_tgt.set(nozzle)
        if bed and bed > 0:
            self.bed_tgt.set(bed)

    def _on_ws_live(self, snap: dict) -> None:
        """WS-Hintergrundthread → Queue; UI-Thread aktualisiert in _poll (Tk-sicher)."""
        try:
            self._live_snap_queue.put_nowait(snap)
        except queue.Full:
            try:
                self._live_snap_queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._live_snap_queue.put_nowait(snap)
            except queue.Full:
                pass

    def _drain_live_snap(self) -> dict | None:
        latest: dict | None = None
        while True:
            try:
                latest = self._live_snap_queue.get_nowait()
            except queue.Empty:
                break
        return latest

    def _refresh_print_strip(self) -> None:
        """„Aktueller Druck“ — unabhängig vom Tab Steuerung/Monitor."""
        snap = self._last_snap
        if not snap and self._conn:
            snap = self._conn.snapshot()
        if not snap:
            return
        try:
            self._apply_print_status(snap)
        except tk.TclError:
            pass

    def _apply_live_status(self, s: dict) -> None:
        """Temperatur, Fortschritt, CFS, Druck-Buttons — bei jedem Poll / WS-Push."""
        self._last_snap = s
        try:
            self._apply_telemetry(s)
        except tk.TclError:
            pass
        try:
            self._apply_print_status(s)
        except tk.TclError:
            pass
        try:
            self._update_cfs_ui(s)
        except tk.TclError:
            pass

    def _effective_target(self, reported: Any, var: tk.IntVar) -> Any:
        """Soll-Temp. für Anzeige: Druckerwert oder Spinbox wenn Firmware 0 meldet."""
        if reported is not None:
            try:
                if int(round(float(reported))) > 0:
                    return reported
            except (TypeError, ValueError):
                pass
        if self._temp_spinboxes_locked() or self._print_job_active():
            try:
                v = int(var.get())
                if v > 0:
                    return v
            except (TypeError, ValueError, tk.TclError):
                pass
        return reported

    def _print_job_active(self) -> bool:
        if not getattr(self, "_last_snap", None):
            return self._temp_spinboxes_locked()
        from creality_nfc.printer_state import print_job_phase

        return print_job_phase(self._last_snap) in ("printing", "paused")

    def _apply_telemetry(self, s: dict) -> None:
        n_cur, n_tgt, b_cur, b_tgt, c_cur, c_tgt = telemetry_temperatures(s)
        self.nozzle_lbl.config(
            text=_fmt_temp(n_cur, self._effective_target(n_tgt, self.nozzle_tgt))
        )
        self.bed_lbl.config(
            text=_fmt_temp(b_cur, self._effective_target(b_tgt, self.bed_tgt))
        )
        self.box_lbl.config(
            text=_fmt_temp(c_cur, self._effective_target(c_tgt, self.box_tgt))
        )

        if not self._fan_drag:
            for i, val in enumerate(telemetry_fans(s)):
                if val is not None:
                    try:
                        self.fan_vars[i].set(int(round(float(val))))
                    except (TypeError, ValueError):
                        pass

    def _apply_state(self, s: dict) -> None:
        self._last_snap = s
        self._ui_lock = True
        try:
            from creality_nfc.printer_state import print_job_phase

            job_active = print_job_phase(s) in ("printing", "paused")
            self._apply_telemetry(s)
            _t = telemetry_temperatures(s)
            self._sync_temp_target_var(self.nozzle_tgt, _t[1], job_active=job_active)
            self._sync_temp_target_var(self.bed_tgt, _t[3], job_active=job_active)
            self._sync_temp_target_var(self.box_tgt, _t[5], job_active=job_active)

            self._apply_print_status(s)

            sw = s.get("lightSw")
            if sw is not None:
                self.led_var.set(int(sw) == 1)

            if time.monotonic() >= self._speed_lock_until:
                pct = self._speed_from_state(s)
                if pct is not None:
                    self._speed_var.set(pct)

            files = parse_gcode_files(s)
            if files:
                self._set_gcode_files(files)
                self._gcode_ssh_tried = False
            elif self._conn and self._conn.connected and not self._gcode_files:
                self._gcode_polls += 1
                if self._gcode_polls >= 3 and not self._gcode_ssh_tried:
                    self._gcode_ssh_tried = True
                    self._fetch_gcode_list_ssh()

            self._update_cfs_ui(s)
            if self._conn and self._conn.connected:
                if all(slot.empty for slot in self._cfs_slots):
                    self._cfs_empty_polls += 1
                    self._conn.request_get(boxsInfo=1)
                    if self._cfs_empty_polls in (1, 3, 8):
                        self._fetch_cfs_snapshot_async()
                else:
                    self._cfs_empty_polls = 0
        finally:
            self._ui_lock = False

    @staticmethod
    def _basename(path: str) -> str:
        return path.replace("\\", "/").rstrip("/").split("/")[-1] if path else "—"

    @staticmethod
    def _duration_seconds(raw: Any) -> int | None:
        if raw is None:
            return None
        try:
            v = float(raw)
        except (TypeError, ValueError):
            return None
        if v < 0:
            return None
        return int(round(v))

    @staticmethod
    def _fmt_duration(seconds: int | None) -> str:
        if seconds is None or seconds <= 0:
            return ""
        h, rem = divmod(seconds, 3600)
        m, sec = divmod(rem, 60)
        if h:
            return f"{h}h {m:02d}min" if m or not sec else f"{h}h"
        if m:
            return f"{m}min {sec}s" if sec else f"{m}min"
        return f"{sec}s"

    @staticmethod
    def _fmt_left_time(seconds: Any, *, phase: str, progress: int | None) -> str:
        if phase in ("complete", "idle", "error"):
            return ""
        s = PrinterDevicePanel._duration_seconds(seconds)
        if s is None:
            return ""
        if s <= 0:
            if progress is not None and progress >= 100:
                return ""
            return "noch < 1 min"
        h, rem = divmod(s, 3600)
        m = rem // 60
        if h:
            return f"noch ca. {h}h {m}min"
        return f"noch ca. {m}min"

    @staticmethod
    def should_trigger_post_print_deduct(
        prev_phase: str,
        phase: str,
        *,
        progress: int | None,
        last_progress: int,
        peak_progress: int = 0,
        filename: str,
        last_filename: str,
    ) -> bool:
        """Abzug-Dialog: Druckende erkennen (auch nach spätem Verbinden)."""
        if phase == "complete" and prev_phase != "complete":
            return True
        if prev_phase in ("printing", "paused") and phase == "complete":
            return True
        if prev_phase in ("printing", "paused") and phase == "idle":
            prog = progress if progress is not None else last_progress
            peak = max(last_progress, peak_progress, prog if prog is not None else 0)
            if peak >= 99 and (filename.strip() or last_filename.strip()):
                return True
        return False

    def _request_post_print_deduct(self, s: dict, ps: dict, *, manual: bool = False) -> None:
        try:
            snap = self._conn.snapshot() if self._conn else s
            loaded = find_loaded_slot_index(snap)
            self.app.on_print_job_finished(
                loaded
                if loaded is not None
                else self._last_print_cfs_slot
                if self._last_print_cfs_slot is not None
                else self._cfs_active_index,
                ps.get("file") or self._last_print_filename or "",
                snap,
                manual=manual,
            )
        except Exception as exc:
            try:
                self.app.notify(f"Filament-Abzug konnte nicht starten: {exc}", "warn")
            except Exception:
                pass

    def _maybe_notify_print_phase(
        self,
        prev_phase: str,
        phase: str,
        s: dict,
        *,
        filename: str,
        progress: int | None,
    ) -> None:
        if not self._print_phase_synced:
            return
        has_job = bool(filename.strip() or self._last_print_filename.strip())
        if not should_notify_print_phase_change(
            prev_phase, phase, has_job=has_job, synced=True
        ):
            return
        note = build_print_phase_notification(
            s,
            phase,
            filename=filename or self._last_print_filename,
            progress=progress,
        )
        if not note:
            return
        self.app.after(
            0,
            lambda: self.app.notify_print_job_alert(
                note["title"], note["detail"], note.get("level", "warn")
            ),
        )

    def _apply_print_status(self, s: dict) -> None:
        ps = print_status(s)
        phase = print_job_phase(s)
        fname = str(ps.get("file") or "").strip()
        prog = ps.get("progress")
        prev_phase = self._last_print_phase
        if not self._print_phase_synced:
            self._last_print_phase = phase
            self._print_phase_synced = True
        else:
            self._maybe_notify_print_phase(
                prev_phase, phase, s, filename=fname, progress=prog
            )
        if phase == "printing":
            self.app._post_print_prompted = False
            if fname and fname != self._last_print_filename:
                self.app._post_print_deduct_file = ""
                self._peak_print_progress = 0
            loaded_now = find_loaded_slot_index(s)
            if loaded_now is not None:
                self._last_print_cfs_slot = loaded_now
            elif self._cfs_active_index is not None:
                self._last_print_cfs_slot = self._cfs_active_index
        if phase in ("printing", "paused") and prog is not None:
            self._peak_print_progress = max(
                self._peak_print_progress, max(0, min(100, int(prog)))
            )
        if self.should_trigger_post_print_deduct(
            self._last_print_phase,
            phase,
            progress=prog,
            last_progress=self._last_print_progress,
            peak_progress=self._peak_print_progress,
            filename=fname,
            last_filename=self._last_print_filename,
        ):
            self._request_post_print_deduct(s, ps)
        if prog is not None:
            self._last_print_progress = max(0, min(100, int(prog)))
        if fname:
            self._last_print_filename = fname
        self._last_print_phase = phase
        fname = self._basename(ps["file"]) if ps["file"] else "—"
        self.print_file_var.set(fname)
        if fname and fname != "—":
            self._sync_listbox_to_filename(fname)
        prog = ps["progress"]
        if prog is not None:
            pct = max(0, min(100, prog))
            self._prog_bar.configure(maximum=100)
            self._prog_bar["value"] = pct
            prog_txt = f"{pct} %"
        else:
            self._prog_bar["value"] = 0
            prog_txt = "—"
        bits: list[str] = [f"Fortschritt: {prog_txt}"]
        try:
            if ps["cur_layer"] is not None and ps["total_layer"] is not None:
                cl, tl = int(ps["cur_layer"]), int(ps["total_layer"])
                if tl > 0:
                    bits.append(f"Layer {cl}/{tl}")
        except (TypeError, ValueError):
            pass
        self.print_prog_var.set(" · ".join(bits))

        used_s = self._duration_seconds(ps.get("used"))
        total_s = self._duration_seconds(ps.get("total"))
        used_txt = self._fmt_duration(used_s)
        total_txt = self._fmt_duration(total_s)
        left_txt = self._fmt_left_time(ps["left_sec"], phase=phase, progress=prog)

        time_bits: list[str] = []
        if phase == "complete":
            if used_txt:
                time_bits.append(f"Druckzeit {used_txt}")
            elif total_txt:
                time_bits.append(f"Druckzeit {total_txt}")
            else:
                time_bits.append("Druck beendet")
        elif phase == "printing":
            if left_txt:
                time_bits.append(left_txt)
            if used_txt:
                time_bits.append(f"{used_txt} verstrichen")
        elif phase == "paused":
            if used_txt:
                time_bits.append(f"{used_txt} verstrichen")
            time_bits.append("pausiert")
        elif left_txt:
            time_bits.append(left_txt)

        self.print_time_var.set(" · ".join(time_bits) if time_bits else "")
        self._update_print_controls(s, phase=phase)

    def _manual_post_print_deduct(self) -> None:
        if not self._conn:
            notify(self, "Zuerst mit dem Drucker verbinden.", "warn")
            return
        snap = self._conn.snapshot()
        ps = print_status(snap)
        if not (ps.get("file") or self._last_print_filename):
            notify(self, "Kein Druckjob erkannt — Dateiname fehlt.", "warn")
            return
        self._request_post_print_deduct(snap, ps, manual=True)

    def _update_print_controls(self, s: dict, *, phase: str | None = None) -> None:
        phase = phase if phase is not None else print_job_phase(s)
        hints = {
            "idle": "Bereit — neuen Job in Creality Print starten.",
            "printing": "Druck läuft — Fortschritt per WebSocket.",
            "paused": "Druck pausiert — „Fortsetzen“ oder „Stopp“.",
            "complete": "Druck beendet — nächsten Job in Creality Print.",
            "error": "Fehler — am Display prüfen oder „Stopp“.",
        }
        self._print_hint_var.set(hints.get(phase, ""))
        try:
            if phase == "paused":
                self._btn_pause.config(state="disabled")
                self._btn_resume.config(state="normal")
            elif phase == "printing":
                self._btn_pause.config(state="normal")
                self._btn_resume.config(state="disabled")
            else:
                self._btn_pause.config(state="disabled")
                self._btn_resume.config(state="disabled")
            if hasattr(self, "_btn_deduct"):
                deduct_ok = phase in ("complete", "idle") and (
                    bool(str(print_status(s).get("file") or "").strip())
                    or bool(self._last_print_filename)
                )
                self._btn_deduct.config(state="normal" if deduct_ok else "disabled")
        except tk.TclError:
            pass

    def _pause_print(self) -> None:
        host = self._host()
        if not host:
            return
        snap = self._conn.snapshot() if self._conn else {}
        if print_job_phase(snap) != "printing":
            notify(self, "Kein laufender Druck — Job in Creality Print starten.", "warn")
            return

        def work() -> None:
            send_print_params(host, {"pause": 1}, self._conn)
            self.app.after(0, lambda: notify(self, "Pause gesendet", "ok"))

        self._run_bg("Pause", work)

    def _resume_print(self) -> None:
        host = self._host()
        if not host:
            return
        snap = self._conn.snapshot() if self._conn else {}

        def work() -> None:
            phase = print_job_phase(snap)
            if phase != "paused":
                self.app.after(
                    0,
                    lambda: notify(
                        self,
                        "Kein pausierter Druck. „Fortsetzen“ gilt nur nach Pause.\n"
                        "Neuen Job in Creality Print starten.",
                        "warn",
                    ),
                )
                return
            if int(snap.get("repoPlrStatus", 0) or 0) == 1 or int(
                snap.get("materialStatus", 0) or 0
            ) == 1:
                send_print_params(host, {"repoPlrStatus": 1}, self._conn)
            else:
                send_print_params(host, {"pause": 0}, self._conn)
            self.app.after(0, lambda: notify(self, "Fortsetzen gesendet", "ok"))

        self._run_bg("Fortsetzen", work)

    def _toggle_live_camera(self) -> None:
        if self._cam_worker:
            self._stop_live_camera()
            return
        self._switch_to_live_camera()

    def _toggle_embedded_camera(self) -> None:
        """Kompatibilität: Monitor-Button „Live-Kamera“."""
        self._toggle_live_camera()

    def _open_camera_fullscreen(self) -> None:
        host = self._conn.host if self._conn else self._host()
        if not host:
            return
        if open_camera_app_window(host):
            self._cam_status_var.set("Vollbild (Edge) geöffnet")
        else:
            notify(self, "Kamera im Browser nicht verfügbar.", "error")

    def _switch_to_live_camera(self) -> None:
        """Tab Monitor: Live-Kamera starten."""
        if hasattr(self, "_main_nb"):
            try:
                self._main_nb.select(0)
            except tk.TclError:
                pass
        self._start_live_camera()

    def _preferred_cam_url(self, host: str) -> str:
        host = normalize_host(host)
        return (self.app.settings.camera_snapshot_by_host or {}).get(host, "")

    def _remember_cam_url(self, host: str, url: str) -> None:
        host = normalize_host(host)
        url = (url or "").strip()
        if not host or not url:
            return
        cache = self.app.settings.camera_snapshot_by_host
        if cache.get(host) == url:
            return
        cache[host] = url
        try:
            from creality_nfc.app_settings import DEFAULT_SETTINGS_PATH

            self.app.settings.save(DEFAULT_SETTINGS_PATH)
        except Exception:
            pass

    def _stop_live_camera(self, *, keep_frame: bool = False) -> None:
        if self._cam_fallback_after:
            try:
                self.after_cancel(self._cam_fallback_after)
            except tk.TclError:
                pass
            self._cam_fallback_after = None
        if self._edge_cam:
            self._edge_cam.stop()
            self._edge_cam = None
        if self._cam_worker:
            self._cam_worker.stop()
            self._cam_worker = None
        self._cam_active_host = ""
        if not keep_frame:
            self._last_cam_jpeg = None
            self._cam_photo = None
            self._cam_status_var.set("")
            if hasattr(self, "cam_preview_label"):
                self.cam_preview_label.place(relx=0, rely=0, relwidth=1, relheight=1)
                self.cam_preview_label.config(
                    image="",
                    text="Verbinde mit dem Drucker — Kamera startet automatisch",
                )

    def _on_cam_jpeg_frame(self, data: bytes) -> None:
        self._last_cam_jpeg = data
        if self._cam_fallback_after:
            try:
                self.after_cancel(self._cam_fallback_after)
            except tk.TclError:
                pass
            self._cam_fallback_after = None
        try:
            self.app.after(0, self._paint_cam_frame)
        except tk.TclError:
            pass

    def _paint_cam_frame(self) -> None:
        data = self._last_cam_jpeg
        if not data or not hasattr(self, "cam_preview_label"):
            return
        try:
            from PIL import Image, ImageTk
            import io

            host = getattr(self, "_cam_preview_host", self._preview_host)
            host.update_idletasks()
            w, h = host.winfo_width(), host.winfo_height()
            if w < 20 or h < 20:
                self.after(250, self._paint_cam_frame)
                return
            w = max(200, w)
            h = max(150, h)
            img = Image.open(io.BytesIO(data))
            img.thumbnail((w, h), Image.Resampling.LANCZOS)
            self._cam_photo = ImageTk.PhotoImage(img, master=host)
            self.cam_preview_label.config(image=self._cam_photo, text="")
            self.cam_preview_label.place(relx=0, rely=0, relwidth=1, relheight=1)
            self._cam_status_var.set("Live")
        except Exception:
            self._cam_status_var.set("Kamera: Bild fehlerhaft")

    def _on_cam_status(self, msg: str) -> None:
        try:
            self.app.after(0, lambda m=msg: self._cam_status_var.set(m))
        except tk.TclError:
            pass

    def _try_edge_camera_fallback(self) -> None:
        self._cam_fallback_after = None
        if not self._printer_tab_visited:
            return
        if self._edge_cam and self._edge_cam.active:
            return
        host = self._conn.host if self._conn else self._host()
        if not host:
            return
        self._cam_status_var.set("Starte Edge/WebRTC …")
        cam_host = getattr(self, "_cam_preview_host", self._preview_host)
        if not self._edge_cam:
            self._edge_cam = EmbeddedEdgeCamera(cam_host, host)
        if self._edge_cam.start():
            self._cam_status_var.set("Live (Edge/WebRTC)")
        else:
            self._cam_status_var.set(
                "Kamera nicht erreichbar — Drucker-IP/WLAN prüfen (unabhängig vom NFC-Reader)"
            )

    def _prefetch_camera_frame(self, host: str) -> None:
        if self._cam_prefetch_pending:
            return
        host = normalize_host(host)
        if not host:
            return
        self._cam_prefetch_pending = True

        def work() -> None:
            try:
                shot = K2CameraWorker.prefetch(
                    host,
                    preferred_url=self._preferred_cam_url(host),
                    timeout=2.0,
                )
                if shot:
                    data, url = shot
                    self._remember_cam_url(host, url)

                    def show() -> None:
                        if normalize_host(self._cam_active_host or host) != host:
                            return
                        self._on_cam_jpeg_frame(data)

                    self.app.after(0, show)
            finally:
                self._cam_prefetch_pending = False

        threading.Thread(target=work, name="k2-cam-prefetch", daemon=True).start()

    def _schedule_camera_start(self, attempt: int = 0) -> None:
        """Kamera erst starten, wenn WS-Daten vom Drucker da sind (sonst hängt „verbinde …“)."""
        host = self._conn.host if self._conn else self._host_quiet()
        if not host:
            self._cam_start_scheduled = False
            return
        if not self._conn or not self._conn.connected:
            if attempt < 24:
                self.after(500, lambda: self._schedule_camera_start(attempt + 1))
            else:
                self._cam_start_scheduled = False
            return
        if not self._conn.has_received() and attempt < 18:
            self.after(400, lambda: self._schedule_camera_start(attempt + 1))
            return
        self._cam_start_scheduled = False
        self._ensure_live_camera(force=not bool(self._last_cam_jpeg))

    def _ensure_live_camera(self, *, force: bool = False) -> None:
        host = self._conn.host if self._conn else self._host()
        if not host:
            self._cam_status_var.set("Kamera: Drucker-IP eintragen (RFID-Tab / Einstellungen)")
            return
        host = normalize_host(host)
        if self._cam_worker and self._cam_active_host == host and not force:
            if self._last_cam_jpeg:
                self._paint_cam_frame()
                return
            age = time.monotonic() - self._cam_started_at if self._cam_started_at else 999.0
            if age < 6.0:
                return
            force = True
        same_host = self._cam_active_host == host
        self._stop_live_camera(keep_frame=same_host and not force)
        self._cam_active_host = host
        cam_host = getattr(self, "_cam_preview_host", self._preview_host)
        if not getattr(self, "_cam_resize_bound", False):
            cam_host.bind("<Configure>", lambda _e: self._paint_cam_frame(), add="+")
            self._cam_resize_bound = True
        if self._last_cam_jpeg:
            self._paint_cam_frame()
        else:
            self._cam_status_var.set("Kamera: verbinde …")
        self._prefetch_camera_frame(host)
        self._cam_worker = K2CameraWorker(
            host,
            self._on_cam_jpeg_frame,
            interval=0.45,
            prefer_snapshot=True,
            on_status=self._on_cam_status,
            on_need_edge=lambda: self.app.after(0, self._try_edge_camera_fallback),
            preferred_snapshot_url=self._preferred_cam_url(host),
            on_snapshot_url=lambda url, h=host: self._remember_cam_url(h, url),
        )
        self._cam_started_at = time.monotonic()
        self._cam_worker.start()
        delay = 3500 if sys.platform == "win32" else 6000
        self._cam_fallback_after = self.after(delay, self._try_edge_camera_fallback)

    def _start_live_camera(self) -> None:
        self._ensure_live_camera(force=True)

    def _update_cfs_ui(self, state: dict) -> None:
        from creality_nfc.cfs_adopt import parse_cfs_meta

        self.cfs_dashboard.set_inventory(self.app.inventory)
        self.cfs_dashboard.update_from_state(state)
        self._cfs_slots = list(self.cfs_dashboard._slots)
        meta = parse_cfs_meta(state)
        self._cfs_active_index = meta.active_index

    def _fetch_cfs_snapshot_async(self) -> None:
        if self._cfs_fetch_pending:
            return
        host = self._conn.host if self._conn else self._host()
        if not host:
            return
        self._cfs_fetch_pending = True

        def work() -> None:
            try:
                snap = fetch_ws_snapshot(
                    host,
                    timeout=10.0,
                    boxsInfo=1,
                    reqPrintObjects=1,
                    ReqPrinterPara=1,
                )
                if self._conn:
                    bi = snap.get("boxsInfo")
                    if bi is not None:
                        with self._conn._lock:
                            prev = self._conn._state.get("boxsInfo")
                            self._conn._state["boxsInfo"] = PrinterConnection._merge_boxs_info(
                                prev, bi
                            )
                        snap = self._conn.snapshot()
            except Exception:
                snap = {}
            finally:
                self._cfs_fetch_pending = False

            def apply() -> None:
                self._update_cfs_ui(snap)
                if self.cfs_dashboard._selected is not None:
                    self.cfs_dashboard._select(self.cfs_dashboard._selected)

            self.app.after(0, apply)

        threading.Thread(target=work, daemon=True).start()

    def _bind_cfs_spool_slot(self, index: int) -> None:
        if index < 0 or index >= len(self._cfs_slots):
            return
        slot = self._cfs_slots[index]
        if hasattr(self.app, "bind_cfs_slot_dialog"):
            self.app.bind_cfs_slot_dialog(index, slot)

    def _adopt_cfs_slot(self, index: int) -> None:
        if index < 0 or index >= len(self._cfs_slots):
            return
        slot = self._cfs_slots[index]
        if slot.empty:
            notify(self, f"Slot {slot.label}: kein Material — Spule einlegen oder manuell wählen.", "warn")
            return
        if hasattr(self.app, "apply_cfs_slot"):
            self.app.apply_cfs_slot(slot)

    def _cfs_feed(self) -> None:
        host = self._host()
        if not host:
            return
        sel = self.cfs_dashboard._selected
        if sel is None:
            notify(self, "Bitte zuerst einen CFS-Slot (1A–1D) wählen.", "warn")
            return
        snap = self._conn.snapshot() if self._conn else {}
        box_id = get_cfs_box_id(snap)

        def work() -> None:
            feed_filament(host, box_id, sel, self._conn)
            self.app.after(
                0,
                lambda: notify(self, f"Zufuhr gestartet — Slot {SLOT_LABELS[sel]}", "ok"),
            )

        self._run_bg("CFS Zufuhr", work)

    def _cfs_retract(self) -> None:
        host = self._host()
        if not host:
            return
        sel = self.cfs_dashboard._selected
        if sel is None:
            notify(self, "Bitte zuerst einen CFS-Slot wählen.", "warn")
            return
        snap = self._conn.snapshot() if self._conn else {}
        box_id = get_cfs_box_id(snap)

        def work() -> None:
            retract_filament(host, box_id, sel, self._conn)
            self.app.after(
                0,
                lambda: notify(self, f"Zurückziehen — Slot {SLOT_LABELS[sel]}", "ok"),
            )

        self._run_bg("CFS Zurück", work)

    def _refresh_cfs(self) -> None:
        host = self._host()
        if not host:
            return
        if self._conn and self._conn.connected:
            self._conn.request_get(boxsInfo=1, reqPrintObjects=1)

            def work_connected() -> None:
                self._conn.wait_for_boxs_info(4.0)
                snap = self._conn.snapshot()
                if all(slot.empty for slot in parse_cfs_slots(snap)):
                    try:
                        snap = fetch_ws_snapshot(
                            host, timeout=6.0, boxsInfo=1, reqPrintObjects=1
                        )
                    except Exception:
                        pass
                self.app.after(0, lambda: self._apply_state(snap))

            threading.Thread(target=work_connected, daemon=True).start()
            self._fetch_cfs_snapshot_async()
            return

        def work_standalone() -> None:
            try:
                snap = fetch_ws_snapshot(host, timeout=5.0, boxsInfo=1, reqPrintObjects=1)
                self.app.after(0, lambda: self._apply_state(snap))
            except Exception as exc:
                self.app.after(0, lambda: notify(self, str(exc), "error"))

        threading.Thread(target=work_standalone, daemon=True).start()

    def _set_light(self, on: bool) -> None:
        if self._ui_lock:
            return
        self.led_var.set(on)
        self._toggle_led()

    def _toggle_led(self) -> None:
        if self._ui_lock:
            return
        host = self._host()
        if not host:
            return

        def work() -> None:
            if self.led_var.get():
                self._send(host, lightSw=1)
            else:
                self._send(host, lightSw=0)

        def runner() -> None:
            try:
                work()
            except Exception as exc:
                self.app.after(0, lambda: notify(self, str(exc), "error"))

        threading.Thread(target=runner, daemon=True).start()

    def _apply_fan(self, channel: int) -> None:
        host = self._host()
        if not host:
            return
        pct = self.fan_vars[channel].get()
        s_val = int(round(255 * (max(0, min(100, pct)) / 100.0)))

        def work() -> None:
            self._send(host, gcodeCmd=f"M106 P{channel} S{s_val}")

        self._run_bg(f"Lüfter {channel}", work)

    def _send(self, host: str, **params) -> None:
        if self._conn and self._conn.connected:
            self._conn.send_set(**params)
        else:
            send_set_once(host, **params)

    def _run_bg(self, label: str, work) -> None:
        def runner() -> None:
            try:
                work()
                self.app.after(0, lambda: notify(self, f"{label} OK", "ok"))
            except Exception as exc:
                self.app.after(0, lambda: notify(self, str(exc), "error"))

        threading.Thread(target=runner, daemon=True).start()

    @staticmethod
    def _speed_from_state(s: dict) -> int | None:
        try:
            if s.get("speedMode") is not None and int(s.get("speedMode")) == 1:
                return 25
        except (TypeError, ValueError):
            pass
        raw = s.get("curFeedratePct", s.get("curFlowratePct"))
        if raw is None:
            return None
        try:
            v = int(round(float(raw)))
        except (TypeError, ValueError):
            return None
        presets = [p for p, _ in PRINT_SPEED_PRESETS]
        return min(presets, key=lambda p: abs(p - v))

    def _apply_speed_preset(self, percent: int) -> None:
        if self._ui_lock:
            return
        host = self._host()
        if not host:
            return
        self._speed_lock_until = time.monotonic() + 3.0
        self._speed_var.set(percent)

        def work() -> None:
            if self._conn and self._conn.connected:
                if percent == 25:
                    self._conn.send_set(speedMode=1)
                else:
                    self._conn.send_set(speedMode=0, setFeedratePct=percent)
            else:
                set_print_speed(host, percent)

        self._run_bg(f"Geschwindigkeit {percent}%", work)

    @staticmethod
    def _gcode_sig(files: list[dict]) -> tuple:
        return tuple((f.get("path"), f.get("mtime"), f.get("name")) for f in files)

    def _set_gcode_files(self, files: list[dict]) -> None:
        if not files:
            return
        if self._gcode_sig(files) == self._gcode_sig(self._gcode_files):
            return
        self._gcode_files = files
        try:
            yview = self.file_list.yview()
        except tk.TclError:
            yview = (0.0, 1.0)
        sel = self.file_list.curselection()
        self.file_list.delete(0, tk.END)
        for f in files:
            name = f.get("name") or "?"
            parts: list[str] = [str(name)]
            when = format_gcode_mtime(f.get("mtime"))
            if when:
                parts.append(when)
            size = f.get("size")
            if size is not None:
                try:
                    mb = float(size) / (1024 * 1024)
                    parts.append(f"{mb:.1f} MB")
                except (TypeError, ValueError):
                    pass
            label = "  ·  ".join(parts)
            self.file_list.insert(tk.END, label)
        if sel and sel[0] < len(files):
            self.file_list.selection_set(sel[0])
        try:
            self.file_list.yview_moveto(yview[0])
        except tk.TclError:
            pass

    def _selected_gcode_entry(self) -> dict | None:
        sel = self.file_list.curselection()
        if not sel:
            return None
        idx = int(sel[0])
        if idx < 0 or idx >= len(self._gcode_files):
            return None
        return self._gcode_files[idx]

    @staticmethod
    def _normalize_gcode_basename(name: str) -> str:
        return name.strip().replace("\\", "/").rsplit("/", 1)[-1].lower()

    def _find_gcode_entry_by_name(self, name: str) -> dict | None:
        if not name or name in ("—", "-", "?"):
            return None
        base = self._normalize_gcode_basename(name)
        if not base:
            return None
        partial: dict | None = None
        for entry in self._gcode_files:
            fn = self._normalize_gcode_basename(str(entry.get("name") or ""))
            fp = self._normalize_gcode_basename(str(entry.get("path") or ""))
            if fn == base or fp == base:
                return entry
            if partial is None and base and (base in fn or fn in base or base in fp):
                partial = entry
        return partial

    def _sync_listbox_to_filename(self, fname: str) -> None:
        entry = self._find_gcode_entry_by_name(fname)
        if not entry:
            return
        for i, f in enumerate(self._gcode_files):
            if (f.get("name") or "") == (entry.get("name") or "") or (
                f.get("path") or ""
            ) == (entry.get("path") or ""):
                try:
                    yview = self.file_list.yview()
                    self.file_list.selection_clear(0, tk.END)
                    self.file_list.selection_set(i)
                    self.file_list.yview_moveto(yview[0])
                except tk.TclError:
                    pass
                self._last_gcode_entry = f
                return

    def _download_gcode(self) -> None:
        host = self._host()
        if not host:
            return
        entry = self._selected_gcode_entry()
        if not entry:
            notify(self, "Bitte zuerst eine G-Code-Datei in der Liste wählen.", "warn")
            return
        name = entry.get("name") or "druck.gcode"
        if not str(name).lower().endswith(".gcode"):
            name = f"{name}.gcode"
        local = filedialog.asksaveasfilename(
            title="G-Code vom Drucker speichern",
            initialfile=name,
            defaultextension=".gcode",
            filetypes=[("G-Code", "*.gcode"), ("Alle Dateien", "*.*")],
        )
        if not local:
            return
        password = self._ssh_password()
        try:
            remote = entry_remote_path(entry)
        except ValueError as exc:
            notify(self, str(exc), "warn")
            return

        def work() -> None:
            try:
                download_gcode_from_printer(host, password, remote, local)
                try:
                    from app.paths import GCODE_CACHE_DIR

                    GCODE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
                    cache_copy = GCODE_CACHE_DIR / Path(local).name
                    shutil.copy2(local, cache_copy)
                except Exception:
                    pass
                self.app.after(
                    0,
                    lambda: notify(
                        self,
                        f"Gespeichert:\n{local}\n\n"
                        "Kopie für Verbrauchsschätzung: data/gcode_cache/",
                        "ok",
                    ),
                )
                self.app.after(0, lambda: self._status_var.set(f"Heruntergeladen: {name}"))
            except Exception as exc:
                self.app.after(0, lambda: notify(self, str(exc), "error"))

        self._status_var.set(f"Lade {name}…")
        threading.Thread(target=work, daemon=True).start()

    def _delete_gcode(self) -> None:
        host = self._host()
        if not host:
            return
        entry = self._selected_gcode_entry()
        if not entry:
            notify(self, "Bitte zuerst eine G-Code-Datei wählen.", "warn")
            return
        name = entry.get("name") or entry.get("path") or "?"
        try:
            remote = entry_remote_path(entry)
        except ValueError as exc:
            notify(self, str(exc), "warn")
            return
        password = self._ssh_password()

        def do() -> None:
            self._status_var.set(f"Lösche {name}…")

            def work() -> None:
                err: str | None = None
                if self._conn and self._conn.connected:
                    try:
                        delete_gcode_file(host, remote, self._conn)
                    except Exception as exc:
                        try:
                            delete_gcode_on_printer_ssh(host, password, remote)
                        except Exception as exc2:
                            err = f"{exc}\n\nSSH: {exc2}"
                else:
                    try:
                        delete_gcode_on_printer_ssh(host, password, remote)
                    except Exception as exc:
                        err = str(exc)

                def done() -> None:
                    if err:
                        notify(self, err, "error")
                        self._status_var.set("Löschen fehlgeschlagen")
                        return
                    notify(self, f"„{name}“ gelöscht.", "ok")
                    self._status_var.set(f"Gelöscht: {name}")
                    if self._conn and self._conn.connected:
                        self._conn.request_get(
                            reqGcodeList=1, reqGcodeFile=1, reqGcodeFileInfo2=1
                        )
                    self._refresh_gcode_list()

                self.app.after(0, done)

            threading.Thread(target=work, daemon=True).start()

        confirm(self, f"„{name}“ wirklich vom Drucker löschen?", do)

    def _upload_gcode(self) -> None:
        host = self._host()
        if not host:
            return
        path = filedialog.askopenfilename(
            title="G-Code auf den Drucker kopieren",
            filetypes=[("G-Code", "*.gcode"), ("Alle Dateien", "*.*")],
        )
        if not path:
            return
        password = self._ssh_password()
        from printer_connect import save_settings

        save_settings(host, password, self.app.printer_var.get().strip() or "K2 Pro")

        def work() -> None:
            try:
                remote = upload_gcode_to_printer(host, password, path)
                self.app.after(0, lambda: self._after_gcode_upload(remote, path))
            except Exception as exc:
                self.app.after(0, lambda: notify(self, str(exc), "error"))

        self._status_var.set("G-Code wird hochgeladen…")
        threading.Thread(target=work, daemon=True).start()

    def _after_gcode_upload(self, remote: str, local_path: str) -> None:
        from pathlib import Path

        name = Path(local_path).name
        self._status_var.set(f"Hochgeladen: {name}")
        notify(self, f"Datei auf dem Drucker:\n{remote}\n\nListe wird aktualisiert…", "ok")
        if self._conn and self._conn.connected:
            self._conn.request_get(reqGcodeList=1, reqGcodeFile=1, reqGcodeFileInfo2=1)
        else:
            self._refresh_gcode_list()

    def _fetch_gcode_list_ssh(self) -> None:
        host = self._host()
        if not host:
            return
        password = self._ssh_password()

        def work() -> None:
            try:
                files = list_gcode_files_ssh(host, password)
            except Exception:
                files = []

            def done() -> None:
                if files:
                    self._set_gcode_files(files)
                    self._status_var.set(f"{len(files)} Dateien (SSH)")
                elif not self._gcode_files:
                    self._status_var.set("Keine Dateien — SSH/Root prüfen")

            self.app.after(0, done)

        threading.Thread(target=work, daemon=True).start()

    def _refresh_gcode_list(self) -> None:
        host = self._host()
        if not host:
            return
        self._gcode_ssh_tried = False
        self._gcode_polls = 0
        self._status_var.set("G-Code-Liste wird geladen…")
        if self._conn and self._conn.connected:
            self._conn.request_get(
                reqGcodeList=1, reqGcodeFile=1, reqGcodeFileInfo2=1, boxsInfo=1
            )
        else:
            try:
                request_gcode_list(host)
            except Exception:
                pass
        self._fetch_gcode_list_ssh()
        self._status_var.set("Dateiliste wird geladen…")

    def _on_gcode_select(self, _evt=None) -> None:
        sel = self.file_list.curselection()
        if not sel:
            self._clear_gcode_preview()
            return
        host = self._host()
        if not host:
            return
        idx = int(sel[0])
        if idx < 0 or idx >= len(self._gcode_files):
            return
        entry = self._gcode_files[idx]
        self._last_gcode_entry = entry
        name = entry.get("name") or "?"
        self._gcode_preview_hold = True
        self.gcode_preview_label.config(image="", text=f"Vorschaubild lädt…\n{name}")
        self.gcode_preview_label.place(relx=0, rely=0, relwidth=1, relheight=1)
        threading.Thread(
            target=self._load_gcode_preview_bg,
            args=(host, entry),
            daemon=True,
        ).start()

    def _load_gcode_preview_bg(self, host: str, entry: dict) -> None:
        urls = thumbnail_urls_for_file(host, entry)
        shot = fetch_image_urls(urls) if urls else None
        name = entry.get("name") or "?"

        def done() -> None:
            if not self._gcode_preview_hold:
                return
            if not shot:
                self.gcode_preview_label.config(
                    image="",
                    text=f"Kein Vorschaubild\n{name}\n\n(nur beim Slicen erzeugt)",
                )
                return
            data, _ = shot
            try:
                from PIL import Image

                self._preview_pil = Image.open(io.BytesIO(data))
                self._fit_gcode_preview_image()
            except Exception:
                self.gcode_preview_label.config(image="", text=f"Vorschaubild fehlerhaft\n{name}")

        self.app.after(0, done)

    def _apply_nozzle(self) -> None:
        host = self._host()
        if not host:
            return
        self._lock_temp_spinboxes()
        v = self.nozzle_tgt.get()

        def work() -> None:
            self._send(host, nozzleTempControl=int(v))

        self._run_bg("Düsentemp.", work)

    def _apply_bed(self) -> None:
        host = self._host()
        if not host:
            return
        self._lock_temp_spinboxes()
        v = self.bed_tgt.get()

        def work() -> None:
            self._send(host, bedTempControl={"num": 0, "val": int(v)})

        self._run_bg("Betttemp.", work)

    def _apply_chamber(self) -> None:
        host = self._host()
        if not host:
            return
        self._lock_temp_spinboxes()
        v = self.box_tgt.get()

        def work() -> None:
            self._send(host, boxTempControl=int(v))

        self._run_bg("Kammertemp.", work)

    def _cmd(self, label: str, fn) -> None:
        host = self._host()
        if not host:
            return

        def runner() -> None:
            try:
                fn(host)
                self.app.after(0, lambda: notify(self, f"{label} OK", "ok"))
            except Exception as exc:
                self.app.after(0, lambda: notify(self, str(exc), "error"))

        threading.Thread(target=runner, daemon=True).start()

    def _stop_print(self) -> None:
        host = self._host()
        if not host:
            return

        def do() -> None:
            def work() -> None:
                send_print_params(host, {"stop": 1}, self._conn)
                self.app.after(0, lambda: notify(self, "Stopp gesendet", "ok"))

            self._run_bg("Stopp", work)

        confirm(self, f"Druck auf {host} wirklich stoppen?", do)

    def _open_creality_web_ui(self) -> None:
        host = self._host_quiet()
        if not host:
            notify(self, "Bitte zuerst die Drucker-IP im Tab „RFID-Tag“ eintragen.", "warn")
            return
        open_url(f"http://{host}/")

    def open_klipper_ui(self) -> None:
        host = self._host()
        if not host:
            return
        self._status_var.set("Klipper/Moonraker wird geprüft…")

        def work() -> None:
            probe = probe_klipper(host)
            url = best_ui_url(host)

            def done() -> None:
                if url:
                    open_url(url)
                msg = probe.summary()
                if probe.moonraker:
                    msg += "\n\nMoonraker-API: Port 7125 (Klipper-Status, G-Code u. a.)"
                else:
                    msg += (
                        "\n\nMoonraker nicht erreichbar — K2 nutzt oft nur Creality-WebSocket (9999). "
                        "Root/SSH in den Drucker-Einstellungen aktivieren."
                    )
                self._status_var.set(probe.summary()[:120])
                notify(self, msg, "ok" if probe.moonraker or probe.ui_links else "warn")

            self.app.after(0, done)

        threading.Thread(target=work, daemon=True).start()
