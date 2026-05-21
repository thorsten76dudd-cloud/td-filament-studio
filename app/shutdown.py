"""Sauberes Beenden — Hintergrund-Threads/Prozesse stoppen (PyInstaller _MEI-Warnung vermeiden)."""

from __future__ import annotations

import gc
import logging
import sys
import time
from typing import Any

import tkinter as tk

log = logging.getLogger(__name__)


def cancel_all_after_callbacks(root: tk.Misc) -> None:
    """Alle geplanten tk.after-Events abbrechen."""
    try:
        ids = root.tk.call("after", "info")
    except tk.TclError:
        return
    if not ids:
        return
    if isinstance(ids, str):
        ids = (ids,)
    for aid in ids:
        try:
            root.after_cancel(aid)
        except tk.TclError:
            pass


def shutdown_application(app: Any) -> None:
    """Vor tk destroy: NFC, Drucker-WS, Kamera, go2rtc beenden."""
    try:
        cancel_all_after_callbacks(app)
    except Exception as exc:
        log.debug("after cancel: %s", exc)

    poll_after = getattr(app, "_reader_poll_after", None)
    if poll_after:
        try:
            app.after_cancel(poll_after)
        except tk.TclError:
            pass
        app._reader_poll_after = None

    if getattr(app, "_monitor", None):
        try:
            app._monitor.stop()
            app._monitor = None
        except Exception as exc:
            log.debug("monitor stop: %s", exc)

    if hasattr(app, "_device_panel"):
        try:
            app._device_panel.disconnect()
        except Exception as exc:
            log.debug("printer disconnect: %s", exc)

    try:
        from creality_nfc.k2_camera_live import K2CameraViewerServer

        with K2CameraViewerServer._lock:
            shared = K2CameraViewerServer._shared
        if shared:
            shared.stop()
            with K2CameraViewerServer._lock:
                K2CameraViewerServer._shared = None
    except Exception as exc:
        log.debug("camera viewer stop: %s", exc)

    try:
        from creality_nfc.stl_preview_server import StlPreviewServer

        with StlPreviewServer._lock:
            shared = StlPreviewServer._shared
        if shared:
            shared.stop()
            with StlPreviewServer._lock:
                StlPreviewServer._shared = None
    except Exception as exc:
        log.debug("stl preview stop: %s", exc)

    gc.collect()
    time.sleep(0.5 if getattr(sys, "frozen", False) else 0.15)


def hard_exit_frozen(exit_code: int = 0) -> None:
    """
    PyInstaller: normaler Exit löst oft „Failed to remove temporary directory _MEI…“ aus
    (DLLs von NFC/Kamera/Threads noch offen). os._exit überspringt Bootloader-Cleanup.
    """
    if getattr(sys, "frozen", False):
        import os

        os._exit(exit_code)


def exit_process_after_frozen_app() -> None:
    hard_exit_frozen(0)
