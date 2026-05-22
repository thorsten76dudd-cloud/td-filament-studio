"""Desktop-Benachrichtigungen (Windows-Toast) mit App-Einstellungen."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from creality_nfc.app_settings import AppSettings


def show_desktop_notification(
    title: str,
    message: str,
    *,
    settings: AppSettings | None = None,
    enabled: bool = True,
) -> None:
    if not enabled:
        return
    if settings is not None and not getattr(settings, "alert_print_windows_toast", True):
        return

    def _run() -> None:
        from creality_nfc.windows_toast import show_windows_toast

        show_windows_toast(title, message.replace("\n", " — "))

    threading.Thread(target=_run, name="desktop-toast", daemon=True).start()
