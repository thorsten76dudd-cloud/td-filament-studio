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


def write_install_now_helper(setup_path: Path | None = None) -> Path:
    """BAT im festen Updates-Ordner (nicht %TEMP%)."""
    staged = stage_setup_for_install(setup_path or default_setup_download_path())
    folder = updates_folder()
    bat = folder / "Setup-jetzt-installieren.bat"
    bat.write_text(
        "@echo off\r\n"
        f'cd /d "{folder}"\r\n'
        f'start "" "{staged}" {_INNO_SETUP_ARGS}\r\n',
        encoding="utf-8",
    )
    _update_log(f"Helper-BAT: {bat} -> {staged}")
    return bat


def notify_install_starting(setup_path: Path, helper: Path) -> None:
    """Sichtbarer Systemdialog unmittelbar vor Installer-Start."""
    if sys.platform != "win32":
        return
    body = (
        f"Setup wird jetzt gestartet.\n\n{setup_path}\n\n"
        f"Die App schließt sich gleich.\n\n"
        f"Falls kein Installer erscheint:\n{helper}"
    )
    try:
        ctypes.windll.user32.MessageBoxW(
            0,
            body,
            "TD Filament Studio — Update",
            _MB_ICONINFORMATION | _MB_SYSTEMMODAL | _MB_SETFOREGROUND | 0x00000000,
        )
        _update_log("notify_install_starting: OK")
    except Exception as exc:
        _update_log(f"notify_install_starting: {exc}")


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
    """Setup immer nach %LOCALAPPDATA%\\TD Filament Studio\\Updates kopieren."""
    dest = default_setup_download_path()
    setup_path = setup_path.resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if setup_path != dest.resolve():
        shutil.copy2(setup_path, dest)
        _update_log(f"staged: {setup_path} -> {dest}")
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


def _write_persistent_runner(setup_path: Path) -> Path:
    """Verzögerter Start aus festem Updates-Ordner (überlebt App-Ende)."""
    folder = updates_folder()
    setup_path = setup_path.resolve()
    runner = folder / "_td_install_after_exit.cmd"
    runner.write_text(
        "@echo off\r\n"
        f'cd /d "{folder}"\r\n'
        "ping 127.0.0.1 -n 11 >nul\r\n"
        f'start "" "{setup_path}" {_INNO_SETUP_ARGS}\r\n',
        encoding="utf-8",
    )
    _update_log(f"Runner-CMD: {runner}")
    return runner


def _popen_installer_detached(setup_path: Path) -> None:
    """Setup.exe als eigener Prozess (nicht Job der App)."""
    setup_path = setup_path.resolve()
    flags = _DETACHED_PROCESS | _CREATE_BREAKAWAY_FROM_JOB
    npg = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(
        [str(setup_path), *_INNO_SETUP_ARGS.split()],
        cwd=str(setup_path.parent),
        close_fds=True,
        creationflags=flags | npg,
    )
    _update_log(f"Popen Installer: {setup_path}")


def _schedule_install_via_schtasks(setup_path: Path) -> None:
    """Windows-Aufgabe — unabhängig vom App-Prozessbaum."""
    setup_path = setup_path.resolve()
    task = "TDFilamentStudioInAppUpdate"
    tr = f'"{setup_path}" {_INNO_SETUP_ARGS}'
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.run(
        ["schtasks", "/Delete", "/TN", task, "/F"],
        capture_output=True,
        creationflags=flags,
    )
    create = subprocess.run(
        ["schtasks", "/Create", "/TN", task, "/TR", tr, "/SC", "ONCE", "/ST", "00:01", "/F"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=flags,
    )
    _update_log(f"schtasks create rc={create.returncode}: {create.stderr or create.stdout}")
    run = subprocess.run(
        ["schtasks", "/Run", "/TN", task],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=flags,
    )
    _update_log(f"schtasks run rc={run.returncode}: {run.stderr or run.stdout}")
    subprocess.run(
        ["schtasks", "/Delete", "/TN", task, "/F"],
        capture_output=True,
        creationflags=flags,
    )


def _launch_installer_after_exit(setup_path: Path) -> None:
    """Verzögerter CMD-Start aus Updates-Ordner."""
    setup_path = setup_path.resolve()
    runner = _write_persistent_runner(setup_path)
    try:
        _shell_execute(str(runner), "", show=_SW_SHOW_NORMAL)
        _update_log(f"ShellExecute Runner: {runner}")
    except OSError as exc:
        _update_log(f"ShellExecute Runner fehlgeschlagen: {exc}")
        flags = _DETACHED_PROCESS | _CREATE_BREAKAWAY_FROM_JOB
        npg = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        subprocess.Popen(
            [str(runner)],
            cwd=str(runner.parent),
            close_fds=True,
            creationflags=flags | npg,
        )
        _update_log(f"Popen Runner: {runner}")


def install_downloaded_setup(setup_path: Path) -> None:
    """Installer starten und Prozess beenden (Inno /FORCECLOSEAPPLICATIONS schließt die App)."""
    staged = stage_setup_for_install(setup_path)
    unblock_setup_file(staged)
    validate_setup_exe(staged)
    write_install_now_helper(staged)
    size = staged.stat().st_size
    _update_log(f"install_downloaded_setup: {staged} ({size} bytes)")
    if sys.platform == "win32":
        prepare_shutdown_for_update()
        _popen_installer_detached(staged)
        try:
            _launch_installer(staged)
        except OSError as exc:
            _update_log(f"ShellExecute Installer: {exc}")
        _launch_installer_after_exit(staged)
        try:
            _schedule_install_via_schtasks(staged)
        except (OSError, subprocess.SubprocessError) as exc:
            _update_log(f"schtasks: {exc}")
        time.sleep(0.8)
    else:
        subprocess.Popen([str(staged)], close_fds=True)
    os._exit(0)
