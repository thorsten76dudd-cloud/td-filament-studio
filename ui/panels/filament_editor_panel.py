"""Eingebetteter Filament-Editor (Tab Filament-Profil)."""

from __future__ import annotations

import copy
import json
import tkinter as tk
from tkinter import scrolledtext, ttk
from typing import Callable

from creality_nfc.config import MATERIAL_DB_PRINTER_ONLY
from creality_nfc.i18n import t as _t
from creality_nfc.db_lock import is_item_locked, set_item_locked
from creality_nfc.db_store import add_or_update_item, find_item, new_filament_item
from creality_nfc.materials import FilamentProfile
from ui.components import scrollable_tab, section
from ui.dialog_theme import theme_dialog
from ui.theme import ACCENT, BG, CARD, MUTED, TEXT, apply_text_area_style
from ui.tooltip import tip
from ui.messaging import notify

FILAMENT_TYPES = (
    "PLA",
    "PETG",
    "ABS",
    "ASA",
    "TPU",
    "PA",
    "PC",
    "PVA",
    "HIPS",
)

def _print_fields() -> tuple[tuple[str, str], ...]:
    return (
        ("nozzle_temperature", _t("fep.col.nozzle_c")),
        ("nozzle_temperature_initial_layer", _t("fep.col.nozzle_first_c")),
        ("hot_plate_temp", _t("fep.col.bed_c")),
        ("hot_plate_temp_initial_layer", _t("fep.col.bed_first_c")),
        ("filament_flow_ratio", _t("fep.col.flow_ratio")),
        ("filament_max_volumetric_speed", _t("fep.col.max_volume")),
        ("filament_retraction_length", _t("fep.col.retraction")),
        ("default_filament_colour", _t("fep.col.color_profile")),
    )


PRINT_FIELDS = _print_fields()


class FilamentEditorPanel(ttk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        db_data: dict,
        on_saved: Callable[[dict], None],
        *,
        readonly: bool = False,
    ) -> None:
        super().__init__(parent)
        theme_dialog(self)
        self.db_data = db_data
        self._on_saved = on_saved
        self._readonly = bool(readonly or MATERIAL_DB_PRINTER_ONLY)
        self._existing_item: dict | None = None
        self._template_item: dict | None = None
        self._print_vars: dict[str, tk.StringVar] = {}
        self._base_entries: list[tk.Widget] = []
        self._readonly_value_labels: dict[str, tk.Label] = {}
        self._type_combo: ttk.Combobox | None = None
        self._lock_cb: ttk.Checkbutton | None = None
        self._print_entries: list[tk.Widget] = []

        self.fid_var = tk.StringVar()
        self.brand_var = tk.StringVar(value="Generic")
        self.name_var = tk.StringVar()
        self.type_var = tk.StringVar(value="PLA")
        self.min_var = tk.StringVar(value="190")
        self.max_var = tk.StringVar(value="220")
        self.lock_var = tk.BooleanVar(value=False)

        self._build_header()
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        if self._readonly:
            self._build_readonly_tabs()
        else:
            self._build_editable_tabs()

        self._clear_form()

    def _build_header(self) -> None:
        hdr = ttk.Frame(self)
        hdr.pack(fill="x", padx=8, pady=(8, 4))
        title_txt = _t("fep.title.view_only") if self._readonly else _t("fep.title.new")
        self._title = ttk.Label(hdr, text=title_txt, font=("Segoe UI", 12, "bold"))
        self._title.pack(side="left")
        if self._readonly:
            ttk.Label(
                hdr,
                text=_t("fep.hdr.changes_in_creality"),
                style="Muted.TLabel",
            ).pack(side="right", padx=(12, 0))
        else:
            tip(
                ttk.Button(hdr, text=_t("fep.btn.reset"), command=self._clear_form, style="Secondary.TButton"),
                "Alle Felder leeren (neues Profil vorbereiten).",
            ).pack(side="right", padx=4)
            tip(
                ttk.Button(hdr, text=_t("fep.btn.save_db"), command=self._save, style="Accent.TButton"),
                _t("fep.hdr.local_only"),
            ).pack(side="right", padx=(0, 4))

        if self._readonly:
            self._summary_host = tk.Frame(self, bg=CARD, highlightbackground=MUTED, highlightthickness=1)
            self._summary_host.pack(fill="x", padx=8, pady=(0, 6))
            inner = tk.Frame(self._summary_host, bg=CARD, padx=14, pady=12)
            inner.pack(fill="x")
            self._summary_name = tk.Label(
                inner,
                text="—",
                bg=CARD,
                fg=TEXT,
                font=("Segoe UI", 14, "bold"),
                anchor="w",
            )
            self._summary_name.pack(anchor="w")
            self._summary_sub = tk.Label(
                inner,
                text=_t("fep.summary_placeholder"),
                bg=CARD,
                fg=MUTED,
                font=("Segoe UI", 10),
                anchor="w",
            )
            self._summary_sub.pack(anchor="w", pady=(4, 0))
            self._summary_temp = tk.Label(
                inner,
                text="",
                bg=CARD,
                fg=ACCENT,
                font=("Segoe UI", 10),
                anchor="w",
            )
            self._summary_temp.pack(anchor="w", pady=(6, 0))

    def _build_readonly_tabs(self) -> None:
        tab_base = ttk.Frame(self.nb)
        self.nb.add(tab_base, text=_t("fep.tab.overview"))
        grid_host = section(tab_base, _t("fep.section.master"))
        grid_host.pack(fill="x", padx=4, pady=6)
        for col in range(4):
            grid_host.columnconfigure(col, weight=1 if col % 2 == 1 else 0)
        self._readonly_value_labels.clear()
        fields = (
            ("fid", "Material-ID"),
            ("brand", "Marke"),
            ("name", "Name"),
            ("type", "Typ"),
            ("min", "Min °C"),
            ("max", "Max °C"),
        )
        for row, (key, label) in enumerate(fields):
            r = row // 2
            c = (row % 2) * 2
            ttk.Label(grid_host, text=label, style="Muted.TLabel").grid(
                row=r, column=c, sticky="w", padx=(8, 4), pady=6
            )
            val = tk.Label(
                grid_host,
                text="—",
                bg=BG,
                fg=TEXT,
                font=("Segoe UI", 10),
                anchor="w",
            )
            val.grid(row=r, column=c + 1, sticky="ew", padx=(0, 16), pady=6)
            self._readonly_value_labels[key] = val

        tab_print = ttk.Frame(self.nb)
        self.nb.add(tab_print, text=_t("fep.tab.print"))
        scroll_frame = ttk.Frame(tab_print)
        scroll_frame.pack(fill="both", expand=True, padx=4, pady=4)
        _canvas, scroll_inner = scrollable_tab(scroll_frame)
        print_sec = section(scroll_inner, _t("fep.section.temp_flow"))
        print_sec.pack(fill="x", padx=2, pady=4)
        print_sec.columnconfigure(1, weight=1)
        print_sec.columnconfigure(3, weight=1)
        for i, (key, label) in enumerate(PRINT_FIELDS):
            r = i // 2
            col_base = (i % 2) * 2
            ttk.Label(print_sec, text=label, style="Muted.TLabel").grid(
                row=r, column=col_base, sticky="w", padx=(8, 4), pady=5
            )
            var = tk.StringVar()
            self._print_vars[key] = var
            val_lbl = tk.Label(
                print_sec,
                text="—",
                bg=BG,
                fg=TEXT,
                font=("Segoe UI", 10),
                anchor="w",
            )
            val_lbl.grid(row=r, column=col_base + 1, sticky="ew", padx=(0, 12), pady=5)
            self._readonly_value_labels[f"print_{key}"] = val_lbl

        tab_json = ttk.Frame(self.nb)
        self.nb.add(tab_json, text=_t("fep.tab.json"))
        ttk.Label(
            tab_json,
            text=_t("fep.hint.raw_kvparam"),
            style="Muted.TLabel",
        ).pack(anchor="w", padx=10, pady=(8, 4))
        self.param_text = scrolledtext.ScrolledText(tab_json, height=14, font=("Consolas", 10))
        self.param_text.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        apply_text_area_style(self.param_text)

    def _build_editable_tabs(self) -> None:
        pad = {"padx": 8, "pady": 2}
        tab_base = ttk.Frame(self.nb)
        self.nb.add(tab_base, text=_t("fep.tab.base"))
        ttk.Label(tab_base, text=_t("fep.label.id")).pack(anchor="w", **pad)
        e_fid = ttk.Entry(tab_base, textvariable=self.fid_var)
        e_fid.pack(fill="x", **pad)
        self._base_entries.append(e_fid)
        ttk.Label(tab_base, text=_t("fep.label.brand")).pack(anchor="w", **pad)
        e_brand = ttk.Entry(tab_base, textvariable=self.brand_var)
        e_brand.pack(fill="x", **pad)
        self._base_entries.append(e_brand)
        ttk.Label(tab_base, text=_t("fep.label.name")).pack(anchor="w", **pad)
        e_name = ttk.Entry(tab_base, textvariable=self.name_var)
        e_name.pack(fill="x", **pad)
        self._base_entries.append(e_name)
        ttk.Label(tab_base, text=_t("fep.label.type")).pack(anchor="w", **pad)
        self._type_combo = ttk.Combobox(
            tab_base, textvariable=self.type_var, values=FILAMENT_TYPES, state="readonly"
        )
        self._type_combo.pack(fill="x", **pad)
        row = ttk.Frame(tab_base)
        row.pack(fill="x", **pad)
        ttk.Label(row, text=_t("fep.label.min_c")).pack(side="left")
        e_min = ttk.Entry(row, textvariable=self.min_var, width=8)
        e_min.pack(side="left", padx=6)
        self._base_entries.append(e_min)
        ttk.Label(row, text=_t("fep.label.max_c")).pack(side="left")
        e_max = ttk.Entry(row, textvariable=self.max_var, width=8)
        e_max.pack(side="left", padx=6)
        self._base_entries.append(e_max)
        self._lock_cb = ttk.Checkbutton(
            tab_base,
            text=_t("fep.chk.protect_from_cloud"),
            variable=self.lock_var,
        )
        self._lock_cb.pack(anchor="w", **pad)

        tab_print = ttk.Frame(self.nb)
        self.nb.add(tab_print, text=_t("fep.tab.print"))
        scroll_outer = ttk.Frame(tab_print)
        scroll_outer.pack(fill="both", expand=True)
        _canvas, scroll = scrollable_tab(scroll_outer)
        for key, label in PRINT_FIELDS:
            rowp = ttk.Frame(scroll)
            rowp.pack(fill="x", padx=8, pady=3)
            ttk.Label(rowp, text=label, width=22).pack(side="left")
            var = tk.StringVar()
            self._print_vars[key] = var
            pe = ttk.Entry(rowp, textvariable=var)
            pe.pack(side="left", fill="x", expand=True)
            self._print_entries.append(pe)

        tab_json = ttk.Frame(self.nb)
        self.nb.add(tab_json, text=_t("fep.tab.json"))
        ttk.Label(
            tab_json,
            text=_t("fep.hint.full_kvparam"),
            style="Muted.TLabel",
        ).pack(anchor="w", **pad)
        self.param_text = scrolledtext.ScrolledText(tab_json, height=12, font=("Consolas", 9))
        self.param_text.pack(fill="both", expand=True, padx=8, pady=4)
        apply_text_area_style(self.param_text)

    def _update_readonly_display(self) -> None:
        if not self._readonly:
            return
        name = self.name_var.get().strip() or "—"
        brand = self.brand_var.get().strip() or "—"
        fid = self.fid_var.get().strip() or "—"
        mtype = self.type_var.get().strip() or "—"
        self._summary_name.config(text=name if name != "—" else brand)
        self._summary_sub.config(text=f"{brand}  ·  ID {fid}  ·  {mtype}")
        min_t = self.min_var.get().strip()
        max_t = self.max_var.get().strip()
        if min_t or max_t:
            self._summary_temp.config(text=_t("fep.summary.temp_range", min_t=min_t, max_t=max_t))
        else:
            self._summary_temp.config(text="")
        mapping = {
            "fid": fid,
            "brand": brand,
            "name": name,
            "type": mtype,
            "min": f"{min_t} °C" if min_t else "—",
            "max": f"{max_t} °C" if max_t else "—",
        }
        for key, text in mapping.items():
            lbl = self._readonly_value_labels.get(key)
            if lbl is not None:
                lbl.config(text=text or "—")
        for key, var in self._print_vars.items():
            lbl = self._readonly_value_labels.get(f"print_{key}")
            if lbl is not None:
                val = var.get().strip()
                lbl.config(text=val if val else "—")

    def set_db_data(self, db_data: dict) -> None:
        self.db_data = db_data

    def load_new(self, template_item: dict | None = None) -> None:
        if self._readonly:
            self._title.config(text=_t("fep.title.view_only"))
            self._template_item = template_item
            self._existing_item = None
            self._apply_item(template_item)
            return
        self._title.config(text=_t("fep.title.new"))
        self._template_item = template_item
        self._existing_item = None
        self._apply_item(template_item)

    def load_edit(self, profile: FilamentProfile) -> None:
        if self._readonly:
            self._title.config(
                text=_t("fep.title.view", brand=profile.brand, name=profile.name)
            )
        else:
            self._title.config(
                text=_t("fep.title.edit", brand=profile.brand, name=profile.name)
            )
        self._template_item = None
        self._existing_item = find_item(
            self.db_data,
            profile.filament_id,
            brand=profile.brand,
            name=profile.name,
        )
        self._apply_item(self._existing_item)

    def _apply_item(self, item: dict | None) -> None:
        base = (item or {}).get("base", {})
        kv = copy.deepcopy((item or {}).get("kvParam", {}))
        fid = str(base.get("id", "")).strip()
        if len(fid) > 5:
            fid = fid[-5:]
        self.fid_var.set(fid.zfill(5)[-5:] if fid.isdigit() else "")
        self.brand_var.set(str(base.get("brand", "Generic")))
        self.name_var.set(str(base.get("name", "")))
        mtype = str(
            base.get("meterialType")
            or base.get("materialType")
            or base.get("type")
            or "PLA"
        ).strip()
        self.type_var.set(mtype or "PLA")
        self.min_var.set(str(base.get("minTemp", 190)))
        self.max_var.set(str(base.get("maxTemp", 220)))
        self.lock_var.set(is_item_locked(item) if item else False)
        for key, var in self._print_vars.items():
            var.set(str(kv.get(key, "")))
        self.param_text.configure(state="normal")
        self.param_text.delete("1.0", "end")
        self.param_text.insert("1.0", json.dumps(kv, indent=2, ensure_ascii=False))
        if self._readonly:
            self.param_text.configure(state="disabled")
            self._update_readonly_display()

    def _apply_readonly_widgets(self) -> None:
        if not self._readonly:
            return
        for w in self._base_entries:
            if isinstance(w, ttk.Entry):
                w.configure(state="disabled")
        for w in self._print_entries:
            if isinstance(w, ttk.Entry):
                w.configure(state="disabled")
        if self._type_combo is not None:
            self._type_combo.configure(state="disabled")
        if self._lock_cb is not None:
            self._lock_cb.state(["disabled"])

    def _clear_form(self) -> None:
        self.load_new(None)

    def _merged_kv(self) -> dict:
        try:
            kv = json.loads(self.param_text.get("1.0", "end"))
            if not isinstance(kv, dict):
                raise ValueError("kvParam muss ein JSON-Objekt sein.")
        except json.JSONDecodeError as exc:
            raise ValueError(_t("fep.error.invalid_json", exc=exc)) from exc
        for key, var in self._print_vars.items():
            val = var.get().strip()
            if val:
                kv[key] = val
        kv["filament_type"] = self.type_var.get().strip()
        kv["filament_vendor"] = self.brand_var.get().strip()
        return kv

    def _save(self) -> None:
        if self._readonly:
            notify(self, _t("fep.notify.save_disabled"), "warn")
            return
        updated = self._commit_save()
        if updated is not None:
            self._on_saved(updated)
            notify(
                self,
                _t(
                    "fep.notify.saved",
                    brand=self.brand_var.get(),
                    name=self.name_var.get(),
                ),
                "ok",
            )

    def _commit_save(self) -> dict | None:
        if self._readonly:
            return None
        fid = self.fid_var.get().strip()
        if len(fid) != 5 or not fid.isdigit():
            notify(self, _t("fep.notify.id_5digits"), "warn")
            return None
        try:
            min_t = int(self.min_var.get())
            max_t = int(self.max_var.get())
        except ValueError:
            notify(self, _t("fep.notify.min_max_numbers"), "warn")
            return None
        try:
            kv = self._merged_kv()
        except ValueError as exc:
            notify(self, str(exc), "error")
            return None
        template = self._existing_item or self._template_item
        item = new_filament_item(
            fid,
            self.brand_var.get().strip(),
            self.name_var.get().strip(),
            self.type_var.get().strip(),
            min_t,
            max_t,
            copy.deepcopy(template) if template else None,
        )
        item["kvParam"] = kv
        set_item_locked(item, self.lock_var.get())
        updated = add_or_update_item(self.db_data, item)
        self.db_data = updated
        self._existing_item = find_item(
            updated,
            fid,
            brand=self.brand_var.get().strip(),
            name=self.name_var.get().strip(),
        )
        return updated
