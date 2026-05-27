"""In-App-Update: Setup laden, alle App-Prozesse beenden, Installer starten."""

from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path

_SETUP_NAME = "TD-Filament-Studio-Setup.exe"
_MIN_SETUP_BYTES = 5_000_000
_INNO_SETUP_ARGS = "/FORCECLOSEAPPLICATIONS"

_CREATE_BREAKAWAY_FROM_JOB = 0x01000000
_DETACHED_PROCESS = 0x00000008
_CREATE_NO_WINDOW = 0x08000000


def _update_log(message: str) -> None:
    try:
        base = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "TD Filament Studio" / "data"
        base.mkdir(parents=True, exist_ok=True)
        path = base / "update_install.log"
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with path.open("a", encoding="utf-8") as fh:
            fh.write(f"[{stamp}] {message}\n")
    except OSError:
        pass


def unblock_setup_file(setup_path: Path) -> None:
    """Mark-of-the-Web entfernen (Browser-Download blockiert oft die Installation)."""
    if sys.platform != "win32":
        return
    setup_path = setup_path.resolve()
    try:
        k32 = ctypes.windll.kernel32
        stream = str(setup_path) + ":Zone.Identifier"
        if k32.DeleteFileW(stream):
            _update_log(f"Zone.Identifier entfernt: {setup_path}")
            return
    except Exception:
        pass
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                f"Unblock-File -LiteralPath '{setup_path}'",
            ],
            capture_output=True,
            creationflags=flags,
            timeout=30,
        )
        _update_log(f"Unblock-File: {setup_path}")
    except (OSError, subprocess.SubprocessError) as exc:
        _update_log(f"Unblock-File fehlgeschlagen: {exc}")


def kill_all_app_processes() -> None:
    """
    Haupt-App und Wächter beenden.
    WICHTIG: ohne /T — sonst werden frisch gestartete Installer-Helfer (cmd/wscript) mit beendet.
    """
    if sys.platform != "win32":
        return
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    for _ in range(3):
        subprocess.run(
            ["taskkill", "/IM", "TD Filament Studio.exe", "/F"],
            capture_output=True,
            creationflags=flags,
        )
        time.sleep(0.6)


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
    unblock_setup_file(dest)


def default_setup_download_path() -> Path:
    """Stabiler Ordner (nicht nur %TEMP%) — weniger SmartScreen-Probleme."""
    base = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "TD Filament Studio" / "Updates"
    base.mkdir(parents=True, exist_ok=True)
    return base / _SETUP_NAME


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


def stage_setup_for_install(setup_path: Path) -> Path:
    """Setup in Updates-Ordner legen (für Installer + VBS-Helfer)."""
    dest = default_setup_download_path()
    setup_path = setup_path.resolve()
    if setup_path != dest.resolve():
        shutil.copy2(setup_path, dest)
    return dest


def _shell_execute(file: str, params: str = "", *, show: int = 1) -> None:
    import ctypes

    ret = ctypes.windll.shell32.ShellExecuteW(None, "open", file, params or None, None, show)
    if ret <= 32:
        raise OSError(f"ShellExecute fehlgeschlagen (Code {ret})")


def _launch_installer_exe(setup_path: Path) -> None:
    """Installer direkt starten (Fallback wenn wscript blockiert ist)."""
    setup_path = setup_path.resolve()
    unblock_setup_file(setup_path)
    args = [str(setup_path), _INNO_SETUP_ARGS]
    flags = _DETACHED_PROCESS | _CREATE_NO_WINDOW | _CREATE_BREAKAWAY_FROM_JOB
    subprocess.Popen(args, close_fds=True, creationflags=flags)
    _update_log(f"Installer direkt gestartet: {setup_path}")


def _schedule_windows_installer(setup_path: Path) -> None:
    """
    Installer per WScript starten — eigener Prozess, überlebt taskkill/os._exit.
    """
    setup_path = setup_path.resolve()
    unblock_setup_file(setup_path)
    vbs_path = setup_path.parent / "_td_run_setup.vbs"
    run_cmd = f'"{setup_path}" {_INNO_SETUP_ARGS}'.replace('"', '""')
    vbs_path.write_text(
        "WScript.Sleep 4000\n"
        "Set sh = CreateObject(\"WScript.Shell\")\n"
        f'sh.Run "{run_cmd}", 1, False\n',
        encoding="utf-8",
    )
    _update_log(f"VBS-Launcher geschrieben: {vbs_path}")
    try:
        flags = _DETACHED_PROCESS | _CREATE_NO_WINDOW | _CREATE_BREAKAWAY_FROM_JOB
        subprocess.Popen(
            ["wscript.exe", "//B", str(vbs_path)],
            close_fds=True,
            creationflags=flags,
        )
        _update_log("wscript.exe gestartet (Installer in ~4 s)")
    except OSError as exc:
        _update_log(f"wscript fehlgeschlagen ({exc}) — direkter Start")
        _launch_installer_exe(setup_path)


def install_downloaded_setup(setup_path: Path) -> None:
    """Installer starten und diesen Prozess sofort beenden (kein Datei-Lock)."""
    staged = stage_setup_for_install(setup_path)
    unblock_setup_file(staged)
    validate_setup_exe(staged)
    _update_log(f"install_downloaded_setup: {staged}")
    if sys.platform == "win32":
        _schedule_windows_installer(staged)
        time.sleep(1.2)
        kill_all_app_processes()
    else:
        subprocess.Popen([str(staged)], close_fds=True)
    from app.shutdown import hard_exit_frozen

    hard_exit_frozen(0)
