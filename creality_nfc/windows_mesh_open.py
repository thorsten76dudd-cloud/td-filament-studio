"""STL/3MF in Windows-3D-Viewer öffnen (ohne PowerShell-/App-Flackern)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_SW_SHOW = 1

_VIEWER_EXE_NAMES = ("3DViewer.exe", "PaintStudio.View.exe")


def _find_viewer_exe() -> Path | None:
    roots: list[Path] = []
    local = os.environ.get("LOCALAPPDATA")
    if local:
        roots.append(Path(local) / "Microsoft" / "WindowsApps")
    pf = os.environ.get("ProgramFiles")
    if pf:
        roots.append(Path(pf) / "WindowsApps")
    for root in roots:
        if not root.is_dir():
            continue
        for name in _VIEWER_EXE_NAMES:
            direct = root / name
            if direct.is_file() and direct.stat().st_size > 0:
                return direct
            try:
                for exe in root.glob(f"**/{name}"):
                    if exe.is_file() and exe.stat().st_size > 0:
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
    try:
        subprocess.Popen(
            ["rundll32.exe", "shell32.dll,OpenAs_RunDLL", str(path.resolve())],
            close_fds=True,
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
        return False, str(exc)


def open_mesh_in_system_viewer(path: Path) -> tuple[bool, str]:
    """Windows 3D Viewer oder „Öffnen mit“-Dialog — kein kurzes Blau-Flackern."""
    path = path.resolve()
    if not path.is_file():
        return False, "Datei nicht gefunden."

    if sys.platform != "win32":
        try:
            subprocess.Popen(["xdg-open", str(path)], close_fds=True)
            return True, ""
        except OSError as exc:
            return False, str(exc)

    viewer = _find_viewer_exe()
    if viewer is not None and _launch_viewer(viewer, path):
        return True, ""

    if _rundll_openas(path) or _shell_openas(path):
        return (
            True,
            "„Öffnen mit“ — bitte „3D Viewer“ oder „Paint 3D“ wählen.",
        )

    return False, (
        "Kein 3D-Viewer gefunden.\n"
        "Microsoft Store: „3D Viewer“ installieren,\n"
        "danach erneut „3D-Viewer wählen…“."
    )
