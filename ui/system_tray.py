"""System-Tray für Hintergrundbetrieb (Windows)."""

from __future__ import annotations

import logging
import sys
import threading
from collections.abc import Callable
from typing import Any

log = logging.getLogger(__name__)


def tray_supported() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import pystray  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError:
        return False
    return load_tray_image() is not None


def load_tray_image() -> Any | None:
    from ui.app_icon import load_tray_pil_image

    return load_tray_pil_image()


class BackgroundTray:
    """Tray-Icon in eigenem Thread (pystray)."""

    def __init__(self) -> None:
        self._icon: Any | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    @property
    def running(self) -> bool:
        with self._lock:
            return self._icon is not None

    def start(
        self,
        *,
        on_show: Callable[[], None],
        on_quit: Callable[[], None],
        tooltip: str = "TD Filament Studio",
    ) -> bool:
        if not tray_supported():
            return False
        with self._lock:
            if self._icon is not None:
                return True

        import pystray

        image = load_tray_image()
        if image is None:
            return False

        menu = pystray.Menu(
            pystray.MenuItem("Öffnen", lambda *_: on_show(), default=True),
            pystray.MenuItem("Beenden", lambda *_: on_quit()),
        )
        icon = pystray.Icon("td_filament_studio", image, tooltip, menu)

        def _run() -> None:
            try:
                icon.run()
            except Exception as exc:
                log.debug("tray beendet: %s", exc)
            finally:
                with self._lock:
                    if self._icon is icon:
                        self._icon = None

        with self._lock:
            self._icon = icon
        self._thread = threading.Thread(target=_run, name="td-tray", daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        with self._lock:
            icon = self._icon
            self._icon = None
        if icon is not None:
            try:
                icon.stop()
            except Exception as exc:
                log.debug("tray stop: %s", exc)

    def set_tooltip(self, text: str) -> None:
        with self._lock:
            icon = self._icon
        if icon is not None:
            try:
                icon.title = text
            except Exception:
                pass
