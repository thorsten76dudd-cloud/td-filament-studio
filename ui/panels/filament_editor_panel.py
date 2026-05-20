"""Eingebetteter Filament-Editor (Tab Material-Datenbank)."""

from __future__ import annotations

import copy
import json
import tkinter as tk
from tkinter import scrolledtext, ttk
from typing import Callable

from creality_nfc.db_lock import is_item_locked, set_item_locked
from creality_nfc.db_store import add_or_update_item, find_item, new_filament_item
from creality_nfc.materials import FilamentProfile
from ui.dialog_theme import theme_dialog
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

PRINT_FIELDS = (
    ("nozzle_temperature", "Düse °C"),
    ("nozzle_temperature_initial_layer", "Düse 1. Layer °C"),
    ("hot_plate_temp", "Heizbett °C"),
    ("hot_plate_temp_initial_layer", "Bett 1. Layer °C"),
    ("filament_flow_ratio", "Flow-Ratio"),
    ("filament_max_volumetric_speed", "Max. Volumen mm³/s"),
    ("filament_retraction_length", "Retraction mm"),
    ("default_filament_colour", "Farbe (Profil)"),
)


class FilamentEditorPanel(ttk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        db_data: dict,
        on_saved: Callable[[dict], None],
    ) -> None:
        super().__init__(parent)
        theme_dialog(self)
        self.db_data = db_data
        self._on_saved = on_saved
        self._existing_item: dict | None = None
        self._template_item: dict | None = None
        self._print_vars: dict[str, tk.StringVar] = {}

        hdr = ttk.Frame(self)
        hdr.pack(fill="x", padx=4, pady=(4, 0))
        self._title = ttk.Label(hdr, text="Filament bearbeiten", font=("Segoe UI", 11, "bold"))
        self._title.pack(side="left")
        tip(
            ttk.Button(hdr, text="Zurücksetzen", command=self._clear_form, style="Secondary.TButton"),
            "Alle Felder leeren (neues Profil vorbereiten).",
        ).pack(side="right", padx=4)
        tip(
            ttk.Button(hdr, text="In Datenbank speichern", command=self._save, style="Accent.TButton"),
            "Nur lokal (k2_pro.json). Der Drucker wird nicht überschrieben.",
        ).pack(side="right", padx=(0, 4))

        pad = {"padx": 8, "pady": 2}
        self.fid_var = tk.StringVar()
        self.brand_var = tk.StringVar(value="Generic")
        self.name_var = tk.StringVar()
        self.type_var = tk.StringVar(value="PLA")
        self.min_var = tk.StringVar(value="190")
        self.max_var = tk.StringVar(value="220")
        self.lock_var = tk.BooleanVar(value=False)

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=4, pady=6)

        tab_base = ttk.Frame(nb)
        nb.add(tab_base, text="  Basis  ")
        ttk.Label(tab_base, text="ID (5 Ziffern)").pack(anchor="w", **pad)
        ttk.Entry(tab_base, textvariable=self.fid_var).pack(fill="x", **pad)
        ttk.Label(tab_base, text="Marke").pack(anchor="w", **pad)
        ttk.Entry(tab_base, textvariable=self.brand_var).pack(fill="x", **pad)
        ttk.Label(tab_base, text="Name").pack(anchor="w", **pad)
        ttk.Entry(tab_base, textvariable=self.name_var).pack(fill="x", **pad)
        ttk.Label(tab_base, text="Typ").pack(anchor="w", **pad)
        ttk.Combobox(
            tab_base, textvariable=self.type_var, values=FILAMENT_TYPES, state="readonly"
        ).pack(fill="x", **pad)
        row = ttk.Frame(tab_base)
        row.pack(fill="x", **pad)
        ttk.Label(row, text="Min °C").pack(side="left")
        ttk.Entry(row, textvariable=self.min_var, width=8).pack(side="left", padx=6)
        ttk.Label(row, text="Max °C").pack(side="left")
        ttk.Entry(row, textvariable=self.max_var, width=8).pack(side="left", padx=6)
        ttk.Checkbutton(
            tab_base,
            text="Vor Cloud/Drucker-Update schützen (eigene Einstellungen behalten)",
            variable=self.lock_var,
        ).pack(anchor="w", **pad)

        tab_print = ttk.Frame(nb)
        nb.add(tab_print, text="  Druckparameter  ")
        scroll = ttk.Frame(tab_print)
        scroll.pack(fill="both", expand=True)
        for key, label in PRINT_FIELDS:
            rowp = ttk.Frame(scroll)
            rowp.pack(fill="x", **pad)
            ttk.Label(rowp, text=label, width=22).pack(side="left")
            var = tk.StringVar()
            self._print_vars[key] = var
            ttk.Entry(rowp, textvariable=var).pack(side="left", fill="x", expand=True)

        tab_json = ttk.Frame(nb)
        nb.add(tab_json, text="  JSON (kvParam)  ")
        ttk.Label(
            tab_json,
            text="Vollständiges kvParam — Erklärungen im Tab „Hilfe“ → JSON kvParam.",
            style="Muted.TLabel",
        ).pack(anchor="w", **pad)
        self.param_text = scrolledtext.ScrolledText(tab_json, height=12, font=("Consolas", 9))
        self.param_text.pack(fill="both", expand=True, padx=8, pady=4)

        self._clear_form()

    def set_db_data(self, db_data: dict) -> None:
        self.db_data = db_data

    def load_new(self, template_item: dict | None = None) -> None:
        self._title.config(text="Neues Filament")
        self._template_item = template_item
        self._existing_item = None
        self._apply_item(template_item)

    def load_edit(self, profile: FilamentProfile) -> None:
        self._title.config(text=f"Bearbeiten: {profile.brand} — {profile.name}")
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
        self.param_text.delete("1.0", "end")
        self.param_text.insert("1.0", json.dumps(kv, indent=2, ensure_ascii=False))

    def _clear_form(self) -> None:
        self.load_new(None)

    def _merged_kv(self) -> dict:
        try:
            kv = json.loads(self.param_text.get("1.0", "end"))
            if not isinstance(kv, dict):
                raise ValueError("kvParam muss ein JSON-Objekt sein.")
        except json.JSONDecodeError as exc:
            raise ValueError(f"Ungültiges JSON:\n{exc}") from exc
        for key, var in self._print_vars.items():
            val = var.get().strip()
            if val:
                kv[key] = val
        kv["filament_type"] = self.type_var.get().strip()
        kv["filament_vendor"] = self.brand_var.get().strip()
        return kv

    def _save(self) -> None:
        updated = self._commit_save()
        if updated is not None:
            self._on_saved(updated)
            notify(self, f"„{self.brand_var.get()} — {self.name_var.get()}“ gespeichert.", "ok")

    def _commit_save(self) -> dict | None:
        fid = self.fid_var.get().strip()
        if len(fid) != 5 or not fid.isdigit():
            notify(self, "ID muss genau 5 Ziffern haben.", "warn")
            return None
        try:
            min_t = int(self.min_var.get())
            max_t = int(self.max_var.get())
        except ValueError:
            notify(self, "Min/Max müssen Zahlen sein.", "warn")
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

