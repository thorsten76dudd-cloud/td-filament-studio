"""Dialog: Drucker-IP und SSH-Passwort."""

from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from ui.messaging import notify

from creality_nfc.i18n import t as _t
from creality_nfc.printer_ssh import default_password
from creality_nfc.printer_store import PrinterProfile, load_printers, migrate_legacy_settings, upsert_printer
from printer_manager import PrinterManagerDialog
from ui.dialog_theme import prepare_toplevel

def _settings_file() -> Path:
    from app.paths import DATA_DIR

    return DATA_DIR / "printer_settings.json"


SETTINGS_FILE = _settings_file()


def load_settings() -> dict:
    migrate_legacy_settings()
    if SETTINGS_FILE.is_file():
        try:
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    printers = load_printers()
    if printers:
        p = printers[0]
        return {"host": p.host, "password": p.password, "printer": p.model}
    return {}


def save_settings(host: str, password: str, printer: str) -> None:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = load_settings()
    data["host"] = host
    data["password"] = password
    data["printer"] = printer
    SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    upsert_printer(PrinterProfile(name=f"{printer} @ {host}", host=host, password=password, model=printer))


class PrinterConnectDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, printer_label: str) -> None:
        super().__init__(parent)
        self.title(_t("pc.title"))
        self.resizable(False, False)
        self.result: tuple[str, str] | None = None

        migrate_legacy_settings()
        saved = load_settings()
        self._printers = load_printers()

        self.host_var = tk.StringVar(value=saved.get("host", ""))
        self.pass_var = tk.StringVar(
            value=saved.get("password") or default_password(printer_label)
        )
        self.saved_var = tk.StringVar()

        pad = {"padx": 12, "pady": 6}
        ttk.Label(
            self,
            text=_t("pc.intro"),
            wraplength=360,
        ).pack(anchor="w", **pad)

        row = ttk.Frame(self)
        row.pack(fill="x", **pad)
        ttk.Label(row, text=_t("pc.saved")).pack(side="left")
        names = [p.name for p in self._printers]
        self.saved_combo = ttk.Combobox(
            row, textvariable=self.saved_var, values=names, state="readonly", width=28
        )
        self.saved_combo.pack(side="left", padx=8)
        self.saved_combo.bind("<<ComboboxSelected>>", self._pick_saved)
        ttk.Button(row, text=_t("pc.manage"), command=self._manage).pack(side="left")
        if names:
            self.saved_var.set(names[0])
            self._pick_saved()

        ttk.Label(self, text=_t("pc.label_ip")).pack(anchor="w", **pad)
        ttk.Entry(self, textvariable=self.host_var, width=36).pack(fill="x", **pad)

        ttk.Label(self, text=_t("pc.label_password")).pack(anchor="w", **pad)
        ttk.Entry(self, textvariable=self.pass_var, width=36, show="•").pack(fill="x", **pad)

        ttk.Label(
            self,
            text=_t("pc.k2_hint"),
            style="Muted.TLabel",
            wraplength=360,
        ).pack(anchor="w", **pad)

        row = ttk.Frame(self)
        row.pack(fill="x", pady=10, padx=12)
        ttk.Button(row, text=_t("btn.cancel"), command=self.destroy).pack(side="right")
        ttk.Button(row, text=_t("printer.btn.connect"), command=self._ok, style="Accent.TButton").pack(
            side="right", padx=8
        )

        prepare_toplevel(self, parent, width=420, height=380, geometry_key="printer_connect")

    def _pick_saved(self, _event=None) -> None:
        name = self.saved_var.get()
        for p in self._printers:
            if p.name == name:
                self.host_var.set(p.host)
                self.pass_var.set(p.password)
                break

    def _manage(self) -> None:
        dlg = PrinterManagerDialog(self)
        self.wait_window(dlg)
        self._printers = load_printers()
        names = [p.name for p in self._printers]
        self.saved_combo["values"] = names
        if names:
            self.saved_var.set(names[0])
            self._pick_saved()

    def _ok(self) -> None:
        host = self.host_var.get().strip()
        password = self.pass_var.get()
        if not host:
            notify(self, _t("pc.notify.enter_ip"), "warn")
            return
        self.result = (host, password)
        self.destroy()
