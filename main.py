#!/usr/bin/env python3
"""TD Filament Studio — entry point."""

from __future__ import annotations

import sys

from app.constants import ensure_data_dir
from app.main_window import TDFilamentStudioApp


def _install_exception_logging() -> None:
    from creality_nfc.app_log import log_exception

    def _hook(exc_type, exc, tb) -> None:
        if exc is not None:
            log_exception("Unbehandelte Ausnahme", exc)
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _hook


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if "--watch-creality" in argv:
        from creality_nfc.creality_watch import run_watch_loop

        ensure_data_dir()
        return run_watch_loop()

    ensure_data_dir()
    _install_exception_logging()
    app = TDFilamentStudioApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
