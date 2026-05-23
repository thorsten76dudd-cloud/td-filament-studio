"""Eingebettete Spulen-Verwaltung (Tab Meine Spulen)."""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import colorchooser, filedialog, ttk
from typing import TYPE_CHECKING, Callable

from app.constants import printer_int_to_display
from creality_nfc.cfs_adopt import SLOT_LABELS
from creality_nfc.cfs_layout import cfs_slot_label
from creality_nfc.cfs_ui_options import cfs_box_count_from_app, cfs_slot_combobox_values
from creality_nfc.printer_store import load_printers
from creality_nfc.materials import FilamentProfile
from creality_nfc.spool_inventory import Spool, SpoolInventory, parse_cfs_slot_index
from creality_nfc.spool_profile import spool_fields_from_profile
from creality_nfc.spool_usage import deduct_grams, is_low_filament, weight_class_to_grams
from creality_nfc.tag_io import WEIGHT_CODES
from ui.color_presets_menu import show_color_presets
from ui.color_swatch import apply_preview_label, make_swatch_photo, normalize_hex
from ui.profile_pick_dialog import ask_filament_profile
from ui.components import scrollable_tab
from ui.dialog_theme import prepare_toplevel
from ui.theme import BG_SUBTLE, CARD, ERR, F_BODY, F_SECTION, TEXT, WARN
from ui.dialog_theme import theme_dialog
from ui.tooltip import tip
from ui.messaging import confirm, notify

if TYPE_CHECKING:
    from app.main_window import TDFilamentStudioApp


class SpoolEditPanel(ttk.LabelFrame):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, text="Spule bearbeiten")
        theme_dialog(self)
        self._spool_id = SpoolInventory.new_id()
        self._tag_uid = ""
        self._extra_tag_uids: list[str] = []
        self._usage_log: list[dict] = []
        self._profiles_fn: Callable[[], list[FilamentProfile]] | None = None
        self._db_data_fn: Callable[[], dict | None] | None = None
        pad = {"padx": 8, "pady": 3}

        self.label_var = tk.StringVar()
        self.brand_var = tk.StringVar()
        self.material_var = tk.StringVar()
        self.fid_var = tk.StringVar()
        self.color_var = tk.StringVar(value="FFFFFF")
        self.weight_var = tk.StringVar(value="1 KG")
        self.printer_var = tk.StringVar()
        self.serial_var = tk.StringVar(value="000001")
        self.remaining_var = tk.StringVar()
        self.notes_var = tk.StringVar()
        self.cfs_slot_var = tk.StringVar(value="")

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        _canvas, form = scrollable_tab(body)

        fields = (
            ("Bezeichnung", self.label_var),
            ("Bemerkung", self.notes_var),
            ("Marke", self.brand_var),
            ("Material", self.material_var),
            ("Filament-ID (5 Ziffern)", self.fid_var),
            ("Seriennummer", self.serial_var),
            ("Restgewicht (g)", self.remaining_var),
            ("Drucker am Tag", self.printer_var),
        )
        for text, var in fields:
            ttk.Label(form, text=text, style="Muted.TLabel").pack(anchor="w", **pad)
            ttk.Entry(form, textvariable=var).pack(fill="x", **pad)

        db_row = ttk.Frame(form)
        db_row.pack(fill="x", padx=8, pady=(4, 2))
        self._btn_from_db = tip(
            ttk.Button(
                db_row,
                text="Aus Material-DB übernehmen…",
                command=self._apply_from_material_db,
                style="Accent.TButton",
            ),
            "Marke, Material, Filament-ID und Profilfarbe aus der Material-Datenbank laden.",
        )
        self._btn_from_db.pack(side="left")

        ttk.Label(form, text="Farbe", style="Muted.TLabel").pack(anchor="w", **pad)
        color_row = ttk.Frame(form)
        color_row.pack(fill="x", padx=8, pady=(0, 3))
        self._color_preview = tk.Label(
            color_row,
            width=4,
            height=1,
            relief="solid",
            borderwidth=1,
            bg="#FFFFFF",
            text="",
        )
        self._color_preview.pack(side="left", padx=(0, 6))
        ttk.Entry(color_row, textvariable=self.color_var, width=10).pack(side="left")
        self.color_var.trace_add("write", lambda *_: self._update_color_preview())
        self._btn_color_pick = tip(
            ttk.Button(color_row, text="Farbe…", command=self._pick_color_dialog, style="Secondary.TButton"),
            "Windows-Farbauswahl (wie im RFID-Tab).",
        )
        self._btn_color_pick.pack(side="left", padx=(6, 0))
        self._btn_color_presets = tip(
            ttk.Button(color_row, text="Presets", command=self._show_color_presets, style="Secondary.TButton"),
            "Standard-Filamentfarben (Schwarz, Weiß, Creality Blau …).",
        )
        self._btn_color_presets.pack(side="left", padx=(4, 0))
        ttk.Label(form, text="Hex ohne # — oder Farbe… / Presets", style="Muted.TLabel").pack(
            anchor="w", padx=8, pady=(0, 4)
        )
        self._update_color_preview()

        ttk.Label(form, text="Gewichtsklasse", style="Muted.TLabel").pack(anchor="w", **pad)
        ttk.Combobox(
            form,
            textvariable=self.weight_var,
            values=list(WEIGHT_CODES.keys()),
            state="readonly",
        ).pack(fill="x", **pad)

        ttk.Label(form, text="CFS-Slot (am Drucker)", style="Muted.TLabel").pack(anchor="w", **pad)
        self._cfs_slot_combo = ttk.Combobox(
            form,
            textvariable=self.cfs_slot_var,
            values=cfs_slot_combobox_values(1),
            state="readonly",
        )
        self._cfs_slot_combo.pack(fill="x", **pad)

        ttk.Label(form, text="Standort (physisch)", style="Muted.TLabel").pack(anchor="w", **pad)
        loc_vals = [""] + [p.name for p in load_printers()] + ["Lager / Regal"]
        self.location_printer_var = tk.StringVar(value="")
        ttk.Combobox(
            form,
            textvariable=self.location_printer_var,
            values=loc_vals,
        ).pack(fill="x", **pad)

        passport = ttk.LabelFrame(form, text="  Filament-Passport  ", padding=6)
        passport.pack(fill="x", **pad)
        ttk.Label(passport, text="Geöffnet am (YYYY-MM-DD)", style="Muted.TLabel").pack(anchor="w")
        self.opened_at_var = tk.StringVar(value="")
        ttk.Entry(passport, textvariable=self.opened_at_var, width=16).pack(anchor="w", pady=(0, 4))
        ttk.Label(passport, text="Charge / Batch-ID", style="Muted.TLabel").pack(anchor="w")
        self.batch_id_var = tk.StringVar(value="")
        ttk.Entry(passport, textvariable=self.batch_id_var).pack(fill="x", pady=(0, 4))
        self._passport_last_var = tk.StringVar(value="—")
        ttk.Label(
            passport,
            textvariable=self._passport_last_var,
            style="Muted.TLabel",
            wraplength=280,
            justify="left",
        ).pack(anchor="w")

        ttk.Label(form, text="RFID-Chips (UIDs)", style="Muted.TLabel").pack(anchor="w", **pad)
        self._tag_uids_label = ttk.Label(
            form,
            text="—",
            style="Muted.TLabel",
            wraplength=300,
            justify="left",
        )
        self._tag_uids_label.pack(anchor="w", padx=8, pady=(0, 3))
        tag_btns = ttk.Frame(form)
        tag_btns.pack(fill="x", padx=8, pady=(0, 3))
        self._tag_pick_var = tk.StringVar()
        self._tag_pick_combo = ttk.Combobox(
            tag_btns,
            textvariable=self._tag_pick_var,
            state="readonly",
            width=24,
        )
        self._tag_pick_combo.pack(side="left", fill="x", expand=True)
        self._tag_remove_btn = tip(
            ttk.Button(
                tag_btns,
                text="Chip entfernen",
                command=self._remove_selected_tag,
                style="Secondary.TButton",
            ),
            "Verknüpfung dieses Chips mit der Spule lösen (Chip am Drucker bleibt unverändert).",
        )
        self._tag_remove_btn.pack(side="left", padx=(6, 0))
        self._tag_remove_btn.config(state="disabled")
        tip(
            ttk.Button(
                tag_btns,
                text="Alle trennen",
                command=self._clear_all_tags,
                style="Secondary.TButton",
            ),
            "Alle Chip-UIDs von dieser Spule entfernen.",
        ).pack(side="left", padx=(6, 0))

        rest_row = ttk.Frame(form)
        rest_row.pack(fill="x", padx=8, pady=(0, 3))
        tip(
            ttk.Button(rest_row, text="Volle Spule", command=self._set_full_weight, style="Secondary.TButton"),
            "Restgewicht = Gewichtsklasse der Spule (z. B. 1000 g).",
        ).pack(side="right")

        footer = ttk.Frame(self)
        footer.pack(side="bottom", fill="x")
        btns = ttk.Frame(footer)
        btns.pack(fill="x", pady=10, padx=8)
        tip(
            ttk.Button(btns, text="Neu / Leeren", command=self.load_new, style="Secondary.TButton"),
            "Formular für eine neue, leere Spule zurücksetzen.",
        ).pack(side="left")
        tip(
            ttk.Button(btns, text="Speichern", command=self._save_click, style="Accent.TButton"),
            "Eingegebene Spulendaten im Inventar speichern.",
        ).pack(side="right")
        self._save_cb = None

    def set_save_handler(self, handler) -> None:
        self._save_cb = handler

    def set_material_db_access(
        self,
        profiles_fn: Callable[[], list[FilamentProfile]],
        db_data_fn: Callable[[], dict | None],
    ) -> None:
        self._profiles_fn = profiles_fn
        self._db_data_fn = db_data_fn

    def _save_click(self) -> None:
        sp = self.build_spool()
        if sp and self._save_cb:
            self._save_cb(sp)

    def _set_full_weight(self) -> None:
        self.remaining_var.set(str(weight_class_to_grams(self.weight_var.get())))

    def refresh_cfs_slot_choices(self, app: "TDFilamentStudioApp") -> None:
        """Dropdown: nur Slots der erkannten CFS (1 Einheit → nur 1A–1D)."""
        combo = getattr(self, "_cfs_slot_combo", None)
        if combo is None:
            return
        n = cfs_box_count_from_app(app)
        vals = cfs_slot_combobox_values(n)
        combo["values"] = vals
        cur = self.cfs_slot_var.get().strip().upper()
        if cur and cur not in vals:
            self.cfs_slot_var.set("")

    def _parse_cfs_slot(self) -> tuple[int | None, int | None]:
        from creality_nfc.cfs_layout import parse_slot_key

        lab = self.cfs_slot_var.get().strip().upper()
        key = parse_slot_key(lab)
        if key:
            return key[0], key[1]
        if lab in SLOT_LABELS:
            return 1, SLOT_LABELS.index(lab)
        return None, None

    def load_new(self) -> None:
        self._spool_id = SpoolInventory.new_id()
        self._tag_uid = ""
        self._extra_tag_uids = []
        self._usage_log = []
        self._tag_uids_label.config(text="— (kein Tag verknüpft)")
        self._refresh_tag_chip_ui()
        self.label_var.set("")
        self.brand_var.set("")
        self.material_var.set("")
        self.fid_var.set("")
        self.color_var.set("FFFFFF")
        self.weight_var.set("1 KG")
        self.printer_var.set("")
        self.serial_var.set("000001")
        self.remaining_var.set("")
        self.notes_var.set("")
        self.cfs_slot_var.set("")
        self.location_printer_var.set("")
        self.opened_at_var.set("")
        self.batch_id_var.set("")
        self._passport_last_var.set("—")
        self._update_color_preview()

    def _update_color_preview(self) -> None:
        apply_preview_label(self._color_preview, self.color_var.get())

    def _apply_color_hex(self, hex_code: str) -> None:
        self.color_var.set(normalize_hex(hex_code))
        self._update_color_preview()

    def _pick_color_dialog(self) -> None:
        current = normalize_hex(self.color_var.get())
        _, hex_color = colorchooser.askcolor(
            parent=self.winfo_toplevel(),
            color="#" + current,
            title="Filamentfarbe",
        )
        if hex_color:
            self._apply_color_hex(hex_color.lstrip("#"))

    def _show_color_presets(self) -> None:
        show_color_presets(self, self._btn_color_presets, self._apply_color_hex)

    def _apply_from_material_db(self) -> None:
        if not self._profiles_fn:
            notify(self, "Material-DB nicht verbunden.", "error")
            return
        profiles = list(self._profiles_fn() or [])
        if not profiles:
            notify(
                self,
                "Keine Profile geladen — Tab „Material-DB“ → „Vom Drucker (SSH)“.",
                "warn",
            )
            return
        picked = ask_filament_profile(self, profiles)
        if not picked:
            return
        data = self._db_data_fn() if self._db_data_fn else None
        fields = spool_fields_from_profile(
            picked,
            data,
            current_label=self.label_var.get(),
        )
        self.brand_var.set(fields["brand"])
        self.material_var.set(fields["material_name"])
        self.fid_var.set(fields["filament_id"])
        if fields.get("label"):
            self.label_var.set(fields["label"])
        if fields.get("printer"):
            self.printer_var.set(fields["printer"])
        if fields.get("color_hex"):
            self.color_var.set(fields["color_hex"])
        self._update_color_preview()
        notify(
            self,
            f"Übernommen: {picked.brand} — {picked.name} (ID {picked.filament_id})",
            "ok",
        )

    def _listed_tag_uids(self) -> list[str]:
        out: list[str] = []
        primary = Spool.normalize_uid(self._tag_uid)
        if primary:
            out.append(primary)
        for raw in self._extra_tag_uids:
            u = Spool.normalize_uid(raw)
            if u and u not in out:
                out.append(u)
        return out

    def _tag_lines_from_state(self) -> str:
        uids = self._listed_tag_uids()
        if not uids:
            return "— (kein Tag verknüpft)"
        return "\n".join(f"Chip {i}: {u}" for i, u in enumerate(uids, 1))

    def _refresh_tag_chip_ui(self) -> None:
        labels = [f"Chip {i}: {u}" for i, u in enumerate(self._listed_tag_uids(), 1)]
        self._tag_pick_combo["values"] = labels
        if labels:
            self._tag_pick_var.set(labels[0])
            self._tag_remove_btn.config(state="normal")
        else:
            self._tag_pick_var.set("")
            self._tag_remove_btn.config(state="disabled")
        self._tag_uids_label.config(text=self._tag_lines_from_state())

    def _uid_from_pick(self) -> str:
        val = self._tag_pick_var.get().strip()
        if ": " in val:
            return val.split(": ", 1)[1].strip()
        return val

    def _persist_after_tag_change(self) -> None:
        sp = self.build_spool()
        if sp and self._save_cb:
            self._save_cb(sp)

    def _remove_selected_tag(self) -> None:
        uid = Spool.normalize_uid(self._uid_from_pick())
        if not uid:
            notify(self, "Kein Chip ausgewählt.", "warn")
            return
        label = self.label_var.get().strip() or "diese Spule"

        def do_remove() -> None:
            if Spool.normalize_uid(self._tag_uid) == uid:
                self._tag_uid = ""
                if self._extra_tag_uids:
                    self._tag_uid = Spool.normalize_uid(self._extra_tag_uids.pop(0))
            else:
                self._extra_tag_uids = [
                    x
                    for x in self._extra_tag_uids
                    if Spool.normalize_uid(x) != uid
                ]
            self._refresh_tag_chip_ui()
            self._persist_after_tag_change()
            notify(
                self,
                f"Chip {uid} von „{label}“ getrennt.\n"
                "Der physische Tag ist unverändert — nur die Verknüpfung hier entfernt.",
                "ok",
            )

        confirm(
            self,
            f"Chip {uid} von „{label}“ entfernen?\n\n"
            "Die Spule bleibt gespeichert; nur die UID-Verknüpfung in der App wird gelöscht.",
            do_remove,
        )

    def _clear_all_tags(self) -> None:
        if not self._listed_tag_uids():
            notify(self, "Keine Chips verknüpft.", "warn")
            return
        label = self.label_var.get().strip() or "diese Spule"

        count = len(self._listed_tag_uids())

        def do_clear() -> None:
            self._tag_uid = ""
            self._extra_tag_uids = []
            self._refresh_tag_chip_ui()
            self._persist_after_tag_change()
            notify(self, f"Alle Chip-Verknüpfungen von „{label}“ entfernt.", "ok")

        confirm(
            self,
            f"Alle RFID-Chips von „{label}“ trennen?\n\n"
            f"Es werden {count} Verknüpfung(en) gelöscht.",
            do_clear,
        )

    def load_spool(self, sp: Spool) -> None:
        self._spool_id = sp.id
        self._tag_uid = sp.tag_uid
        self._extra_tag_uids = list(sp.extra_tag_uids or [])
        self._refresh_tag_chip_ui()
        self.label_var.set(sp.label)
        self.brand_var.set(sp.brand)
        self.material_var.set(sp.material_name)
        self.fid_var.set(sp.filament_id)
        self.color_var.set(sp.color_hex)
        self.weight_var.set(sp.weight or "1 KG")
        self.printer_var.set(printer_int_to_display(sp.printer))
        self.serial_var.set(sp.serial)
        self.remaining_var.set("" if sp.remaining_g is None else str(sp.remaining_g))
        self.notes_var.set(sp.notes)
        self.cfs_slot_var.set(sp.cfs_slot_label())
        self.location_printer_var.set(sp.location_printer or "")
        self.opened_at_var.set(sp.opened_at or "")
        self.batch_id_var.set(sp.batch_id or "")
        if sp.last_print_at:
            fn = sp.last_print_filename or "?"
            dg = (
                f", {sp.last_print_deducted_g} g abgezogen"
                if sp.last_print_deducted_g
                else ""
            )
            self._passport_last_var.set(f"Letzter Druck: {sp.last_print_at[:10]} — {fn}{dg}")
        else:
            self._passport_last_var.set("Letzter Druck: —")
        self._usage_log = list(sp.usage_log or [])
        self._update_color_preview()

    def build_spool(self) -> Spool | None:
        fid = self.fid_var.get().strip()
        if fid and (len(fid) != 5 or not fid.isdigit()):
            notify(self, "Filament-ID: genau 5 Ziffern oder leer.", "warn")
            return None
        rem_raw = self.remaining_var.get().strip()
        remaining: int | None = None
        if rem_raw:
            try:
                remaining = int(rem_raw)
            except ValueError:
                notify(self, "Restgewicht muss eine Zahl sein.", "warn")
                return None
        color = self.color_var.get().strip().lstrip("#").upper()[:6] or "FFFFFF"
        box_id, cfs_slot = self._parse_cfs_slot()
        if cfs_slot is None:
            cfs_slot = parse_cfs_slot_index(self.notes_var.get())
            box_id = 1 if cfs_slot is not None else None
        loc = self.location_printer_var.get().strip()
        if loc == "Lager / Regal":
            loc = ""
        return Spool(
            id=self._spool_id,
            label=self.label_var.get().strip() or "Unbenannt",
            brand=self.brand_var.get().strip(),
            material_name=self.material_var.get().strip(),
            filament_id=fid.zfill(5)[-5:] if fid else "",
            color_hex=color,
            weight=self.weight_var.get(),
            printer=printer_int_to_display(self.printer_var.get().strip()),
            serial=self.serial_var.get().strip() or "000001",
            remaining_g=remaining,
            tag_uid=self._tag_uid,
            extra_tag_uids=list(self._extra_tag_uids),
            notes=self.notes_var.get().strip(),
            cfs_slot=cfs_slot,
            cfs_box_id=box_id,
            opened_at=self.opened_at_var.get().strip(),
            batch_id=self.batch_id_var.get().strip(),
            location_printer=loc,
            usage_log=list(self._usage_log),
        )


class SpoolManagerPanel(ttk.Frame):
    def __init__(self, app: TDFilamentStudioApp) -> None:
        super().__init__(app.tab_spools)
        theme_dialog(self)
        self.app = app

        top = ttk.Frame(self)
        top.pack(fill="x", padx=8, pady=8)
        tip(ttk.Button(top, text="Neu", command=self._new), "Neue leere Spule anlegen.").pack(
            side="left", padx=2
        )
        tip(
            ttk.Button(top, text="Löschen", command=self._delete),
            "Ausgewählte Spule aus dem Inventar entfernen.",
        ).pack(side="left", padx=2)
        tip(
            ttk.Button(top, text="Aus RFID-Tab übernehmen", command=self._from_current),
            "Aktuelle Daten aus dem RFID-Tab als neue Spule übernehmen.",
        ).pack(side="left", padx=6)
        tip(
            ttk.Button(
                top,
                text="Aus Material-DB…",
                command=self._from_material_db_toolbar,
                style="Secondary.TButton",
            ),
            "Profil aus Material-DB in die bearbeitete Spule übernehmen.",
        ).pack(side="left", padx=2)
        tip(
            ttk.Button(top, text="Duplizieren", command=self._duplicate_selected, style="Secondary.TButton"),
            "Ausgewählte Spule als Kopie anlegen.",
        ).pack(side="left", padx=2)
        tip(
            ttk.Button(top, text="Verlauf", command=self._show_usage_history, style="Secondary.TButton"),
            "Verbrauchshistorie der Spule.",
        ).pack(side="left", padx=2)
        tip(
            ttk.Button(top, text="→ RFID-Tab", command=self._apply_to_tag, style="Accent.TButton"),
            "Gewählte Spule in den RFID-Tab laden (zum Tag-Schreiben).",
        ).pack(side="right", padx=4)
        tip(
            ttk.Button(top, text="Etikett speichern…", command=self._label),
            "Spulen-Etikett als Bilddatei exportieren.",
        ).pack(side="right", padx=4)
        tip(
            ttk.Button(
                top,
                text="Standort-Übersicht",
                command=self._show_locations,
                style="Secondary.TButton",
            ),
            "Wo liegt welche Spule (Drucker / Lager)?",
        ).pack(side="right", padx=4)

        body = ttk.Panedwindow(self, orient="horizontal")
        body.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        left = ttk.Frame(body)
        body.add(left, weight=5)

        self._swatch_cache: dict[str, tk.PhotoImage] = {}

        tree_wrap = ttk.Frame(left)
        tree_wrap.pack(fill="both", expand=True)
        tree_wrap.rowconfigure(0, weight=1)
        tree_wrap.columnconfigure(0, weight=1)

        self._tree_cols = ("cfs", "label", "brand", "material", "weight", "rest", "serial", "uid", "notes")
        self._col_titles = {
            "cfs": "CFS",
            "label": "Bezeichnung",
            "brand": "Marke",
            "material": "Material",
            "weight": "Gewicht",
            "rest": "Rest g",
            "serial": "Serie",
            "uid": "Tag-UID",
            "notes": "Bemerkung",
        }
        self._stretch_col = "label"
        self.tree = ttk.Treeview(
            tree_wrap,
            columns=self._tree_cols,
            show="tree headings",
            height=16,
            style="Spool.Treeview",
            selectmode="browse",
        )
        self.tree.heading("#0", text="Farbe", anchor="center")
        self.tree.column("#0", width=52, stretch=False, minwidth=52, anchor="center")
        for c in self._tree_cols:
            anchor = "center" if c in ("cfs", "weight", "rest", "serial") else "w"
            self.tree.heading(c, text=self._col_titles[c], anchor=anchor)
            self.tree.column(
                c,
                width=80,
                minwidth=36,
                stretch=(c == self._stretch_col),
                anchor=anchor,
            )
        self._tree_body_font = tkfont.Font(font=F_BODY)
        self._tree_head_font = tkfont.Font(font=F_SECTION)

        self.tree.tag_configure("odd", background=CARD, foreground=TEXT)
        self.tree.tag_configure("even", background=BG_SUBTLE, foreground=TEXT)
        self.tree.tag_configure("active", background="#2a4a3c", foreground=TEXT)
        self.tree.tag_configure("low", foreground=WARN)

        sy = ttk.Scrollbar(tree_wrap, orient="vertical", command=self.tree.yview)
        sx = ttk.Scrollbar(tree_wrap, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        sy.grid(row=0, column=1, sticky="ns")
        sx.grid(row=1, column=0, sticky="ew")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Button-1>", self._on_tree_click, add="+")
        self.tree.bind("<Double-1>", lambda _e: self._apply_to_tag())

        deduct_row = ttk.Frame(left)
        deduct_row.pack(fill="x", pady=6)
        ttk.Label(deduct_row, text="Verbrauch (g):").pack(side="left")
        self._deduct_var = tk.StringVar(value="50")
        ttk.Entry(deduct_row, textvariable=self._deduct_var, width=8).pack(side="left", padx=6)
        tip(
            ttk.Button(deduct_row, text="Abziehen", command=self._deduct_apply),
            "Verbrauch in Gramm vom Restgewicht der Spule abziehen.",
        ).pack(side="left")

        right = ttk.Frame(body)
        body.add(right, weight=2)
        self.edit_panel = SpoolEditPanel(right)
        self.edit_panel.pack(fill="both", expand=True, padx=(8, 0))
        self.edit_panel.set_save_handler(self._persist_spool)
        self.edit_panel.set_material_db_access(
            lambda: self.app.profiles,
            lambda: self.app.db_data,
        )

        ttk.Label(
            self,
            text="Links auswählen, rechts bearbeiten und „Speichern“. Doppelklick = Daten in den RFID-Tab.",
            style="Muted.TLabel",
            wraplength=900,
        ).pack(anchor="w", padx=12, pady=(0, 8))

        self.reload()
        self.tree.bind("<Configure>", self._on_tree_configure, add="+")

    def _show_locations(self) -> None:
        from ui.spool_location_dialog import show_spool_location_dialog

        show_spool_location_dialog(self, self.app.inventory)

    def _spool_cell(self, sp: Spool, col: str) -> str:
        if col == "cfs":
            return sp.cfs_slot_label() or ""
        if col == "label":
            return sp.label
        if col == "brand":
            return sp.brand
        if col == "material":
            return sp.material_name
        if col == "weight":
            return sp.weight or ""
        if col == "rest":
            return "" if sp.remaining_g is None else str(sp.remaining_g)
        if col == "serial":
            return sp.serial
        if col == "uid":
            return sp.tag_uids_display(compact=len(sp.all_tag_uids()) > 2)
        if col == "notes":
            return sp.notes or ""
        return ""

    def _measure_col_width(self, texts: list[str], *, min_w: int = 36, max_w: int = 320, pad: int = 20) -> int:
        body = max(self._tree_body_font.measure(t) for t in texts) if texts else min_w
        head = max(self._tree_head_font.measure(t) for t in texts) if texts else min_w
        return int(min(max_w, max(min_w, body, head) + pad))

    def _autosize_columns(self) -> None:
        spools = list(self.app.inventory.sorted_spools())
        for col in self._tree_cols:
            samples = [self._col_titles[col]]
            for sp in spools:
                cell = self._spool_cell(sp, col)
                if cell:
                    samples.append(cell)
            caps = {
                "cfs": 64,
                "weight": 88,
                "rest": 72,
                "serial": 80,
                "uid": 260,
                "label": 320,
            }
            w = self._measure_col_width(samples, max_w=caps.get(col, 280))
            stretch = col == self._stretch_col
            anchor = "center" if col in ("cfs", "weight", "rest", "serial") else "w"
            self.tree.column(col, width=w, minwidth=min(w, 44), stretch=stretch, anchor=anchor)

    def _on_tree_configure(self, event) -> None:
        if event.widget is not self.tree:
            return
        # Nach Fenstergröße: Stretch-Spalte füllt Rest, keine Lücke in der Mitte
        self.tree.column(self._stretch_col, stretch=True)

    def select_spool(self, spool_id: str) -> None:
        """Spule in der Liste markieren (z. B. nach Tag-Schreiben)."""
        if not spool_id or not self.tree.exists(spool_id):
            return
        self.tree.selection_set(spool_id)
        self.tree.focus(spool_id)
        self._paint_selection()
        sp = self.app.inventory.get(spool_id)
        if sp:
            self.edit_panel.load_spool(sp)

    def reload(self) -> None:
        sel_keep = self.tree.selection()
        prefer_id = self.app._active_spool_id or (sel_keep[0] if sel_keep else "")
        for item in self.tree.get_children():
            self.tree.delete(item)
        thr = self.app.settings.low_filament_threshold_g
        for i, s in enumerate(self.app.inventory.sorted_spools()):
            swatch = make_swatch_photo(
                self.winfo_toplevel(),
                s.color_hex,
                cache=self._swatch_cache,
            )
            stripe = "even" if i % 2 else "odd"
            tags: list[str] = [stripe]
            if is_low_filament(s, thr):
                tags.append("low")
            self.tree.insert(
                "",
                "end",
                iid=s.id,
                image=swatch,
                text="",
                tags=tuple(tags),
                values=tuple(self._spool_cell(s, c) for c in self._tree_cols),
            )
        self._autosize_columns()
        if prefer_id and self.tree.exists(prefer_id):
            self.select_spool(prefer_id)
        elif sel_keep and self.tree.exists(sel_keep[0]):
            self.select_spool(sel_keep[0])
        elif self.tree.get_children():
            self.select_spool(self.tree.get_children()[0])

    def _paint_selection(self) -> None:
        for iid in self.tree.get_children():
            tags = [t for t in (self.tree.item(iid, "tags") or ()) if t != "active"]
            self.tree.item(iid, tags=tuple(tags))
        sel = self.tree.selection()
        if sel:
            iid = sel[0]
            tags = list(self.tree.item(iid, "tags") or ())
            if "active" not in tags:
                tags.append("active")
            self.tree.item(iid, tags=tuple(tags))
            self.tree.see(iid)

    def _selected(self) -> Spool | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return self.app.inventory.get(sel[0])

    def _on_tree_click(self, event) -> None:
        row = self.tree.identify_row(event.y)
        if row:
            self.tree.selection_set(row)
            self.tree.focus(row)

    def _on_select(self, _event=None) -> None:
        self._paint_selection()
        sp = self._selected()
        if sp:
            self.edit_panel.load_spool(sp)

    def _new(self) -> None:
        self.tree.selection_remove(self.tree.selection())
        self.edit_panel.load_new()

    def _persist_spool(self, sp: Spool) -> None:
        existing = self.app.inventory.get(sp.id)
        if existing:
            self.app.inventory.update(sp)
            msg = f"„{sp.label}“ aktualisiert."
        else:
            self.app.inventory.add(sp)
            self.app._active_spool_id = sp.id
            msg = f"„{sp.label}“ angelegt."
        thr = self.app.settings.low_filament_threshold_g
        if is_low_filament(sp, thr):
            msg += f" — Rest niedrig ({sp.remaining_g} g)"
        self.app._refresh_spool_combo()
        panel = getattr(self.app, "_device_panel", None) or getattr(
            self.app, "_printer_device_panel", None
        )
        if panel is not None:
            panel.cfs_dashboard.set_inventory(self.app.inventory)
        self.reload()
        self.tree.selection_set(sp.id)
        notify(self, msg, "warn" if is_low_filament(sp, thr) else "ok")

    def prefill(self, sp: Spool) -> None:
        self.edit_panel.load_spool(sp)
        self.tree.selection_remove(self.tree.selection())

    def _delete(self) -> None:
        sp = self._selected()
        if not sp:
            notify(self, "Bitte eine Spule auswählen.", "warn")
            return

        def do_delete() -> None:
            self.app.inventory.delete(sp.id)
            if self.app._active_spool_id == sp.id:
                self.app._active_spool_id = ""
            self.app._refresh_spool_combo()
            self.reload()
            self.edit_panel.load_new()
            notify(self, f"„{sp.label}“ gelöscht.", "ok")

        confirm(self, f"Spule „{sp.label}“ löschen?", do_delete)

    def _from_current(self) -> None:
        self.edit_panel.load_spool(self.app.spool_from_form())
        self.tree.selection_remove(self.tree.selection())

    def _from_material_db_toolbar(self) -> None:
        self.edit_panel._apply_from_material_db()

    def _deduct_apply(self) -> None:
        sp = self._selected()
        if not sp:
            notify(self, "Bitte eine Spule in der Liste wählen.", "warn")
            return
        try:
            grams = int(self._deduct_var.get().strip())
        except ValueError:
            notify(self, "Gramm als Zahl eingeben.", "warn")
            return
        if grams < 1 or grams > 5000:
            notify(self, "Wert zwischen 1 und 5000 g.", "warn")
            return
        if sp.remaining_g is None:
            sp.remaining_g = weight_class_to_grams(sp.weight)
        deduct_grams(sp, grams, note="Manuell abgezogen")
        self.app.inventory.update(sp)
        self.app._refresh_spool_combo()
        self.reload()
        self.tree.selection_set(sp.id)
        self.edit_panel.load_spool(sp)
        thr = self.app.settings.low_filament_threshold_g
        notify(
            self,
            f"Rest: {sp.remaining_g} g",
            "warn" if is_low_filament(sp, thr) else "ok",
        )

    def _duplicate_selected(self) -> None:
        sp = self._selected()
        if not sp:
            notify(self, "Bitte eine Spule auswählen.", "warn")
            return
        copy = Spool(
            id=SpoolInventory.new_id(),
            label=f"{sp.label} (Kopie)"[:80],
            brand=sp.brand,
            material_name=sp.material_name,
            filament_id=sp.filament_id,
            color_hex=sp.color_hex,
            weight=sp.weight,
            printer=sp.printer,
            serial=sp.serial,
            remaining_g=sp.remaining_g,
            tag_uid="",
            notes=sp.notes,
            cfs_slot=None,
            usage_log=[],
        )
        self.app.inventory.add(copy)
        self.reload()
        self.tree.selection_set(copy.id)
        self.edit_panel.load_spool(copy)
        notify(self, f"Kopie „{copy.label}“ angelegt.", "ok")

    def _show_usage_history(self) -> None:
        sp = self._selected()
        if not sp:
            notify(self, "Bitte eine Spule wählen.", "warn")
            return
        dlg = tk.Toplevel(self)
        dlg.title(f"Verlauf — {sp.label}")
        prepare_toplevel(dlg, self, width=480, height=320, geometry_key="spool_usage_log")
        txt = tk.Text(dlg, wrap="word", height=14)
        txt.pack(fill="both", expand=True, padx=10, pady=10)
        if not sp.usage_log:
            txt.insert("1.0", "Noch kein Verbrauch eingetragen.")
        else:
            for row in reversed(sp.usage_log[-40:]):
                ts = row.get("ts", "?")
                g = row.get("grams", 0)
                note = row.get("note", "")
                rest = row.get("remaining_after", "")
                line = f"{ts}  −{g} g"
                if note:
                    line += f"  ({note})"
                if rest != "":
                    line += f"  → Rest {rest} g"
                txt.insert("end", line + "\n")
        txt.config(state="disabled")
        ttk.Button(dlg, text="Schließen", command=dlg.destroy).pack(pady=8)

    def _label(self) -> None:
        sp = self._selected()
        if not sp:
            notify(self, "Bitte eine Spule auswählen.", "warn")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".html",
            initialfile=f"etikett_{sp.label.replace(' ', '_')}.html",
            filetypes=[("HTML-Etikett", "*.html"), ("Text", "*.txt")],
        )
        if not path:
            return
        try:
            import webbrowser

            from creality_nfc.spool_label import write_spool_label_html

            if str(path).lower().endswith(".html"):
                write_spool_label_html(Path(path), sp)
                webbrowser.open(Path(path).as_uri())
                notify(self, f"Etikett (HTML) — im Browser drucken:\n{path}", "ok")
            else:
                lines = [
                    f"Spule: {sp.label}",
                    f"Marke: {sp.brand} · {sp.material_name}",
                    f"Rest: {sp.remaining_g} g" if sp.remaining_g is not None else "Rest: —",
                    f"SN: {sp.serial} · ID {sp.filament_id}",
                    f"UID: {sp.tag_uid or '—'}",
                ]
                Path(path).write_text("\n".join(lines), encoding="utf-8")
                notify(self, f"Etikett: {path}", "ok")
        except OSError as exc:
            notify(self, str(exc), "error")

    def _apply_to_tag(self) -> None:
        sp = self._selected()
        if not sp:
            sp = self.edit_panel.build_spool()
        if not sp:
            notify(self, "Keine Spule zum Übernehmen.", "warn")
            return
        self.app.notebook.select(self.app.tab_tag)
        self.app.update_idletasks()
        try:
            self.app.apply_spool(sp)
        except Exception as exc:
            notify(self, f"Daten teilweise übernommen: {exc}", "warn")
        notify(self, f"„{sp.label}“ → RFID-Tab übernommen.", "ok")
