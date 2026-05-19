"""Einfaches Fehler- und Ereignisprotokoll (data/app.log)."""

from __future__ import annotations

import traceback
from datetime import datetime, timezone
from pathlib import Path


def _log_path() -> Path:
    from app.paths import DATA_DIR

    return DATA_DIR / "app.log"


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def log_event(message: str) -> None:
    try:
        path = _log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        line = f"[{_stamp()}] {message}\n"
        with path.open("a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass


def log_exception(context: str, exc: BaseException) -> None:
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    log_event(f"{context}: {exc}\n{tb}")
