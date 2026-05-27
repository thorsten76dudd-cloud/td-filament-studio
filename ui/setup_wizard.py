"""Kurzer Ersteinrichtungs-Dialog."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from creality_nfc.config import MATERIAL_DB_PRINTER_ONLY
from creality_nfc.i18n import t as _t
from creality_nfc.smartcard_service import probe_pcsc, scard_status_message
from ui.components import scrollable_tab
from ui.dialog_theme import prepare_toplevel


class SetupWizardDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        *,
        has_database: bool,
        show_on_startup: bool = False,
        on_open_help: Callable[[], None],
        on_connect_reader: Callable[[], None],
        on_load_db: Callable[[], None],
        on_done: Callable[[bool], None],
    ) -> None:
        super().__init__(parent)
        self.title(_t("wiz.title"))
        self.minsize(500, 420)

        footer = ttk.Frame(self, padding=(14, 10))
        footer.pack(side="bottom", fill="x")

        self.show_on_startup_var = tk.BooleanVar(value=show_on_startup)
        ttk.Checkbutton(
            footer,
            text=_t("wiz.show_on_startup"),
            variable=self.show_on_startup_var,
        ).pack(anchor="w", pady=(0, 10))

        btns = ttk.Frame(footer)
        btns.pack(fill="x")
        ttk.Button(btns, text=_t("wiz.btn.open_help"), command=on_open_help, style="Secondary.TButton").pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(btns, text=_t("wiz.btn.connect_reader"), command=on_connect_reader, style="Secondary.TButton").pack(
            side="left", padx=(0, 8)
        )
        if not has_database:
            load_label = _t("wiz.btn.load_printer") if MATERIAL_DB_PRINTER_ONLY else _t("wiz.btn.load_cloud")
            ttk.Button(btns, text=load_label, command=on_load_db, style="Secondary.TButton").pack(
                side="left", padx=(0, 8)
            )
        ttk.Button(
            btns,
            text=_t("wiz.btn.done"),
            command=lambda: self._finish(on_done),
            style="Accent.TButton",
        ).pack(side="right")

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        _canvas, scroll = scrollable_tab(body)

        pad = {"padx": 14, "pady": 6}
        ttk.Label(
            scroll,
            text=_t("wiz.welcome"),
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", **pad)

        ttk.Label(
            scroll,
            text=_t("wiz.intro.body"),
            wraplength=480,
            justify="left",
            style="Muted.TLabel",
        ).pack(anchor="w", **pad)

        state = probe_pcsc()
        checks = [
            (
                _t("wiz.check.scard"),
                state in ("ok", "no_reader"),
                scard_status_message(state),
            ),
            (
                _t("wiz.hw.reader"),
                state == "ok",
                _t("wiz.hw.reader_hint"),
            ),
            (
                _t("wiz.check.materialdb"),
                has_database,
                (
                    _t("wiz.check.materialdb_hint_printer")
                    if MATERIAL_DB_PRINTER_ONLY
                    else _t("wiz.check.materialdb_hint_cloud")
                ),
            ),
            (
                _t("wiz.check.tags"),
                True,
                _t("wiz.hw.see_help"),
            ),
        ]

        for title, ok, hint in checks:
            row = ttk.Frame(scroll)
            row.pack(fill="x", **pad)
            mark = "\u2713" if ok else "\u25cb"
            color = "#4ade9a" if ok else "#9aa0a6"
            ttk.Label(row, text=f"{mark}  {title}", foreground=color).pack(anchor="w")
            ttk.Label(row, text=hint, wraplength=460, style="Muted.TLabel").pack(anchor="w", padx=(18, 0))

        ttk.Label(
            scroll,
            text=_t("wiz.flow.body"),
            wraplength=480,
            justify="left",
        ).pack(anchor="w", padx=14, pady=(8, 12))

        prepare_toplevel(self, parent, width=560, height=520, geometry_key="setup_wizard")

    def _finish(self, on_done: Callable[[bool], None]) -> None:
        on_done(self.show_on_startup_var.get())
        self.destroy()
