"""Three.js-Vorschau in Tk — Edge/Chrome per SetParent (wie K2-Kamera)."""

from __future__ import annotations

import ctypes
import subprocess
import sys
import threading
import time
import tkinter as tk
from ctypes import wintypes
from typing import Any

from creality_nfc.k2_camera_embed import _client_pixels, _hwnd_process_id
from creality_nfc.k2_camera_live import _edge_chrome_paths
from creality_nfc.stl_preview_server import (
    build_stl_browser_args,
    make_viewer_title,
    make_viewer_window_id,
)

_WM_SIZE = 0x0005
_SIZE_RESTORED = 0
_GWL_STYLE = -16
_GWL_EXSTYLE = -20
_WS_CHILD = 0x40000000
_WS_VISIBLE = 0x10000000
_WS_CAPTION = 0x00C00000
_WS_THICKFRAME = 0x00040000
_WS_SYSMENU = 0x00080000
_WS_MINIMIZEBOX = 0x00020000
_WS_MAXIMIZEBOX = 0x00010000
_WS_EX_DLGMODALFRAME = 0x00000001
_WS_EX_WINDOWEDGE = 0x00000100
_WS_EX_CLIENTEDGE = 0x00000200
_SWP_SHOWWINDOW = 0x0040
_SWP_NOZORDER = 0x0004
_SWP_NOACTIVATE = 0x0010


def _find_browser_window(title: str, browser_pid: int) -> int | None:
    """Größtes sichtbares Fenster mit passendem Titel (Haupt-App, nicht Popup)."""
    if browser_pid <= 0:
        return None
    user32 = ctypes.windll.user32
    want = title.strip().lower()
    best_hwnd: int | None = None
    best_area = 0

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd: int, _lparam: int) -> bool:
        nonlocal best_hwnd, best_area
        if _hwnd_process_id(hwnd) != browser_pid:
            return True
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd) + 1
        buf = ctypes.create_unicode_buffer(length)
        user32.GetWindowTextW(hwnd, buf, length)
        got = buf.value.strip().lower()
        if want not in got and got != want:
            return True
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        area = max(0, rect.right - rect.left) * max(0, rect.bottom - rect.top)
        if area > best_area:
            best_area = area
            best_hwnd = hwnd
        return True

    user32.EnumWindows(callback, 0)
    return best_hwnd


def _reparent_fill(child: int, parent: int) -> bool:
    user32 = ctypes.windll.user32
    try:
        style = user32.GetWindowLongW(child, _GWL_STYLE)
        style &= ~(_WS_CAPTION | _WS_THICKFRAME | _WS_SYSMENU | _WS_MINIMIZEBOX | _WS_MAXIMIZEBOX)
        style |= _WS_CHILD | _WS_VISIBLE
        user32.SetWindowLongW(child, _GWL_STYLE, style)
        ex = user32.GetWindowLongW(child, _GWL_EXSTYLE)
        ex &= ~(_WS_EX_DLGMODALFRAME | _WS_EX_WINDOWEDGE | _WS_EX_CLIENTEDGE)
        user32.SetWindowLongW(child, _GWL_EXSTYLE, ex)
        user32.SetParent(child, parent)
        user32.SetWindowPos(
            child,
            0,
            0,
            0,
            0,
            0,
            _SWP_NOZORDER | _SWP_NOACTIVATE | _SWP_SHOWWINDOW,
        )
        return True
    except Exception:
        return False


def _parent_client_size(parent_hwnd: int, tk_widget: Any) -> tuple[int, int]:
    rect = wintypes.RECT()
    user32 = ctypes.windll.user32
    if user32.GetClientRect(parent_hwnd, ctypes.byref(rect)):
        w = int(rect.right - rect.left)
        h = int(rect.bottom - rect.top)
        if w > 20 and h > 20:
            return w, h
    return _client_pixels(tk_widget, parent_hwnd)


def _fit_browser_to_parent(browser_hwnd: int, parent_hwnd: int, tk_widget: Any) -> None:
    user32 = ctypes.windll.user32
    w, h = _parent_client_size(parent_hwnd, tk_widget)
    user32.MoveWindow(browser_hwnd, 0, 0, w, h, True)
    lparam = (h & 0xFFFF) << 16 | (w & 0xFFFF)
    user32.SendMessageW(browser_hwnd, _WM_SIZE, _SIZE_RESTORED, lparam)
    user32.RedrawWindow(browser_hwnd, None, None, 0x0001 | 0x0004 | 0x0100)
    user32.ShowWindow(browser_hwnd, 5)

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def child_cb(child: int, _lp: int) -> bool:
        if user32.IsWindowVisible(child):
            user32.MoveWindow(child, 0, 0, w, h, True)
        return True

    user32.EnumChildWindows(browser_hwnd, child_cb, 0)


class EmbeddedStlPreview:
    def __init__(self, tk_parent: Any) -> None:
        self._parent = tk_parent
        self._proc: subprocess.Popen | None = None
        self._browser_hwnd: int | None = None
        self._browser_pid = 0
        self._window_id = ""
        self._window_title = ""
        self._running = False
        self._thread: threading.Thread | None = None
        self._url = ""
        self._resize_after: str | None = None

    @property
    def active(self) -> bool:
        return self._running and self._browser_hwnd is not None

    def _host_size(self) -> tuple[int, int]:
        try:
            self._parent.update_idletasks()
            w = int(self._parent.winfo_width())
            h = int(self._parent.winfo_height())
            return max(320, w), max(240, h)
        except tk.TclError:
            return 900, 600

    def start(self, base_url: str) -> bool:
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
        self._url = f"{base_url.rstrip('/')}/?win={self._window_id}"
        w, h = self._host_size()
        launched = False
        for exe in _edge_chrome_paths():
            if not exe.is_file():
                continue
            try:
                self._proc = subprocess.Popen(
                    build_stl_browser_args(exe, self._url, width=w, height=h),
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
        self._thread = threading.Thread(target=self._embed_loop, name="stl-preview-embed", daemon=True)
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
        proc = self._proc
        self._proc = None
        if proc:
            pid = int(proc.pid)
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except Exception:
                flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    capture_output=True,
                    creationflags=flags,
                )

    def resize(self) -> None:
        if sys.platform != "win32" or not self._browser_hwnd:
            return
        try:
            self._parent.update_idletasks()
            parent_hwnd = int(self._parent.winfo_id())
            _fit_browser_to_parent(self._browser_hwnd, parent_hwnd, self._parent)
        except Exception:
            pass

    def _schedule_resize(self) -> None:
        if self._resize_after:
            try:
                self._parent.after_cancel(self._resize_after)
            except tk.TclError:
                pass
        self._resize_after = self._parent.after(80, self._resize_debounced)

    def _resize_debounced(self) -> None:
        self._resize_after = None
        self.resize()

    def _schedule_resize_burst(self) -> None:
        for ms in (0, 80, 200, 500, 1000, 1800):
            self._parent.after(ms, self._schedule_resize)

    def _embed_loop(self) -> None:
        deadline = time.monotonic() + 15.0
        hwnd: int | None = None
        while self._running and time.monotonic() < deadline:
            hwnd = _find_browser_window(self._window_title, self._browser_pid)
            if hwnd:
                break
            time.sleep(0.2)
        if not hwnd or not self._running:
            return
        try:
            parent_hwnd = int(self._parent.winfo_id())
        except tk.TclError:
            return
        if _reparent_fill(hwnd, parent_hwnd):
            self._browser_hwnd = hwnd
            self._parent.after(0, self._schedule_resize_burst)

    def bind_resize(self) -> None:
        self._parent.bind("<Configure>", lambda _e: self._schedule_resize(), add="+")
        try:
            top = self._parent.winfo_toplevel()
            top.bind("<Configure>", lambda _e: self._schedule_resize(), add="+")
            top.bind("<Map>", lambda _e: self._schedule_resize_burst(), add="+")
            top.bind("<Visibility>", lambda _e: self._schedule_resize(), add="+")
        except tk.TclError:
            pass
