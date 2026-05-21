"""Hintergrund-Wächter: TD Filament Studio starten, wenn Creality Print läuft."""

from __future__ import annotations

import argparse
import ctypes
import subprocess
import sys
import time
from pathlib import Path

# Typische Prozessnamen (Creality Print 5–7, Slicer, Cloud-Client)
CREALITY_PROCESS_NAMES = (
    "CrealityPrint.exe",
    "Creality Print.exe",
    "CrealitySlicer.exe",
    "CrealitySlicerNext.exe",
    "Creality.exe",
    "crealityprint.exe",
    "creality_print.exe",
    "CrealityPrintClient.exe",
    "CrealityCloud.exe",
    "CrealityHelper.exe",
)

OUR_PROCESS_NAMES = (
    "TD Filament Studio.exe",
    "td filament studio.exe",
)

POLL_INTERVAL_S = 3.0
SETTINGS_POLL_S = 5.0


def _pid_alive(pid: int) -> bool:
    if pid <= 0 or sys.platform != "win32":
        return False
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if handle:
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    return False


def _data_dir() -> Path:
    from app.paths import DATA_DIR

    return DATA_DIR


def _pid_file() -> Path:
    return _data_dir() / "creality_watch.pid"


def _main_app_pid_file() -> Path:
    return _data_dir() / "main_app.pid"


def register_main_app() -> None:
    """GUI-Prozess markieren (Wächter darf sich nicht als Haupt-App zählen)."""
    path = _main_app_pid_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(os_getpid()), encoding="utf-8")


def unregister_main_app() -> None:
    try:
        _main_app_pid_file().unlink(missing_ok=True)
    except OSError:
        pass


def _main_app_pid_alive() -> bool:
    path = _main_app_pid_file()
    if not path.is_file():
        return False
    try:
        pid = int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return False
    return _pid_alive(pid)


def watcher_is_running() -> bool:
    path = _pid_file()
    if not path.is_file():
        return False
    try:
        pid = int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return False
    return _pid_alive(pid)


def _write_pid() -> None:
    path = _pid_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(os_getpid()), encoding="utf-8")


def os_getpid() -> int:
    import os

    return os.getpid()


def _clear_pid() -> None:
    try:
        _pid_file().unlink(missing_ok=True)
    except OSError:
        pass


def _tasklist_blob() -> str:
    if sys.platform != "win32":
        return ""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        proc = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=20,
            creationflags=flags,
        )
        return (proc.stdout or "").lower()
    except (OSError, subprocess.SubprocessError):
        return ""


def _any_image_running(blob: str, names: tuple[str, ...]) -> bool:
    if not blob:
        return False
    for name in names:
        if name.lower() in blob:
            return True
    return False


def _watch_log(message: str) -> None:
    try:
        path = _data_dir() / "creality_watch.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with path.open("a", encoding="utf-8") as fh:
            fh.write(f"[{stamp}] {message}\n")
    except OSError:
        pass


def _powershell_bool(command: str) -> bool | None:
    """True/False per PowerShell; None = Aufruf fehlgeschlagen."""
    if sys.platform != "win32":
        return None
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            capture_output=True,
            text=True,
            timeout=25,
            creationflags=flags,
        )
        return (proc.stdout or "").strip().lower() == "true"
    except (OSError, subprocess.SubprocessError):
        return None


def _win_creality_running_powershell() -> bool | None:
    """Alle Prozesse mit „creality“ im Namen (ohne TD Filament Studio)."""
    script = (
        "$p = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { "
        "$n = $_.Name; $n -match '(?i)creality' -and $n -notmatch '(?i)filament' }; "
        "if ($p) { 'true' } else { 'false' }"
    )
    return _powershell_bool(script)


def is_creality_running() -> bool:
    ps = _win_creality_running_powershell()
    if ps is not None:
        return ps
    blob = _tasklist_blob()
    if _any_image_running(blob, CREALITY_PROCESS_NAMES):
        return True
    # Fallback: „creality“ irgendwo in der Prozessliste (fremde EXE-Namen)
    low = blob
    if "creality" in low and "filament studio" not in low:
        return True
    return False


def _win_td_studio_gui_running() -> bool:
    """TD Filament Studio.exe ohne --watch-creality (Wächter zählt nicht)."""
    if sys.platform != "win32":
        return False
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        proc = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                (
                    "$p = Get-CimInstance Win32_Process -Filter "
                    "\"name='TD Filament Studio.exe'\" -ErrorAction SilentlyContinue; "
                    "($p | Where-Object { $_.CommandLine -notmatch '--watch-creality' }).Count -gt 0"
                ),
            ],
            capture_output=True,
            text=True,
            timeout=20,
            creationflags=flags,
        )
        return (proc.stdout or "").strip().lower() == "true"
    except (OSError, subprocess.SubprocessError):
        return False


def is_main_app_running() -> bool:
    if _main_app_pid_alive():
        return True
    if sys.platform == "win32" and getattr(sys, "frozen", False):
        return _win_td_studio_gui_running()
    blob = _tasklist_blob()
    if _any_image_running(blob, OUR_PROCESS_NAMES):
        # Nur Wächter läuft → kein GUI (gleicher EXE-Name)
        if getattr(sys, "frozen", False):
            return _win_td_studio_gui_running()
        return True
    if sys.platform != "win32":
        return False
    # Entwicklung: python/pythonw mit main.py / creality_watch ohne --watch nur main
    low = blob
    if "python.exe" not in low and "pythonw.exe" not in low:
        return False
    try:
        proc = subprocess.run(
            [
                "wmic",
                "process",
                "where",
                "name='python.exe' or name='pythonw.exe'",
                "get",
                "processid,commandline",
                "/format:list",
            ],
            capture_output=True,
            text=True,
            timeout=25,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        text = (proc.stdout or "").lower()
        return "main.py" in text and "creality_watch" not in text and "--watch-creality" not in text
    except (OSError, subprocess.SubprocessError):
        return False


def resolve_app_executable() -> Path:
    """EXE der App (gebaut oder Entwicklung)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable)
    root = Path(__file__).resolve().parents[1]
    built = root / "dist" / "TD Filament Studio" / "TD Filament Studio.exe"
    if not built.is_file():
        built = root / "dist" / "TD Filament Studio.exe"
    if built.is_file():
        return built
    return Path(sys.executable)


def launch_main_app() -> bool:
    exe = resolve_app_executable()
    if not exe.is_file():
        _watch_log(f"launch_main_app: EXE fehlt ({exe})")
        return False
    if sys.platform == "win32":
        try:
            import os

            os.startfile(str(exe))  # noqa: S606 — GUI sichtbar starten
            _watch_log(f"launch_main_app: startfile OK ({exe})")
            return True
        except OSError as exc:
            _watch_log(f"launch_main_app: startfile fehlgeschlagen ({exc})")
    cwd = exe.parent
    args = [str(exe)]
    if not getattr(sys, "frozen", False) and exe.name.lower().startswith("python"):
        root = Path(__file__).resolve().parents[1]
        args = [str(exe), str(root / "main.py")]
        cwd = root
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    try:
        subprocess.Popen(args, cwd=str(cwd), creationflags=flags, close_fds=True)
        _watch_log(f"launch_main_app: Popen OK ({exe})")
        return True
    except OSError as exc:
        _watch_log(f"launch_main_app: Popen fehlgeschlagen ({exc})")
        return False


_AUTOSTART_VALUE_NAME = "TDFilamentStudioCrealityWatch"


def _autostart_run_key() -> str:
    return r"Software\Microsoft\Windows\CurrentVersion\Run"


def sync_watcher_autostart(enabled: bool) -> None:
    """Windows-Anmeldung: Wächter starten, wenn Einstellung aktiv (ohne vorher TD zu öffnen)."""
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return
    import winreg

    exe = resolve_app_executable()
    cmd = f'"{exe}" --watch-creality'
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            _autostart_run_key(),
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            if enabled:
                winreg.SetValueEx(key, _AUTOSTART_VALUE_NAME, 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(key, _AUTOSTART_VALUE_NAME)
                except FileNotFoundError:
                    pass
    except OSError:
        pass


def stop_watcher() -> None:
    path = _pid_file()
    if not path.is_file():
        return
    try:
        pid = int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        _clear_pid()
        return
    if _pid_alive(pid):
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                capture_output=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        else:
            import os
            import signal

            os.kill(pid, signal.SIGTERM)
    _clear_pid()


def sync_creality_watch(enabled: bool) -> tuple[bool, str]:
    """
    Einstellung „Mit Creality Print starten“ anwenden.
    Returns (watcher_started_or_already, status_message).
    """
    sync_watcher_autostart(enabled)
    if not enabled:
        stop_watcher()
        return False, "Creality-Wächter beendet"
    if watcher_is_running():
        return False, "Creality-Wächter läuft bereits"
    if start_watcher_detached():
        return True, "Creality-Wächter gestartet"
    return False, "Creality-Wächter konnte nicht gestartet werden"


def start_watcher_detached() -> bool:
    """Wächter-Prozess starten (einmalig)."""
    if watcher_is_running():
        return False
    exe = Path(sys.executable)
    args = [str(exe)]
    if getattr(sys, "frozen", False):
        args.append("--watch-creality")
    else:
        root = Path(__file__).resolve().parents[1]
        args = [str(exe), str(root / "main.py"), "--watch-creality"]
    flags = subprocess.DETACHED_PROCESS | getattr(subprocess, "CREATE_NEW_WINDOW", 0)
    if sys.platform == "win32":
        flags |= getattr(subprocess, "CREATE_NO_WINDOW", 0) | 0x01000000  # CREATE_BREAKAWAY_FROM_JOB
        if exe.name.lower() == "python.exe":
            pyw = exe.with_name("pythonw.exe")
            if pyw.is_file():
                exe = pyw
                args[0] = str(exe)
    try:
        subprocess.Popen(args, creationflags=flags, close_fds=True)
        return True
    except OSError:
        return False


def run_watch_loop() -> int:
    from creality_nfc.app_settings import DEFAULT_SETTINGS_PATH, AppSettings

    _write_pid()
    launched_for_session = False
    last_settings_check = 0.0
    enabled = False

    try:
        while True:
            now = time.monotonic()
            if now - last_settings_check >= SETTINGS_POLL_S:
                last_settings_check = now
                enabled = AppSettings.load(DEFAULT_SETTINGS_PATH).launch_with_creality_print
            if not enabled:
                launched_for_session = False
                time.sleep(POLL_INTERVAL_S)
                continue

            creality_up = is_creality_running()
            if creality_up:
                if not launched_for_session and not is_main_app_running():
                    _watch_log("Creality erkannt — starte TD Filament Studio …")
                    if launch_main_app():
                        launched_for_session = True
                    else:
                        _watch_log("Start von TD Filament Studio fehlgeschlagen")
                elif is_main_app_running():
                    launched_for_session = True
            else:
                if launched_for_session:
                    _watch_log("Creality beendet — Warte auf naechsten Start")
                launched_for_session = False

            time.sleep(POLL_INTERVAL_S)
    finally:
        _clear_pid()
        if getattr(sys, "frozen", False):
            import os

            os._exit(0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Creality-Print-Wächter für TD Filament Studio")
    parser.add_argument(
        "--watch-creality",
        action="store_true",
        help="Hintergrund-Schleife (wird von der App gestartet)",
    )
    args = parser.parse_args(argv)
    if args.watch_creality:
        from app.constants import ensure_data_dir

        ensure_data_dir()
        return run_watch_loop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
