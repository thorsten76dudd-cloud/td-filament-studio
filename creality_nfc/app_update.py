"""In-App-Update: Setup laden, alle App-Prozesse beenden, Installer starten."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path

_SETUP_NAME = "TD-Filament-Studio-Setup.exe"


def kill_all_app_processes() -> None:
    """Haupt-App und Creality-Wächter (gleiche EXE) beenden."""
    if sys.platform != "win32":
        return
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.run(
        ["taskkill", "/IM", "TD Filament Studio.exe", "/F", "/T"],
        capture_output=True,
        creationflags=flags,
    )
    time.sleep(0.8)


def download_setup(
    url: str,
    dest: Path,
    *,
    on_progress: Callable[[int, int], None] | None = None,
) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "TD-Filament-Studio"})
    with urllib.request.urlopen(req, timeout=300) as resp, dest.open("wb") as out:
        total_hdr = resp.headers.get("Content-Length")
        total = int(total_hdr) if total_hdr and str(total_hdr).isdigit() else 0
        received = 0
        while True:
            chunk = resp.read(1024 * 256)
            if not chunk:
                break
            out.write(chunk)
            received += len(chunk)
            if on_progress:
                on_progress(received, total)


def default_setup_download_path() -> Path:
    return Path(tempfile.gettempdir()) / "td_filament_studio" / _SETUP_NAME


def install_downloaded_setup(setup_path: Path) -> None:
    """Installer starten und diesen Prozess sofort beenden (kein Datei-Lock)."""
    setup_path = setup_path.resolve()
    if not setup_path.is_file():
        raise FileNotFoundError(setup_path)
    kill_all_app_processes()
    subprocess.Popen(
        [str(setup_path)],
        close_fds=True,
        creationflags=getattr(subprocess, "DETACHED_PROCESS", 0)
        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    from app.shutdown import hard_exit_frozen

    hard_exit_frozen(0)
