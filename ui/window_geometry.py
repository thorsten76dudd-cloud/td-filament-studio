"""Fenstergröße und -position merken (in app_settings.json)."""

from __future__ import annotations

import re
import tkinter as tk
from collections.abc import Callable
from typing import TYPE_CHECKING

from ui.dialog_theme import center_toplevel

if TYPE_CHECKING:
    from creality_nfc.app_settings import AppSettings

_GEOM_RE = re.compile(r"^(\d+)x(\d+)(?:\+(-?\d+)\+(-?\d+))?$")
_manager: WindowGeometryManager | None = None


def set_window_geometry_manager(manager: WindowGeometryManager | None) -> None:
    global _manager
    _manager = manager


def get_window_geometry_manager() -> WindowGeometryManager | None:
    return _manager


def parse_geometry(geom: str) -> tuple[int, int, int | None, int | None] | None:
    m = _GEOM_RE.match((geom or "").strip())
    if not m:
        return None
    w, h = int(m.group(1)), int(m.group(2))
    x = int(m.group(3)) if m.group(3) is not None else None
    y = int(m.group(4)) if m.group(4) is not None else None
    return w, h, x, y


def format_geometry(
    width: int,
    height: int,
    x: int | None = None,
    y: int | None = None,
) -> str:
    if x is None or y is None:
        return f"{width}x{height}"
    return f"{width}x{height}+{x}+{y}"


_SCREEN_MARGIN = 48
_TABLE_DIALOG_KEYS = frozenset({"print_history", "spool_location"})


def clear_table_dialog_geometries(store: dict[str, str]) -> bool:
    """Kaputte gespeicherte Tabellen-Dialoge entfernen (Inhalt war unsichtbar)."""
    changed = False
    for key in _TABLE_DIALOG_KEYS:
        if key in store:
            del store[key]
            changed = True
    return changed


def clamp_geometry(
    geom: str,
    *,
    screen_w: int,
    screen_h: int,
    min_w: int = 320,
    min_h: int = 200,
) -> str:
    parsed = parse_geometry(geom)
    if not parsed:
        return geom
    w, h, x, y = parsed
    max_w = max(min_w, screen_w - _SCREEN_MARGIN)
    max_h = max(min_h, screen_h - _SCREEN_MARGIN)
    w = max(min_w, min(w, max_w))
    h = max(min_h, min(h, max_h))
    if x is not None and y is not None:
        x = max(0, min(x, max(0, screen_w - w)))
        y = max(0, min(y, max(0, screen_h - h)))
        return format_geometry(w, h, x, y)
    return format_geometry(w, h)


def repair_stored_window_geometries(
    store: dict[str, str],
    *,
    screen_w: int,
    screen_h: int,
) -> bool:
    """Zu breite/hohe oder teilweise unsichtbare Dialoge auf den Bildschirm bringen."""
    changed = False
    for key in list(store.keys()):
        geom = store.get(key) or ""
        parsed = parse_geometry(geom)
        if not parsed:
            continue
        w, h, x, y = parsed
        max_w = max(320, screen_w - _SCREEN_MARGIN)
        max_h = max(200, screen_h - _SCREEN_MARGIN)
        cap_w = 920 if key in _TABLE_DIALOG_KEYS else max_w
        off_screen = (
            w > max_w
            or w > cap_w
            or h > max_h
            or (x is not None and x + w > screen_w)
            or (y is not None and y + h > screen_h)
            or (x is not None and x < 0)
        )
        if off_screen:
            store[key] = clamp_geometry(
                geom,
                screen_w=screen_w,
                screen_h=screen_h,
                min_w=min(320, cap_w),
            )
            if key in _TABLE_DIALOG_KEYS:
                p2 = parse_geometry(store[key])
                if p2 and p2[0] > cap_w:
                    store[key] = format_geometry(cap_w, p2[1], p2[2], p2[3])
            changed = True
    return changed


class WindowGeometryManager:
    """Speichert Geometrie in AppSettings.window_geometry."""

    _MAX_KEYS = 96
    _SAVE_DEBOUNCE_MS = 450

    def __init__(self, settings: AppSettings, save_fn: Callable[[], None]) -> None:
        self.settings = settings
        self._save_fn = save_fn
        self._save_after: str | None = None
        self._main_last_normal: str | None = None

    def attach_root(self, win: tk.Tk) -> None:
        if self.settings.main_window_maximized:
            self._try_maximize(win)
        else:
            geom = self.settings.window_geometry.get("main")
            if geom and parse_geometry(geom):
                win.geometry(
                    clamp_geometry(
                        geom,
                        screen_w=win.winfo_screenwidth(),
                        screen_h=win.winfo_screenheight(),
                        min_w=win.minsize()[0] or 1280,
                        min_h=win.minsize()[1] or 800,
                    )
                )
            else:
                self._try_maximize(win)

        def _on_configure(event: tk.Event) -> None:
            if event.widget is not win:
                return
            try:
                if win.state() == "zoomed":
                    return
            except tk.TclError:
                pass
            try:
                g = win.geometry()
            except tk.TclError:
                return
            if g and parse_geometry(g):
                self._main_last_normal = g

        win.bind("<Configure>", _on_configure, add="+")

    def save_root(self, win: tk.Misc) -> None:
        try:
            zoomed = win.state() == "zoomed"
        except tk.TclError:
            zoomed = False
        self.settings.main_window_maximized = zoomed
        geom = self._main_last_normal
        if not zoomed:
            try:
                geom = win.geometry()
            except tk.TclError:
                pass
        if geom and parse_geometry(geom):
            self.remember("main", geom, schedule=False)
        self._schedule_save()

    def attach_toplevel(
        self,
        win: tk.Toplevel,
        key: str,
        *,
        default_width: int,
        default_height: int,
        min_width: int = 0,
        min_height: int = 0,
    ) -> None:
        win._td_geom_min_w = max(0, min_width)  # type: ignore[attr-defined]
        win._td_geom_min_h = max(0, min_height)  # type: ignore[attr-defined]
        if min_width > 0 or min_height > 0:
            win.minsize(max(0, min_width), max(0, min_height))
        self.restore_toplevel(win, key, default_width, default_height)
        win._td_geom_mapped = False  # type: ignore[attr-defined]
        win._td_geom_last: str | None = None  # type: ignore[attr-defined]

        def _on_map(_event: tk.Event) -> None:
            win._td_geom_mapped = True  # type: ignore[attr-defined]

        def _on_configure(event: tk.Event) -> None:
            if event.widget is not win:
                return
            if not getattr(win, "_td_geom_mapped", False):
                return
            try:
                g = win.geometry()
            except tk.TclError:
                return
            if parse_geometry(g):
                win._td_geom_last = g  # type: ignore[attr-defined]

        def _on_destroy(_event: tk.Event) -> None:
            g = getattr(win, "_td_geom_last", None)
            if g:
                self.remember(key, g)

        win.bind("<Map>", _on_map, add="+")
        win.bind("<Configure>", _on_configure, add="+")
        win.bind("<Destroy>", _on_destroy, add="+")

    def restore_toplevel(
        self,
        win: tk.Toplevel,
        key: str,
        default_width: int,
        default_height: int,
    ) -> None:
        min_w = int(getattr(win, "_td_geom_min_w", 0) or 0) or default_width
        min_h = int(getattr(win, "_td_geom_min_h", 0) or 0) or default_height
        geom = self.settings.window_geometry.get(key)
        if geom and parse_geometry(geom):
            parsed = parse_geometry(geom)
            assert parsed is not None
            w, h, _x, _y = parsed
            if w < min_w or h < min_h:
                center_toplevel(win, width=default_width, height=default_height)
                return
            win.geometry(
                clamp_geometry(
                    geom,
                    screen_w=win.winfo_screenwidth(),
                    screen_h=win.winfo_screenheight(),
                    min_w=min_w,
                    min_h=min_h,
                )
            )
            return
        center_toplevel(win, width=default_width, height=default_height)

    def remember(self, key: str, geom: str, *, schedule: bool = True) -> None:
        parsed = parse_geometry(geom)
        if not parsed:
            return
        w, h, x, y = parsed
        if w < 320 or h < 200:
            return
        store = self.settings.window_geometry
        store[key] = format_geometry(w, h, x, y)
        if len(store) > self._MAX_KEYS:
            for old in list(store.keys())[:- self._MAX_KEYS]:
                if old != "main":
                    del store[old]
        if schedule:
            self._schedule_save()

    def _schedule_save(self) -> None:
        root = tk._default_root
        if root is None:
            try:
                self._save_fn()
            except Exception:
                pass
            return
        if self._save_after:
            try:
                root.after_cancel(self._save_after)
            except tk.TclError:
                pass
        self._save_after = root.after(self._SAVE_DEBOUNCE_MS, self._flush_save)

    def _flush_save(self) -> None:
        self._save_after = None
        try:
            self._save_fn()
        except Exception:
            pass

    @staticmethod
    def _try_maximize(win: tk.Misc) -> None:
        try:
            win.state("zoomed")
            return
        except tk.TclError:
            pass
        try:
            win.attributes("-zoomed", True)
        except tk.TclError:
            try:
                win.geometry("1280x900")
            except tk.TclError:
                pass
