"""Live-Kamera in Tk-Frame einbetten (Windows: Edge-Fenster per SetParent)."""

from __future__ import annotations

import ctypes
import subprocess
import sys
import threading
import time
import tkinter as tk
from ctypes import wintypes
from typing import Any

from creality_nfc.k2_camera_live import (
    K2CameraViewerServer,
    _edge_chrome_paths,
    build_isolated_browser_args,
    make_viewer_title,
    make_viewer_window_id,
)

_WM_SIZE = 0x0005
_SIZE_RESTORED = 0


class EmbeddedEdgeCamera:
    """WebRTC-Viewer (lokaler HTTP-Server) in einem Tk-Frame einbetten."""

    def __init__(self, tk_parent: Any, printer_host: str) -> None:
        self._parent = tk_parent
        self._host = printer_host
        self._proc: subprocess.Popen | None = None
        self._browser_hwnd: int | None = None
        self._browser_pid: int = 0
        self._window_id = ""
        self._window_title = ""
        self._running = False
        self._thread: threading.Thread | None = None
        self._url = ""
        self._resize_after: str | None = None
        self._last_geom: tuple[int, int, int, int] | None = None

    @property
    def active(self) -> bool:
        return self._running and self._browser_hwnd is not None

    def start(self) -> bool:
        if sys.platform != "win32":
            return False
        if self._running and self._browser_hwnd:
            self.resize()
            return True
        if self._running:
            self.stop()
        self._running = True
        self._window_id = make_viewer_window_id()
        self._window_title = make_viewer_title(self._window_id)
        try:
            base = K2CameraViewerServer().start(self._host)
            self._url = f"{base.rstrip('/')}/?win={self._window_id}"
        except OSError:
            self._running = False
            return False
        launched = False
        for exe in _edge_chrome_paths():
            if not exe.is_file():
                continue
            try:
                self._proc = subprocess.Popen(
                    build_isolated_browser_args(exe, self._url),
                    close_fds=True,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                self._browser_pid = int(self._proc.pid)
                launched = True
                break
            except OSError:
                continue
        if not launched:
            self._running = False
            return False
        self._thread = threading.Thread(target=self._embed_loop, name="k2-cam-embed", daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._running = False
        if self._resize_after:
            try:
                self._parent.after_cancel(self._resize_after)
            except tk.TclError:
                pass
            self._resize_after = None
        self._browser_hwnd = None
        self._terminate_browser_proc()
        self._browser_pid = 0

    def resize(self) -> None:
        if sys.platform != "win32" or not self._browser_hwnd:
            return
        try:
            self._parent.update_idletasks()
            parent_hwnd = int(self._parent.winfo_id())
            w, h = _client_pixels(self._parent, parent_hwnd)
            user32 = ctypes.windll.user32
            user32.MoveWindow(self._browser_hwnd, 0, 0, w, h, True)
            lparam = (h & 0xFFFF) << 16 | (w & 0xFFFF)
            user32.SendMessageW(self._browser_hwnd, _WM_SIZE, _SIZE_RESTORED, lparam)
            user32.RedrawWindow(
                self._browser_hwnd,
                None,
                None,
                0x0001 | 0x0004 | 0x0100,  # invalidate | update | allchildren
            )
            user32.ShowWindow(self._browser_hwnd, 5)
        except Exception:
            pass

    def _terminate_browser_proc(self) -> None:
        """Nur den von uns gestarteten Browser-Prozess beenden (nicht den normalen Edge/Chrome)."""
        proc = self._proc
        self._proc = None
        if not proc:
            return
        pid = int(proc.pid)
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            if sys.platform == "win32":
                flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    capture_output=True,
                    creationflags=flags,
                )
            else:
                try:
                    proc.kill()
                except OSError:
                    pass

    def _schedule_resize(self) -> None:
        if self._resize_after:
            try:
                self._parent.after_cancel(self._resize_after)
            except tk.TclError:
                pass
        self._resize_after = self._parent.after(120, self._resize_debounced)

    def _resize_debounced(self) -> None:
        self._resize_after = None
        if not self._browser_hwnd:
            return
        try:
            top = self._parent.winfo_toplevel()
            geom = (
                top.winfo_rootx(),
                top.winfo_rooty(),
                self._parent.winfo_width(),
                self._parent.winfo_height(),
            )
        except tk.TclError:
            geom = None
        if geom and geom != self._last_geom:
            self._last_geom = geom
        self.resize()

    def _embed_loop(self) -> None:
        deadline = time.monotonic() + 12.0
        hwnd: int | None = None
        while self._running and time.monotonic() < deadline:
            hwnd = _find_browser_window(self._window_title, self._browser_pid)
            if hwnd:
                break
            time.sleep(0.25)
        if not hwnd or not self._running:
            return
        try:
            parent_hwnd = int(self._parent.winfo_id())
        except tk.TclError:
            return
        if _reparent(hwnd, parent_hwnd):
            self._browser_hwnd = hwnd
            self._parent.after(0, self._schedule_resize)
            self._parent.after(400, self._schedule_resize)

    def bind_resize(self) -> None:
        self._parent.bind("<Configure>", lambda _e: self._schedule_resize(), add="+")
        try:
            top = self._parent.winfo_toplevel()
            top.bind("<Configure>", lambda _e: self._schedule_resize(), add="+")
            top.bind("<Map>", lambda _e: self._parent.after(150, self._schedule_resize), add="+")
            top.bind(
                "<Visibility>",
                lambda _e: self._parent.after(150, self._schedule_resize),
                add="+",
            )
        except tk.TclError:
            pass


def _client_pixels(tk_widget: Any, hwnd: int) -> tuple[int, int]:
    """Größe des Tk-Frames in echten Pixeln (wichtig bei 2. Monitor / anderer DPI)."""
    rect = wintypes.RECT()
    user32 = ctypes.windll.user32
    if user32.GetClientRect(hwnd, ctypes.byref(rect)):
        w = int(rect.right - rect.left)
        h = int(rect.bottom - rect.top)
        if w > 10 and h > 10:
            return w, h
    try:
        tk_widget.update_idletasks()
        scale = float(tk_widget.tk.call("tk", "scaling"))
    except (tk.TclError, TypeError, ValueError):
        scale = 1.0
    w = max(200, int(tk_widget.winfo_width() * scale))
    h = max(150, int(tk_widget.winfo_height() * scale))
    return w, h


def _hwnd_process_id(hwnd: int) -> int:
    pid = wintypes.DWORD()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(pid.value)


def _find_browser_window(title: str, browser_pid: int) -> int | None:
    """Fenster nur vom gestarteten Kamera-Browser (PID), nicht vom normalen Edge/Chrome."""
    if browser_pid <= 0:
        return None
    user32 = ctypes.windll.user32
    found: list[int] = []
    want = title.strip().lower()

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd: int, _lparam: int) -> bool:
        if _hwnd_process_id(hwnd) != browser_pid:
            return True
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd) + 1
        buf = ctypes.create_unicode_buffer(length)
        user32.GetWindowTextW(hwnd, buf, length)
        got = buf.value.strip().lower()
        if got == want or want in got:
            found.append(hwnd)
            return False
        return True

    user32.EnumWindows(callback, 0)
    return found[0] if found else None


def _reparent(child: int, parent: int) -> bool:
    user32 = ctypes.windll.user32
    gwl_style = -16
    ws_child = 0x40000000
    ws_visible = 0x10000000
    ws_caption = 0x00C00000
    try:
        style = user32.GetWindowLongW(child, gwl_style)
        style = (style & ~ws_caption) | ws_child | ws_visible
        user32.SetWindowLongW(child, gwl_style, style)
        user32.SetParent(child, parent)
        user32.ShowWindow(child, 5)
        return True
    except Exception:
        return False
