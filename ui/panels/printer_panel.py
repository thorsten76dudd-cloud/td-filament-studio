"""Drucker-Dashboard im Tab Material-Datenbank: DB, Options, SSH."""

from __future__ import annotations

import json
import threading
import tkinter as tk
from datetime import datetime
from tkinter import scrolledtext, ttk
from typing import TYPE_CHECKING

from creality_nfc.db_compare import compare_databases, format_compare_report
from creality_nfc.material_options import build_material_options
from creality_nfc.printer_camera import printer_reachable
from creality_nfc.printer_ssh import (
    download_database_from_printer,
    download_options_from_printer,
    fetch_printer_info,
    normalize_host,
)
from ui.dialog_theme import theme_dialog
from ui.rounded_widgets import rounded_button
from ui.theme import BG, BG_SUBTLE, apply_text_area_style
from ui.tooltip import tip
from ui.messaging import confirm, notify

if TYPE_CHECKING:
    from app.main_window import TDFilamentStudioApp


class PrinterDashboardPanel(ttk.LabelFrame):
    """Material-Sync & Options — Live-Steuerung im Tab „Drucker“."""

    def __init__(self, parent: tk.Misc, app: TDFilamentStudioApp) -> None:
        super().__init__(parent, text="  Drucker-Dashboard (Material)  ")
        theme_dialog(self)
        self.app = app
        self._last_remote_db: dict | None = None
        self._busy = False

        top = ttk.Frame(self)
        top.pack(fill="x", padx=8, pady=8)

        self.status_var = tk.StringVar(value="IP eintragen → „Status prüfen“")
        ttk.Label(top, textvariable=self.status_var, wraplength=720, style="Muted.TLabel").pack(
            anchor="w", pady=(0, 4)
        )
        ttk.Label(
            top,
            text="LED, Pause, Temperaturen, G-Code → Tab „Drucker“",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(0, 8))

        btns = tk.Frame(top, bg=BG)
        btns.pack(fill="x", pady=(0, 4))
        def _open_print_check() -> None:
            panel = getattr(self.app, "_device_panel", None) or getattr(
                self.app, "_printer_device_panel", None
            )
            if panel is None:
                return
            self.app.notebook.select(self.app.tab_printer)
            panel.show_print_check()

        for text, cmd, help_txt in (
            ("Status prüfen", self.check_status, "Erreichbarkeit des Druckers und SSH prüfen."),
            (
                "Druck-Check",
                _open_print_check,
                "Markierte/zuletzt gewählte G-Code-Datei oder laufender Druck vs. CFS/Spulen (Tab Drucker).",
            ),
            (
                "DB vergleichen",
                self.compare_db,
                "Lokale und Drucker-Datenbank vergleichen (Unterschiede anzeigen).",
            ),
            ("Options vom Drucker", self.pull_options, "Material-Options-Datei vom Drucker laden (nur Lesen)."),
        ):
            tip(
                rounded_button(btns, text, cmd, variant="secondary", compact=True),
                help_txt,
            ).pack(side="left", padx=(0, 8), pady=4)
        tip(
            rounded_button(
                btns,
                "→ Tab Drucker",
                lambda: self.app.notebook.select(self.app.tab_printer),
                variant="secondary",
                compact=True,
            ),
            "Zum Tab Drucker wechseln (Live-Steuerung, G-Code, CFS).",
        ).pack(side="left", padx=(8, 0), pady=4)

        self.compare_text = scrolledtext.ScrolledText(
            self, height=3, font=("Consolas", 9), wrap="word"
        )
        apply_text_area_style(self.compare_text, bg=BG_SUBTLE)
        self.compare_text.pack(fill="x", padx=8, pady=(0, 8))
        self._log("Bereit. Live-Steuerung: Tab „Drucker“.")

    def _log(self, text: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.compare_text.config(state="normal")
        self.compare_text.insert("end", f"[{ts}] {text}\n")
        self.compare_text.see("end")
        self.compare_text.config(state="disabled")

    def _run_bg(self, label: str, work, on_ok=None) -> None:
        if self._busy:
            notify(self, "Bitte warten — Vorgang läuft noch.", "warn")
            return
        self._busy = True
        self._log(f"{label}…")
        self.status_var.set(label + "…")
        self.app.update_idletasks()

        def runner() -> None:
            err = None
            result = None
            try:
                result = work()
            except Exception as exc:
                err = exc
            self.app.after(0, lambda: self._finish_bg(label, err, result, on_ok))

        threading.Thread(target=runner, daemon=True).start()

    def _finish_bg(self, label: str, err: Exception | None, result, on_ok) -> None:
        self._busy = False
        if err:
            self._log(f"FEHLER ({label}): {err}")
            self.status_var.set(f"Fehler: {str(err)[:60]}")
            notify(self, str(err), "error")
        else:
            if on_ok:
                on_ok(result)
            else:
                self._log(f"OK: {label}")
            notify(self, f"{label} fertig.", "ok")

    def _creds(self) -> tuple[str, str, str] | None:
        printer = self.app.printer_var.get().strip()
        creds = self.app._ssh_credentials(printer)
        if not creds:
            return None
        host, password = creds
        return normalize_host(host), password, printer

    def check_status(self) -> None:
        creds = self._creds()
        if not creds:
            return
        host, password, printer = creds

        def work():
            if not printer_reachable(host, 22):
                raise RuntimeError(f"{host}: Port 22 nicht erreichbar.")
            return fetch_printer_info(host, password, printer)

        def on_ok(info: dict) -> None:
            local_n = len(self.app.profiles) if self.app.db_data else 0
            self.status_var.set(
                f"✓ {host} | Profile: {info.get('profile_count', '?')} (Drucker) / {local_n} (lokal)"
            )
            self._log(f"Status OK — Box: {info.get('box_dir')}")

        self._run_bg("Status prüfen", work, on_ok)

    def compare_db(self) -> None:
        if not self.app.db_data:
            notify(self, "Zuerst lokale Material-DB laden.", "warn")
            return
        creds = self._creds()
        if not creds:
            return
        host, password, printer = creds

        def work():
            return download_database_from_printer(host, password, printer)

        def on_ok(remote: dict) -> None:
            self._last_remote_db = remote
            result = compare_databases(self.app.db_data, remote)
            report = format_compare_report(result)
            self.compare_text.config(state="normal")
            self.compare_text.delete("1.0", "end")
            self.compare_text.insert("1.0", report)
            self.compare_text.config(state="disabled")
            self._log("DB-Vergleich abgeschlossen.")

        self._run_bg("DB vergleichen", work, on_ok)

    def pull_options(self) -> None:
        creds = self._creds()
        if not creds:
            return
        host, password, printer = creds

        def work():
            return download_options_from_printer(host, password, printer)

        def on_ok(data: dict) -> None:
            from app.paths import DATA_DIR

            out = DATA_DIR / "material_options_from_printer.json"
            out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            n = len(data.get("brands") or [])
            self._log(f"Options geladen ({n} Marken)")

        self._run_bg("Options vom Drucker", work, on_ok)

