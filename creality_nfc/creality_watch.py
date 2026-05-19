"""Hintergrund-Wächter: TD Filament Studio starten, wenn Creality Print läuft."""

from __future__ import annotations

import argparse
import ctypes
import subprocess
import sys
import time
from pathlib import Path

# Typische Prozessnamen (Creality Print / Creality Slicer / Handy-App am PC)
CREALITY_PROCESS_NAMES = (
    "CrealityPrint.exe",
    "Creality Print.exe",
    "CrealitySlicer.exe",
    "Creality.exe",
    "crealityprint.exe",
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


def _pid_file() -> Path:
    from app.paths import DATA_DIR

    return DATA_DIR / "creality_watch.pid"


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


def is_creality_running() -> bool:
    blob = _tasklist_blob()
    return _any_image_running(blob, CREALITY_PROCESS_NAMES)


def is_main_app_running() -> bool:
    blob = _tasklist_blob()
    if _any_image_running(blob, OUR_PROCESS_NAMES):
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
        return "main.py" in text and "creality_watch" not in text
    except (OSError, subprocess.SubprocessError):
        return False


def resolve_app_executable() -> Path:
    """EXE der App (gebaut oder Entwicklung)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable)
    root = Path(__file__).resolve().parents[1]
    built = root / "dist" / "TD Filament Studio.exe"
    if built.is_file():
        return built
    return Path(sys.executable)


def launch_main_app() -> bool:
    exe = resolve_app_executable()
    cwd = exe.parent if exe.is_file() else Path.cwd()
    args = [str(exe)]
    if not getattr(sys, "frozen", False) and exe.name.lower().startswith("python"):
        root = Path(__file__).resolve().parents[1]
        args = [str(exe), str(root / "main.py")]
        cwd = root
    flags = 0
    if sys.platform == "win32":
        flags = (
            subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NEW_PROCESS_GROUP
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
    try:
        subprocess.Popen(
            args,
            cwd=str(cwd),
            creationflags=flags,
            close_fds=True,
        )
        return True
    except OSError:
        return False


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
        flags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
        # pythonw für kein Konsolenfenster in Dev
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
                    if launch_main_app():
                        launched_for_session = True
                elif is_main_app_running():
                    launched_for_session = True
            else:
                launched_for_session = False

            time.sleep(POLL_INTERVAL_S)
    finally:
        _clear_pid()


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
