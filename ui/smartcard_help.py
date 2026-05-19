"""Hilfe-Dialog wenn der Windows-Smartcard-Dienst hängt."""

from __future__ import annotations

import os
import sys
import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, ttk

from creality_nfc.smartcard_service import probe_pcsc, restart_scard_elevated, start_scard_elevated
from ui.dialog_theme import prepare_toplevel
from ui.theme import F_BODY, F_SMALL, apply_text_area_style


def open_services_msc() -> None:
    if sys.platform == "win32":
        os.startfile("services.msc")  # type: ignore[attr-defined]


HELP_TEXT = """Der Windows-Dienst „Smartcard“ (SCardSvr) antwortet nicht.
Das hat meist nichts mit dem RFID-Leser zu tun — der kann noch fehlen.

So behebst du es (eine Option reicht oft):

1. Win+R → services.msc → Enter
   → „Smartcard“ suchen → Rechtsklick → Neu starten
   (Windows fragt ggf. nach Admin)

2. PC einmal neu starten, danach SpoolTag erneut öffnen

3. PowerShell als Administrator:
   net stop SCardSvr
   net start SCardSvr

Ohne funktionierenden Dienst geht nur Tag lesen/schreiben nicht.
Material-DB, Filamente und „Meine Spulen“ funktionieren trotzdem.

Wenn der ACR122U erst später kommt: Dienst jetzt reparieren,
Reader danach per USB — Status wird gelb („Reader verbinden“)."""


class SmartcardHelpDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, on_retry: Callable[[], None] | None = None) -> None:
        super().__init__(parent)
        self.title("Smartcard — Hilfe")
        self.minsize(480, 400)

        state = probe_pcsc()
        labels = {
            "ok": "Bereit",
            "no_reader": "Dienst OK — Reader fehlt noch",
            "service_down": "Dienst gestoppt",
            "service_stuck": "Dienst hängt",
            "error": "Unbekannter Fehler",
        }
        ttk.Label(
            self,
            text=f"Aktueller Status: {labels.get(state, state)}",
            font=F_BODY,
        ).pack(anchor="w", padx=16, pady=(16, 8))

        box = tk.Text(self, wrap="word", height=14, font=F_SMALL, padx=8, pady=8)
        apply_text_area_style(box)
        box.pack(fill="both", expand=True, padx=16, pady=8)
        box.insert("1.0", HELP_TEXT)
        box.config(state="disabled")

        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=16, pady=12)
        ttk.Button(btns, text="Schließen", command=self.destroy).pack(side="right")
        ttk.Button(btns, text="Dienste öffnen (services.msc)", command=open_services_msc).pack(
            side="right", padx=8
        )
        ttk.Button(
            btns,
            text="Smartcard neu starten (UAC)",
            command=lambda: self._retry(on_retry),
            style="Accent.TButton",
        ).pack(side="left")

        prepare_toplevel(self, parent, width=520, height=440)

    def _retry(self, on_retry: Callable[[], None] | None) -> None:
        state = probe_pcsc()
        if state == "service_stuck":
            ok = restart_scard_elevated()
        else:
            ok = start_scard_elevated()
        if not ok:
            messagebox.showerror("Smartcard", "UAC abgebrochen oder fehlgeschlagen.", parent=self)
            return
        messagebox.showinfo(
            "Smartcard",
            "Befehl gesendet.\n\n5 Sekunden warten, dann dieses Fenster schließen\n"
            "und unten prüfen ob der Status grün oder gelb wird.",
            parent=self,
        )
        if on_retry:
            self.after(5000, on_retry)
