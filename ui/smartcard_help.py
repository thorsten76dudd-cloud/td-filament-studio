"""Hilfe-Dialog wenn der Windows-Smartcard-Dienst hängt."""

from __future__ import annotations

import os
import sys
import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, ttk

from creality_nfc.i18n import t as _t
from creality_nfc.smartcard_service import probe_pcsc, restart_scard_elevated, start_scard_elevated
from ui.dialog_theme import prepare_toplevel
from ui.theme import F_BODY, F_SMALL, apply_text_area_style


def open_services_msc() -> None:
    if sys.platform == "win32":
        os.startfile("services.msc")  # type: ignore[attr-defined]


class SmartcardHelpDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, on_retry: Callable[[], None] | None = None) -> None:
        super().__init__(parent)
        self.title(_t("scard.dialog_title"))
        self.minsize(480, 400)

        state = probe_pcsc()
        label = _t(f"scard.state.{state}") if state else state
        if label.startswith("scard.state."):
            label = state
        ttk.Label(
            self,
            text=_t("scard.status_prefix", label=label),
            font=F_BODY,
        ).pack(anchor="w", padx=16, pady=(16, 8))

        box = tk.Text(self, wrap="word", height=14, font=F_SMALL, padx=8, pady=8)
        apply_text_area_style(box)
        box.pack(fill="both", expand=True, padx=16, pady=8)
        box.insert("1.0", _t("scard.help_text"))
        box.config(state="disabled")

        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=16, pady=12)
        ttk.Button(btns, text=_t("scard.btn.close"), command=self.destroy).pack(side="right")
        ttk.Button(btns, text=_t("scard.btn.open_services"), command=open_services_msc).pack(
            side="right", padx=8
        )
        ttk.Button(
            btns,
            text=_t("scard.btn.restart_uac"),
            command=lambda: self._retry(on_retry),
            style="Accent.TButton",
        ).pack(side="left")

        prepare_toplevel(self, parent, width=520, height=440, geometry_key="smartcard_help")

    def _retry(self, on_retry: Callable[[], None] | None) -> None:
        state = probe_pcsc()
        if state == "service_stuck":
            ok = restart_scard_elevated()
        else:
            ok = start_scard_elevated()
        if not ok:
            messagebox.showerror(_t("scard.title"), _t("scard.err.uac_failed"), parent=self)
            return
        messagebox.showinfo(
            _t("scard.title"),
            _t("scard.cmd_sent"),
            parent=self,
        )
        if on_retry:
            self.after(5000, on_retry)
