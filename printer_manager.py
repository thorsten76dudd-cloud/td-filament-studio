"""Dialog: mehrere Drucker verwalten."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ui.messaging import confirm, notify

from app.constants import DEFAULT_PRINTER, PRINTER_OPTIONS
from creality_nfc.i18n import t as _t
from creality_nfc.printer_ssh import default_password
from creality_nfc.printer_store import PrinterProfile, load_printers, save_printers
from ui.dialog_theme import prepare_toplevel
from ui.tooltip import tip


class PrinterManagerDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, on_apply=None) -> None:
        super().__init__(parent)
        self._on_apply = on_apply
        self.title(_t("pm.dialog_title"))
        self.minsize(560, 380)

        # Fußzeile zuerst packen — sonst werden Buttons auf Höhe 0 gequetscht
        bar = ttk.LabelFrame(self, text=_t("pm.actions_label"), padding=(12, 10))
        bar.pack(side="bottom", fill="x", padx=12, pady=(0, 12))

        btn_row = ttk.Frame(bar)
        btn_row.pack(fill="x")

        def action_btn(text: str, command, style: str, help_txt: str) -> None:
            tip(
                ttk.Button(btn_row, text=text, command=command, style=style),
                help_txt,
            ).pack(side="left", padx=(0, 8))

        action_btn(
            _t("pm.btn.add"),
            self._add,
            "Secondary.TButton",
            _t("pm.btn.add_tip"),
        )
        action_btn(
            _t("pm.btn.edit"),
            self._edit,
            "Secondary.TButton",
            _t("pm.btn.edit_tip"),
        )
        action_btn(
            _t("pm.btn.delete"),
            self._delete,
            "Secondary.TButton",
            _t("pm.btn.delete_tip"),
        )
        if on_apply is not None:
            action_btn(
                _t("pm.btn.adopt"),
                self._apply_selected,
                "Accent.TButton",
                _t("pm.btn.adopt_tip"),
            )
        action_btn(_t("pm.btn.close"), self.destroy, "Secondary.TButton", _t("pm.btn.close_tip"))

        body = ttk.Frame(self)
        body.pack(side="top", fill="both", expand=True, padx=12, pady=12)

        self.tree = ttk.Treeview(
            body, columns=("name", "host", "model"), show="headings", height=10
        )
        self.tree.heading("name", text=_t("pm.col.name"))
        self.tree.heading("host", text=_t("pm.col.host"))
        self.tree.heading("model", text=_t("pm.col.model"))
        self.tree.column("name", width=140)
        self.tree.column("host", width=180)
        self.tree.column("model", width=120)
        scroll = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self._reload()
        prepare_toplevel(self, parent, width=620, height=420, geometry_key="printer_manager")

    def _reload(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        for p in load_printers():
            self.tree.insert("", "end", iid=p.name, values=(p.name, p.host, p.model))

    def _selected(self) -> PrinterProfile | None:
        sel = self.tree.selection()
        if not sel:
            return None
        for p in load_printers():
            if p.name == sel[0]:
                return p
        return None

    def _apply_selected(self) -> None:
        p = self._selected()
        if not p:
            notify(self, _t("pm.notify.pick_printer"), "warn")
            return
        if self._on_apply:
            self._on_apply(p)
        self.destroy()

    def _add(self) -> None:
        self._edit_dialog(None)

    def _edit(self) -> None:
        p = self._selected()
        if not p:
            notify(self, _t("pm.notify.pick_entry"), "warn")
            return
        self._edit_dialog(p)

    def _edit_dialog(self, profile: PrinterProfile | None) -> None:
        dlg = tk.Toplevel(self)
        dlg.title(_t("pm.edit.title_edit") if profile else _t("pm.edit.title_new"))
        dlg.minsize(440, 400)

        btn_bar = ttk.Frame(dlg, padding=(12, 12))
        btn_bar.pack(side="bottom", fill="x")

        form = ttk.Frame(dlg, padding=12)
        form.pack(fill="both", expand=True)

        name_v = tk.StringVar(value=profile.name if profile else _t("pm.edit.default_name"))
        host_v = tk.StringVar(value=profile.host if profile else "")
        pass_v = tk.StringVar(
            value=profile.password if profile else default_password(DEFAULT_PRINTER)
        )
        from app.constants import normalize_printer_model

        model_v = tk.StringVar(
            value=normalize_printer_model(profile.model if profile else DEFAULT_PRINTER)
        )
        pad = {"padx": 0, "pady": 5}
        for label, var, is_pwd in (
            (_t("pm.edit.label_name"), name_v, False),
            (_t("pm.edit.label_ip"), host_v, False),
            (_t("pm.edit.label_password"), pass_v, True),
        ):
            ttk.Label(form, text=label).pack(anchor="w", **pad)
            show = "*" if is_pwd else ""
            ttk.Entry(form, textvariable=var, show=show).pack(fill="x", **pad)
        ttk.Label(form, text=_t("pm.edit.label_model")).pack(anchor="w", **pad)
        ttk.Combobox(
            form,
            textvariable=model_v,
            values=list(PRINTER_OPTIONS),
            state="readonly",
        ).pack(fill="x", **pad)
        ttk.Label(
            form,
            text=_t("app.supported_printers_short"),
            style="Muted.TLabel",
            wraplength=400,
        ).pack(anchor="w", pady=(0, 8))

        def ok() -> None:
            if not host_v.get().strip():
                notify(dlg, _t("pm.edit.ip_missing"), "warn")
                return
            model = model_v.get().strip()
            if model not in PRINTER_OPTIONS:
                notify(
                    dlg,
                    _t("pm.notify.pick_supported"),
                    "warn",
                )
                return
            from creality_nfc.printer_store import upsert_printer

            upsert_printer(
                PrinterProfile(
                    name_v.get().strip() or _t("pm.edit.default_fallback"),
                    host_v.get().strip(),
                    pass_v.get(),
                    model,
                )
            )
            dlg.destroy()
            self._reload()

        ttk.Button(btn_bar, text=_t("btn.cancel"), command=dlg.destroy, style="Secondary.TButton").pack(
            side="right", padx=(8, 0)
        )
        ttk.Button(btn_bar, text=_t("btn.ok"), command=ok, style="Accent.TButton").pack(side="right")
        prepare_toplevel(dlg, self, width=460, height=420, geometry_key="printer_edit")

    def _delete(self) -> None:
        p = self._selected()
        if not p:
            return

        def do_delete() -> None:
            save_printers([x for x in load_printers() if x.name != p.name])
            self._reload()

        confirm(self, _t("pm.confirm.delete", name=p.name), do_delete)
