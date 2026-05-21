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
_MIN_SETUP_BYTES = 5_000_000

# Windows: Installer aus PyInstaller-Job lösen (sonst stirbt er mit os._exit)
_CREATE_BREAKAWAY_FROM_JOB = 0x01000000
_DETACHED_PROCESS = 0x00000008
_CREATE_NO_WINDOW = 0x08000000


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


def validate_setup_exe(setup_path: Path) -> None:
    """Prüfen, ob der Download eine echte Setup-EXE ist (kein HTML/Fehler)."""
    setup_path = setup_path.resolve()
    if not setup_path.is_file():
        raise FileNotFoundError(setup_path)
    size = setup_path.stat().st_size
    if size < _MIN_SETUP_BYTES:
        raise ValueError(
            f"Setup-Datei zu klein ({size // 1024} KB) — Download unvollständig oder fehlerhaft."
        )
    with setup_path.open("rb") as fh:
        if fh.read(2) != b"MZ":
            raise ValueError("Keine gültige Windows-EXE — bitte Setup im Browser erneut laden.")


def _schedule_windows_installer(setup_path: Path) -> None:
    """
    Installer per eigenem CMD starten (überlebt App-Ende / PyInstaller os._exit).
    Kurze Verzögerung, damit taskkill die EXE freigibt.
    """
    setup_path = setup_path.resolve()
    cmd_path = setup_path.parent / "_td_install_update.cmd"
    cmd_path.write_text(
        "@echo off\r\n"
        "ping -n 3 127.0.0.1 >nul\r\n"
        f'start "" "{setup_path}"\r\n'
        'del "%~f0" 2>nul\r\n',
        encoding="utf-8",
    )
    flags = _DETACHED_PROCESS | _CREATE_NO_WINDOW | _CREATE_BREAKAWAY_FROM_JOB
    subprocess.Popen(
        ["cmd.exe", "/c", str(cmd_path)],
        close_fds=True,
        creationflags=flags,
    )


def install_downloaded_setup(setup_path: Path) -> None:
    """Installer starten und diesen Prozess sofort beenden (kein Datei-Lock)."""
    setup_path = setup_path.resolve()
    validate_setup_exe(setup_path)
    if sys.platform == "win32":
        _schedule_windows_installer(setup_path)
        kill_all_app_processes()
    else:
        subprocess.Popen([str(setup_path)], close_fds=True)
    from app.shutdown import hard_exit_frozen

    hard_exit_frozen(0)
