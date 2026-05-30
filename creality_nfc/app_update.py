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
_SW_SHOW_NORMAL = 1
_MB_OKCANCEL = 0x00000001
_MB_ICONINFORMATION = 0x00000040
_MB_SYSTEMMODAL = 0x00001000
_MB_SETFOREGROUND = 0x00010000
_IDOK = 1


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


def prepare_shutdown_for_update() -> None:
    """Tray-Wächter und Hintergrund-Helfer beenden, bevor der Installer startet."""
    if sys.platform != "win32":
        return
    try:
        from creality_nfc.creality_watch import stop_watcher

        stop_watcher()
        _update_log("Creality-Wächter gestoppt")
    except Exception as exc:
        _update_log(f"stop_watcher: {exc}")


def kill_all_app_processes() -> None:
    """
    Haupt-App, Wächter und zweite Instanzen beenden.
    WICHTIG: ohne /T — sonst werden frisch gestartete Installer-Helfer mit beendet.
    """
    if sys.platform != "win32":
        return
    prepare_shutdown_for_update()
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


def updates_folder() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "TD Filament Studio" / "Updates"
    base.mkdir(parents=True, exist_ok=True)
    return base


def open_updates_folder() -> None:
    """Explorer öffnen — Nutzer findet Setup auch bei Tray/Hintergrund."""
    if sys.platform != "win32":
        return
    try:
        os.startfile(str(updates_folder()))
        _update_log(f"Explorer: {updates_folder()}")
    except OSError as exc:
        _update_log(f"Explorer öffnen fehlgeschlagen: {exc}")


def write_install_now_helper(setup_path: Path) -> Path:
    """Dauerhafte BAT zum manuellen Start, falls In-App-Install hängt."""
    setup_path = setup_path.resolve()
    bat = setup_path.parent / "Setup-jetzt-installieren.bat"
    bat.write_text(
        "@echo off\r\n"
        f'cd /d "{setup_path.parent}"\r\n'
        f'start "" "{setup_path}" {_INNO_SETUP_ARGS}\r\n',
        encoding="utf-8",
    )
    _update_log(f"Helper-BAT: {bat}")
    return bat


def confirm_install_ok(title: str, message: str) -> bool:
    """
    Windows-Systemdialog (sichtbar auch bei Tray / ausgeblendetem Fenster).
    """
    if sys.platform != "win32":
        return True
    try:
        ret = ctypes.windll.user32.MessageBoxW(
            0,
            message,
            title,
            _MB_OKCANCEL | _MB_ICONINFORMATION | _MB_SYSTEMMODAL | _MB_SETFOREGROUND,
        )
        _update_log(f"MessageBox Antwort: {ret}")
        return ret == _IDOK
    except Exception as exc:
        _update_log(f"MessageBox fehlgeschlagen: {exc}")
        return True


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
    """Setup in Updates-Ordner legen (für Installer)."""
    dest = default_setup_download_path()
    setup_path = setup_path.resolve()
    if setup_path != dest.resolve():
        shutil.copy2(setup_path, dest)
    return dest


def _shell_execute(file: str, params: str = "", *, show: int = _SW_SHOW_NORMAL) -> None:
    ret = ctypes.windll.shell32.ShellExecuteW(None, "open", file, params or None, None, show)
    if ret <= 32:
        raise OSError(f"ShellExecute fehlgeschlagen (Code {ret})")


def _launch_installer(setup_path: Path) -> None:
    """Installer sichtbar starten (Inno Setup braucht ein normales Fenster)."""
    setup_path = setup_path.resolve()
    unblock_setup_file(setup_path)
    try:
        _shell_execute(str(setup_path), _INNO_SETUP_ARGS, show=_SW_SHOW_NORMAL)
        _update_log(f"ShellExecute Installer: {setup_path}")
        return
    except OSError as exc:
        _update_log(f"ShellExecute fehlgeschlagen ({exc}) — cmd start")
    flags = _DETACHED_PROCESS | _CREATE_BREAKAWAY_FROM_JOB
    subprocess.Popen(
        ["cmd.exe", "/c", "start", "", str(setup_path), *_INNO_SETUP_ARGS.split()],
        close_fds=True,
        creationflags=flags,
    )
    _update_log(f"cmd start Installer: {setup_path}")


def _launch_installer_after_exit(setup_path: Path) -> None:
    """
    Installer erst nach App-Ende starten (Tray/Hintergrund-EXE sonst blockiert).
    """
    setup_path = setup_path.resolve()
    unblock_setup_file(setup_path)
    write_install_now_helper(setup_path)
    ps1 = setup_path.parent / "_td_run_setup_after_exit.ps1"
    ps1.write_text(
        "Start-Sleep -Seconds 3\n"
        f"Start-Process -LiteralPath '{setup_path}' "
        f"-ArgumentList '{_INNO_SETUP_ARGS}' -WindowStyle Normal\n",
        encoding="utf-8",
    )
    flags = _DETACHED_PROCESS | _CREATE_BREAKAWAY_FROM_JOB
    subprocess.Popen(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-WindowStyle",
            "Hidden",
            "-File",
            str(ps1),
        ],
        close_fds=True,
        creationflags=flags,
        cwd=str(setup_path.parent),
    )
    _update_log(f"Deferred-Installer-PowerShell: {ps1}")


def install_downloaded_setup(setup_path: Path) -> None:
    """Installer starten und Prozess sofort beenden (kein Datei-Lock, kein Zurück zur GUI)."""
    staged = stage_setup_for_install(setup_path)
    unblock_setup_file(staged)
    validate_setup_exe(staged)
    _update_log(f"install_downloaded_setup: {staged}")
    if sys.platform == "win32":
        prepare_shutdown_for_update()
        _launch_installer_after_exit(staged)
        time.sleep(0.8)
        kill_all_app_processes()
    else:
        subprocess.Popen([str(staged)], close_fds=True)
    os._exit(0)
