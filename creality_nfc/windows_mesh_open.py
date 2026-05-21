"""STL/3MF in Windows-3D-Viewer öffnen (ohne PowerShell-/App-Flackern)."""

from __future__ import annotations

import glob
import os
import subprocess
import sys
from pathlib import Path

_SW_SHOW = 1

_VIEWER_EXE_NAMES = ("3DViewer.exe", "PaintStudio.View.exe")
_VIEWER_PACKAGE_GLOBS = (
    r"%ProgramFiles%\WindowsApps\Microsoft.Microsoft3DViewer*\3DViewer.exe",
    r"%ProgramFiles%\WindowsApps\Microsoft.MSPaint*\PaintStudio.View.exe",
)


def _find_viewer_exe() -> Path | None:
    roots: list[Path] = []
    local = os.environ.get("LOCALAPPDATA")
    if local:
        roots.append(Path(local) / "Microsoft" / "WindowsApps")
    pf = os.environ.get("ProgramFiles")
    if pf:
        roots.append(Path(pf) / "WindowsApps")
    for pattern in _VIEWER_PACKAGE_GLOBS:
        expanded = os.path.expandvars(pattern)
        for match in glob.glob(expanded):
            p = Path(match)
            if p.is_file() and p.stat().st_size > 1024:
                return p
    for root in roots:
        if not root.is_dir():
            continue
        for name in _VIEWER_EXE_NAMES:
            direct = root / name
            if direct.is_file() and direct.stat().st_size > 1024:
                return direct
            try:
                for exe in root.glob(f"**/{name}"):
                    if exe.is_file() and exe.stat().st_size > 1024:
                        return exe
            except OSError:
                continue
    return None


def _shell_execute(operation: str, file: str, parameters: str | None = None) -> bool:
    try:
        import ctypes

        rc = ctypes.windll.shell32.ShellExecuteW(  # type: ignore[attr-defined]
            None,
            operation,
            file,
            parameters,
            None,
            _SW_SHOW,
        )
        return rc > 32
    except Exception:
        return False


def _launch_viewer(exe: Path, path: Path) -> bool:
    """Viewer als normale GUI-App starten (kein CREATE_NO_WINDOW — sonst Blitz & Schließen)."""
    resolved = str(path.resolve())
    if _shell_execute("open", str(exe), f'"{resolved}"'):
        return True
    try:
        subprocess.Popen([str(exe), resolved], close_fds=True)
        return True
    except OSError:
        return False


def _rundll_openas(path: Path) -> bool:
    """Klassischer „Öffnen mit“-Dialog — bleibt offen, kein kurzes Aufblitzen."""
    resolved = str(path.resolve())
    try:
        subprocess.Popen(
            ["rundll32.exe", f"shell32.dll,OpenAs_RunDLL {resolved}"],
            close_fds=True,
        )
        return True
    except OSError:
        pass
    try:
        subprocess.Popen(
            ["rundll32.exe", "shell32.dll,OpenAs_RunDLL", resolved],
            close_fds=True,
        )
        return True
    except OSError:
        return False


def _cmd_start(path: Path) -> bool:
    """Windows start-Befehl (Standard-App für STL/3MF)."""
    resolved = str(path.resolve())
    try:
        subprocess.Popen(
            ["cmd.exe", "/c", "start", "", resolved],
            close_fds=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return True
    except OSError:
        return False


def _shell_openas(path: Path) -> bool:
    return _shell_execute("openas", str(path.resolve()))


def open_mesh_with_default_app(path: Path) -> tuple[bool, str]:
    """Creality / Windows-Standard-App."""
    path = path.resolve()
    if not path.is_file():
        return False, "Datei nicht gefunden."
    try:
        if sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(path)], close_fds=True)
        return True, ""
    except OSError as exc:
        if sys.platform == "win32" and _cmd_start(path):
            return True, ""
        return False, str(exc)


def open_mesh_choose_viewer(path: Path) -> tuple[bool, str]:
    """
    „3D-Viewer wählen“: zuerst „Öffnen mit“-Dialog (Nutzer wählt App),
    danach direkter 3D-Viewer / Paint 3D.
    """
    path = path.resolve()
    if not path.is_file():
        return False, "Datei nicht gefunden."

    if sys.platform != "win32":
        try:
            subprocess.Popen(["xdg-open", str(path)], close_fds=True)
            return True, ""
        except OSError as exc:
            return False, str(exc)

    if _rundll_openas(path):
        return (
            True,
            "Dialog „Öffnen mit“ wurde geöffnet.\n"
            "Bitte „3D Viewer“ oder „Paint 3D“ wählen (ggf. unter „Weitere Apps“).",
        )

    viewer = _find_viewer_exe()
    if viewer is not None and _launch_viewer(viewer, path):
        return True, f"Gestartet mit {viewer.name}."

    if _shell_openas(path):
        return True, "„Öffnen mit“ — App im Dialog wählen."

    if _cmd_start(path):
        return True, "Mit der Windows-Standard-App für STL/3MF geöffnet."

    return False, (
        "Kein 3D-Viewer gefunden.\n"
        "Microsoft Store: „3D Viewer“ installieren,\n"
        "danach erneut „3D-Viewer wählen…“."
    )


def open_mesh_in_system_viewer(path: Path) -> tuple[bool, str]:
    """Windows 3D Viewer oder „Öffnen mit“-Dialog — kein kurzes Blau-Flackern."""
    return open_mesh_choose_viewer(path)
