"""STL/3MF in Windows-3D-Viewer öffnen."""

from __future__ import annotations

import glob
import os
import subprocess
import sys
from pathlib import Path

_SW_SHOW = 1
_STORE_3D_VIEWER = "ms-windows-store://pdp/?productid=9NBLGGH4THNS"

_VIEWER_EXE_NAMES = ("3DViewer.exe", "PaintStudio.View.exe")
_VIEWER_PACKAGE_GLOBS = (
    r"%ProgramFiles%\WindowsApps\Microsoft.Microsoft3DViewer*\3DViewer.exe",
    r"%ProgramFiles%\WindowsApps\Microsoft.MSPaint*\PaintStudio.View.exe",
)


def _find_viewer_exe() -> Path | None:
    for pattern in _VIEWER_PACKAGE_GLOBS:
        for match in glob.glob(os.path.expandvars(pattern)):
            p = Path(match)
            if p.is_file() and p.stat().st_size > 1024:
                return p
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
    resolved = str(path.resolve())
    if _shell_execute("open", str(exe), f'"{resolved}"'):
        return True
    try:
        subprocess.Popen([str(exe), resolved], close_fds=True)
        return True
    except OSError:
        return False


def _shell_invoke_openas(path: Path) -> bool:
    """Explorer „Öffnen mit“ — zeigt Apps zuverlässiger als rundll32 allein."""
    resolved = str(path.resolve()).replace("'", "''")
    ps = (
        f"$p = '{resolved}'\n"
        "$sh = New-Object -ComObject Shell.Application\n"
        "$dir = Split-Path -LiteralPath $p\n"
        "$leaf = Split-Path -LiteralPath $p -Leaf\n"
        "$item = $sh.Namespace($dir).ParseName($leaf)\n"
        "if ($item) { $item.InvokeVerb('openas'); 'ok' } else { 'fail' }\n"
    )
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Sta", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=45,
            creationflags=flags,
        )
        return (proc.stdout or "").strip().lower() == "ok"
    except (OSError, subprocess.SubprocessError):
        return False


def _shopenwith_dialog(path: Path) -> bool:
    """Windows-Dialog „Öffnen mit“ (Vista+)."""
    try:
        import ctypes
        from ctypes import Structure, byref, c_void_p, wintypes

        class OPENASINFO(Structure):
            _fields_ = [
                ("pcszFile", wintypes.LPCWSTR),
                ("poi", c_void_p),
                ("oewo", wintypes.DWORD),
            ]

        OAIF_EXEC = 0x0004
        OAIF_ALLOW_REGISTRATION = 0x0001

        info = OPENASINFO()
        info.pcszFile = str(path.resolve())
        info.poi = None
        info.oewo = OAIF_EXEC | OAIF_ALLOW_REGISTRATION
        hr = ctypes.windll.shell32.SHOpenWithDialog(None, byref(info))
        return hr == 0
    except Exception:
        return False


def _rundll_openas(path: Path) -> bool:
    resolved = str(path.resolve())
    try:
        subprocess.Popen(
            ["rundll32.exe", f"shell32.dll,OpenAs_RunDLL {resolved}"],
            close_fds=True,
        )
        return True
    except OSError:
        return False


def open_microsoft_store_3d_viewer() -> bool:
    return _shell_execute("open", _STORE_3D_VIEWER)


def open_mesh_with_default_app(path: Path) -> tuple[bool, str]:
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


def open_mesh_choose_viewer(path: Path) -> tuple[bool, str, str]:
    """
    Returns (ok, message, mode).
    mode: direct | openas | store | error
    """
    path = path.resolve()
    if not path.is_file():
        return False, "Datei nicht gefunden.", "error"

    if sys.platform != "win32":
        try:
            subprocess.Popen(["xdg-open", str(path)], close_fds=True)
            return True, "", "direct"
        except OSError as exc:
            return False, str(exc), "error"

    viewer = _find_viewer_exe()
    if viewer is not None and _launch_viewer(viewer, path):
        return True, f"3D Viewer gestartet ({viewer.name}).", "direct"

    if _shell_invoke_openas(path):
        return (
            True,
            "Menü „Öffnen mit“ — App wählen (z. B. 3D Viewer, Paint 3D, Creality Print).",
            "openas",
        )

    if _shopenwith_dialog(path):
        return (
            True,
            "Dialog „Öffnen mit“ — App auswählen und bestätigen.",
            "openas",
        )

    if _rundll_openas(path):
        return True, "„Öffnen mit“ (klassisch) — App wählen.", "openas"

    if _shell_execute("openas", str(path)):
        return True, "„Öffnen mit“ — App wählen.", "openas"

    return (
        False,
        "Kein 3D Viewer installiert und „Öffnen mit“ konnte nicht geöffnet werden.\n\n"
        "„3D Viewer“ aus dem Microsoft Store installieren oder „In Creality öffnen“ nutzen.",
        "store",
    )


def open_mesh_in_system_viewer(path: Path) -> tuple[bool, str]:
    ok, msg, _mode = open_mesh_choose_viewer(path)
    return ok, msg
