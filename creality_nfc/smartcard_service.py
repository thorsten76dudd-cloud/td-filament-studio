"""Windows Smartcard-Dienst (SCardSvr) — Status & gestartet per UAC (ein Klick)."""

from __future__ import annotations

import ctypes
import subprocess
import sys


def scard_status() -> str:
    """running | stopped | missing | unknown"""
    if sys.platform != "win32":
        return "unknown"
    try:
        r = subprocess.run(
            ["sc", "query", "SCardSvr"],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        out = (r.stdout or "") + (r.stderr or "")
        if r.returncode != 0 and "1060" in out:
            return "missing"
        if "RUNNING" in out:
            return "running"
        if "STOPPED" in out:
            return "stopped"
    except Exception:
        pass
    return "unknown"


def scard_status_message(state: str | None = None) -> str:
    state = state or probe_pcsc()
    if state == "service_stuck":
        return (
            "Windows meldet „Dienst läuft“, aber NFC antwortet nicht.\n"
            "„Smartcard neu starten“ (UAC) — oder PC neu starten."
        )
    if state == "no_reader":
        return "Smartcard-Dienst OK. Bitte ACR122U per USB anschließen."
    s = scard_status()
    if s == "running" and state == "ok":
        return "Smartcard-Dienst läuft."
    if s == "stopped":
        return (
            "Smartcard-Dienst (SCardSvr) ist gestoppt.\n"
            "Einmal „Dienst starten“ — Windows fragt kurz nach Admin (UAC).\n"
            "Danach funktioniert die .exe normal ohne Admin."
        )
    if s == "missing":
        return "Smartcard-Dienst nicht installiert (ungewöhnlich auf Windows 10/11)."
    return "Smartcard-Dienst-Status unbekannt."


def probe_pcsc() -> str:
    """
    Echter NFC/PC/SC-Status (nicht nur Windows-Dienst).
    ok | no_reader | service_down | service_stuck | error
    """
    if scard_status() != "running":
        return "service_down"
    try:
        from smartcard.System import readers

        if not readers():
            return "no_reader"
        return "ok"
    except Exception as exc:
        msg = str(exc)
        if "8010001D" in msg or "Ressourcen-Manager" in msg or "Resource Manager" in msg:
            return "service_stuck"
        return "error"


def restart_scard_elevated() -> bool:
    """Stoppt und startet SCardSvr neu (UAC)."""
    if sys.platform != "win32":
        return False
    params = "/c net stop SCardSvr & timeout /t 2 /nobreak >nul & net start SCardSvr"
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", "cmd.exe", params, None, 0)
    return int(rc) > 32


def start_scard_elevated() -> bool:
    """
    Startet SCardSvr mit UAC-Elevation (ein Bestätigungsdialog).
    Gibt True zurück, wenn der Elevate-Aufruf gestartet wurde (nicht ob Dienst läuft).
    """
    if sys.platform != "win32":
        return False
    # net start ist zuverlässiger als PowerShell-Start-Service unter runas
    params = '/c net start SCardSvr'
    rc = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        "cmd.exe",
        params,
        None,
        0,  # SW_HIDE — nur UAC-Dialog sichtbar
    )
    # ShellExecute > 32 = Erfolg beim Starten des Prozesses
    return int(rc) > 32
