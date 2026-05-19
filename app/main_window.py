"""TD Filament Studio — main window."""

from __future__ import annotations

import os
import sys
import threading
import tkinter as tk

from ui.tk_root import AppTk
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, scrolledtext, ttk

from app.constants import (
    DATA_DIR,
    DEFAULT_PRINTER,
    PRINTER_OPTIONS,
    SKIP_DATA_JSON,
    SUPPORTED_PRINTERS_SHORT,
    normalize_printer_model,
)
from creality_nfc.app_settings import DEFAULT_SETTINGS_PATH, AppSettings
from creality_nfc.config import APP_NAME, APP_TAGLINE, APP_VERSION
from creality_nfc.db_merge import merge_databases, merge_stats
from creality_nfc.db_store import (
    db_path_for_printer,
    find_item,
    list_items_for_id,
    load_database_raw,
    profiles_from_db,
    save_database,
)
from creality_nfc.data_backup import (
    backup_data_dir,
    default_backup_name,
    factory_reset_data_dir,
    import_cfs_rfid_zip,
    restore_data_dir,
)
from creality_nfc.db_sync import download_material_database
from creality_nfc.printer_store import migrate_legacy_settings
from creality_nfc.material_options import export_material_options
from creality_nfc.materials import (
    FilamentProfile,
    builtin_profiles,
    normalize_filament_id,
)
from creality_nfc.printer_camera import printer_reachable
from creality_nfc.printer_ssh import (
    download_database_from_printer,
    upload_database_to_printer,
)
from creality_nfc.reader import CrealityNfcReader, NfcReaderError
from creality_nfc.reader_monitor import NfcCardMonitor
from creality_nfc.smartcard_service import (
    probe_pcsc,
    restart_scard_elevated,
    scard_status_message,
    start_scard_elevated,
)
from creality_nfc.spool_inventory import Spool, SpoolInventory
from creality_nfc.spool_profile import resolve_filament_profile
from creality_nfc.cfs_adopt import CfsSlotInfo, match_profile_id
from creality_nfc.cfs_spool_link import bind_slot, find_spool_for_deduct, find_spool_for_slot, slot_label
from creality_nfc.cfs_feed import find_loaded_slot_index
from creality_nfc.gcode_filament import (
    build_slot_usage_plan,
    cache_gcode_from_printer,
    estimate_grams_for_slot,
    material_hint_from_gcode_path,
    primary_gcode_slot_mapping,
    refresh_state_for_filament_usage,
    resolve_local_gcode_path,
)
from creality_nfc.slicer_import import (
    collect_slicer_profiles_from_paths,
    merge_slicer_profiles_into_db,
)
from creality_nfc.printer_gcode import parse_gcode_files
from creality_nfc.spool_usage import deduct_grams, is_low_filament, weight_class_to_grams
from creality_nfc.app_log import log_event, log_exception
from creality_nfc.tag_io import (
    WEIGHT_CODES,
    TagSession,
    build_tag_payload,
    payload_bytes_from_read,
    parse_tag_payload,
    payload_is_empty,
    verify_tag_payload,
)
from creality_nfc.update_check import fetch_latest_release_tag, is_newer
from printer_connect import load_settings, save_settings
from printer_manager import PrinterManagerDialog
from tag_tools import TagToolsDialog
from creality_nfc.color_from_image import color_from_image_path
from creality_nfc.tag_export import build_tag_export, save_tag_export
from ui.color_presets_menu import show_color_presets
from ui.color_swatch import color_from_tag_field, normalize_hex
from ui.setup_wizard import SetupWizardDialog
from app.bundled_assets import CHIP_TAG_PLASTIC_3MF, save_bundled_asset
from ui.tag_holder_links import (
    TagHolderLinksDialog,
    URL_PLASTIC_SPOOL_HOLDER,
)
from ui.components import labeled_row, scrollable_tab, section
from ui.rounded_widgets import rounded_button
from ui.messaging import confirm
from ui.post_print_deduct_dialog import DeductRow, ask_post_print_deductions
from ui.rfid_placement_help import RFID_PLACEMENT_SHORT
from ui.panels.filament_editor_panel import FilamentEditorPanel
from ui.panels.help_panel import HelpPanel
from ui.panels.model_library_panel import ModelLibraryPanel
from ui.panels.printer_device_panel import PrinterDevicePanel
from ui.panels.printer_panel import PrinterDashboardPanel
from ui.panels.settings_panel import SettingsPanel
from ui.panels.spool_panel import SpoolManagerPanel
from ui.tooltip import tip
from ui.theme import (
    ACCENT_DARK,
    ACCENT_LIGHT,
    ACCENT_SOFT,
    BG,
    BG_SUBTLE,
    BORDER,
    CARD,
    CONFIRM_BG,
    ERR,
    F_BODY,
    F_HEAD,
    F_MONO,
    F_SMALL,
    F_TITLE,
    FONT,
    HEADER,
    HEADER_SURFACE,
    MUTED,
    F_BADGE,
    F_HEADER_SUB,
    OK,
    ON_HEADER,
    ON_HEADER_ERR,
    ON_HEADER_MUTED,
    ON_HEADER_OK,
    ON_HEADER_SUB,
    ON_HEADER_WARN,
    TEXT,
    TEXT_SECONDARY,
    WARN,
    apply_text_area_style,
    apply_theme,
)


class TDFilamentStudioApp(AppTk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME}  ·  {APP_TAGLINE}")
        self.minsize(1280, 800)

        apply_theme(self)
        try:
            self.state("zoomed")
        except tk.TclError:
            try:
                self.attributes("-zoomed", True)
            except tk.TclError:
                self.geometry("1280x900")

        self.reader = CrealityNfcReader()
        self.settings = AppSettings.load(DEFAULT_SETTINGS_PATH)
        self.profiles: list[FilamentProfile] = []
        self.db_data: dict | None = None
        self.db_path: Path | None = None
        self.color_hex = "FFFFFF"
        self._color_from_user = False
        self._demo_mode = True
        self._db_source = "demo"
        self._monitor: NfcCardMonitor | None = None
        self._tag_busy = False
        self._last_auto_uid = ""
        self._active_spool_id = ""
        self._scard_needs_start = False
        self._scard_help_shown = False
        self.inventory = SpoolInventory(DATA_DIR / "spools.json")
        self._filtered_profiles: list[FilamentProfile] = []
        self._material_combo_map: dict[str, tuple[str, str, str]] = {}
        self._current_profile: tuple[str, str, str] = ("", "", "")
        self._batch_waiting = False
        self._bg_job_running = False
        self._last_tag_export: dict | None = None
        self._suppress_auto_read_until = 0.0
        self._chip_dup_step = ""
        self._chip_dup_payload: bytes | None = None
        self._chip_dup_source_uid = ""
        self._chip_dup_source_spool_id = ""
        self._last_write_template: dict | None = None
        self._post_print_prompted = False
        self._post_print_deduct_file = ""
        migrate_legacy_settings()

        self._build_menu()
        # Statusleiste zuerst (unten), dann Kopf + Inhalt — sonst überlappt der Body die Leiste.
        self._build_statusbar()
        self._build_header()
        self._build_body()
        self._build_message_area()

        self._load_materials()
        self.after(300, self._initial_nfc_check)
        self.after(600, self._start_monitor)
        if self.settings.check_updates:
            self.after(1500, self._check_updates_quiet)
        if self.settings.show_setup_on_startup or not self.settings.setup_completed:
            self.after(900, self._maybe_show_setup_wizard)
        self._schedule_reader_poll()
        self.after(1200, self._sync_creality_watcher)

    # ── UI construction ─────────────────────────────────────────────

    def _build_menu(self) -> None:
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        m_file = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Datei", menu=m_file)
        m_import = tk.Menu(m_file, tearoff=0)
        m_file.add_cascade(label="Import", menu=m_import)
        m_import.add_command(label="Von Creality Cloud…", command=self.sync_database)
        m_import.add_command(label="Vom Drucker (SSH)…", command=self.sync_from_printer)
        m_import.add_command(label="Slicer-Profile (Orca JSON)…", command=self.import_slicer_profiles)
        m_import.add_command(label="Datenbank-Datei öffnen…", command=self.pick_database)
        m_import.add_command(label="Cloud in lokale DB mergen…", command=self.merge_cloud)
        m_import.add_command(label="CFS-RFID ZIP…", command=self.import_cfs_zip)
        m_file.add_separator()
        m_file.add_command(label="DB öffnen…", command=self.pick_database)
        m_file.add_command(label="DB speichern unter…", command=self.save_database_as)
        m_file.add_command(label="Zum Drucker senden (SSH)…", command=self.upload_to_printer)
        m_file.add_command(label="material_options.json exportieren…", command=self.export_options)
        m_file.add_separator()
        m_file.add_command(label="Daten sichern (ZIP)…", command=self.backup_data)
        m_file.add_command(label="Daten wiederherstellen (ZIP)…", command=self.restore_data)
        m_file.add_command(label="CFS-RFID ZIP importieren…", command=self.import_cfs_zip)
        m_file.add_command(label="Tag-Daten exportieren…", command=self.export_tag_data)
        m_file.add_command(label="Tag leeren…", command=self.format_tag_quick)
        m_file.add_command(label="Chip duplizieren…", command=self.duplicate_chip_start)
        m_file.add_separator()
        m_file.add_command(label="Beenden", command=self.destroy)

        m_extra = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Navigation", menu=m_extra)
        m_extra.add_command(label="Tab: RFID-Tag", command=lambda: self.notebook.select(self.tab_tag))
        m_extra.add_command(label="Tag leeren…", command=self.format_tag_quick)
        m_extra.add_command(label="Chip duplizieren…", command=self.duplicate_chip_start)
        m_extra.add_command(label="Tab: Filament-Profil", command=lambda: self.notebook.select(self.tab_profile))
        m_extra.add_command(label="Tab: Material-DB", command=lambda: self.notebook.select(self.tab_db))
        m_extra.add_command(label="Tab: Drucker", command=lambda: self.notebook.select(self.tab_printer))
        m_extra.add_command(label="Tab: Meine Spulen", command=lambda: self.notebook.select(self.tab_spools))
        m_extra.add_command(
            label="Tab: Modell-Bibliothek", command=lambda: self.notebook.select(self.tab_models)
        )
        m_extra.add_command(label="Tab: Hilfe", command=lambda: self.notebook.select(self.tab_help))
        m_extra.add_separator()
        m_extra.add_command(label="Tag-Halter (Links)…", command=self.open_tag_holder_links)
        m_extra.add_command(label="Tab: Einstellungen", command=lambda: self.notebook.select(self.tab_settings))
        m_extra.add_command(label="Drucker verwalten…", command=self.open_printer_manager)
        m_extra.add_command(label="Nach Updates suchen", command=self.check_updates)

    def _build_header(self) -> None:
        hdr = tk.Frame(self, bg=HEADER, height=96)
        hdr.pack(fill="x", side="top")
        hdr.pack_propagate(False)

        left = tk.Frame(hdr, bg=HEADER)
        left.pack(side="left", fill="y", padx=28, pady=14)
        title_row = tk.Frame(left, bg=HEADER)
        title_row.pack(anchor="w")
        tk.Label(title_row, text=APP_NAME, bg=HEADER, fg="#ffffff", font=F_TITLE).pack(side="left")
        tk.Label(
            title_row,
            text=" TD ",
            bg=ACCENT_SOFT,
            fg=ACCENT_LIGHT,
            font=(FONT, 10, "bold"),
            padx=8,
            pady=4,
        ).pack(side="left", padx=(12, 0))
        tk.Label(
            left,
            text=f"{APP_TAGLINE}  ·  Version {APP_VERSION}",
            bg=HEADER,
            fg=ON_HEADER_SUB,
            font=F_HEADER_SUB,
            wraplength=720,
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

        right = tk.Frame(hdr, bg=HEADER)
        right.pack(side="right", fill="y", padx=28, pady=14)
        self.db_badge = tk.Label(
            right,
            text="Datenbank: …",
            bg=HEADER_SURFACE,
            fg=ON_HEADER,
            font=F_BADGE,
            padx=16,
            pady=10,
        )
        self.db_badge.pack(anchor="e")

    def _build_body(self) -> None:
        body = ttk.Frame(self, padding=(12, 8, 12, 10))
        body.pack(fill="both", expand=True, side="top")

        self.notebook = ttk.Notebook(body)
        self.notebook.pack(fill="both", expand=True)

        tab_pad = 4
        self.tab_tag = ttk.Frame(self.notebook, padding=tab_pad)
        self.tab_profile = ttk.Frame(self.notebook, padding=tab_pad)
        self.tab_db = ttk.Frame(self.notebook, padding=tab_pad)
        self.tab_printer = ttk.Frame(self.notebook, padding=0)
        self.tab_spools = ttk.Frame(self.notebook, padding=tab_pad)
        self.tab_models = ttk.Frame(self.notebook, padding=tab_pad)
        self.tab_help = ttk.Frame(self.notebook, padding=tab_pad)
        self.tab_settings = ttk.Frame(self.notebook, padding=tab_pad)

        self.notebook.add(self.tab_tag, text=" RFID-Tag ")
        self.notebook.add(self.tab_profile, text=" Filament-Profil ")
        self.notebook.add(self.tab_db, text=" Material-DB ")
        self.notebook.add(self.tab_printer, text=" Drucker ")
        self.notebook.add(self.tab_spools, text=" Meine Spulen ")
        self.notebook.add(self.tab_models, text=" Modell-Bibliothek ")
        self.notebook.add(self.tab_help, text=" Hilfe ")
        self.notebook.add(self.tab_settings, text=" Einstellungen ")

        saved = load_settings()
        from creality_nfc.printer_ssh import default_password

        printer_name = saved.get("printer", "K2 Pro")
        self.ssh_host_var = tk.StringVar(value=saved.get("host", ""))
        self.ssh_pass_var = tk.StringVar(
            value=saved.get("password") or default_password(printer_name)
        )

        self._build_tab_tag()
        self._build_tab_profile()
        self._build_tab_database()
        self._build_tab_printer()
        self._build_tab_spools()
        ModelLibraryPanel(self).pack(fill="both", expand=True)
        HelpPanel(self.tab_help).pack(fill="both", expand=True)
        self._settings_panel = SettingsPanel(
            self.tab_settings,
            self.settings,
            self._apply_settings,
            on_show_setup=lambda: self._show_setup_wizard(mark_done=False),
            on_factory_reset=self._factory_reset_app,
        )
        self._settings_panel.pack(fill="both", expand=True, padx=8, pady=8)
        self.notebook.bind("<<NotebookTabChanged>>", self._on_notebook_tab)

    def _on_notebook_tab(self, _event=None) -> None:
        try:
            tab = self.notebook.nametowidget(self.notebook.select())
        except tk.TclError:
            return
        if tab is self.tab_printer and hasattr(self, "_device_panel"):
            self._device_panel.on_tab_shown()

    def _build_tab_tag(self) -> None:
        root = ttk.Frame(self.tab_tag)
        root.pack(fill="both", expand=True)

        # Feste Aktionsleiste — bleibt sichtbar, kein Überlappen mit Formular
        action_bar = ttk.LabelFrame(root, text="  Aktionen  ", padding=(14, 12))
        action_bar.pack(fill="x", pady=(0, 6))

        tag_info = tk.Frame(
            action_bar,
            bg=BG_SUBTLE,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        tag_info.pack(fill="x", pady=(0, 10))
        self.spool_match_label = tk.Label(
            tag_info,
            text="— Tag auflegen oder „Tag lesen“ —",
            font=F_HEAD,
            bg=BG_SUBTLE,
            fg=MUTED,
            anchor="w",
            justify="left",
            wraplength=820,
        )
        self.spool_match_label.pack(fill="x", padx=12, pady=(10, 4))
        tag_sub = tk.Frame(tag_info, bg=BG_SUBTLE)
        tag_sub.pack(fill="x", padx=12, pady=(0, 10))
        tk.Label(
            tag_sub,
            text="UID",
            font=F_SMALL,
            bg=BG_SUBTLE,
            fg=MUTED,
        ).pack(side="left")
        self.uid_label = tk.Label(
            tag_sub,
            text="—",
            font=F_MONO,
            bg=BG_SUBTLE,
            fg=TEXT_SECONDARY,
        )
        self.uid_label.pack(side="left", padx=(8, 0))
        self.tag_extra_label = tk.Label(
            tag_sub,
            text="",
            font=F_SMALL,
            bg=BG_SUBTLE,
            fg=MUTED,
            anchor="w",
        )
        self.tag_extra_label.pack(side="left", padx=(16, 0))

        btn_row = ttk.Frame(action_bar)
        btn_row.pack(fill="x")
        color_box = tk.Frame(btn_row, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        color_box.pack(side="left", padx=(0, 10))
        self.color_preview = tk.Label(
            color_box,
            text="#FFFFFF",
            bg="#FFFFFF",
            width=6,
            height=2,
            font=F_SMALL,
            fg=MUTED,
        )
        self.color_preview.pack(padx=6, pady=6)
        self._update_color_preview()
        tip(
            ttk.Button(btn_row, text="Farbe…", command=self.pick_color, style="Secondary.TButton"),
            "Filamentfarbe für den RFID-Tag wählen (Hex-Farbcode).",
        ).pack(side="left", padx=(0, 4))
        self._btn_color_presets = tip(
            ttk.Button(btn_row, text="Presets", command=self.show_color_presets, style="Secondary.TButton"),
            "Standardfarben (Schwarz, Weiß, Creality-Blau …).",
        )
        self._btn_color_presets.pack(side="left", padx=(0, 4))
        tip(
            ttk.Button(btn_row, text="Foto…", command=self.pick_color_from_image, style="Secondary.TButton"),
            "Farbe aus Filament-Foto schätzen (JPG/PNG).",
        ).pack(side="left", padx=(0, 8))
        tip(
            ttk.Button(btn_row, text="Tag lesen", command=self.read_tag, style="Secondary.TButton"),
            "Aktuellen Inhalt vom NFC-Tag einlesen (UID, Farbe, Gewicht, Filament-ID).",
        ).pack(side="left", padx=(0, 8))
        tip(
            ttk.Button(btn_row, text="Tag schreiben", command=self.write_tag, style="Accent.TButton"),
            "Gewähltes Profil, Farbe und Seriennummer auf den Tag schreiben.",
        ).pack(side="left", padx=(0, 4))
        tip(
            ttk.Button(btn_row, text="Tag leeren…", command=self.format_tag_quick, style="Secondary.TButton"),
            "Creality-Daten vom Tag löschen (nicht physisch zerstören — danach neu beschreiben).",
        ).pack(side="left", padx=(0, 4))
        tip(
            ttk.Button(btn_row, text="Chip duplizieren…", command=self.duplicate_chip_start, style="Secondary.TButton"),
            "Quell-Chip lesen, Ziel-Chip beschreiben — 1:1-Kopie (Assistent mit Meldungen).",
        ).pack(side="left", padx=(0, 8))
        tip(
            ttk.Button(btn_row, text="Tag export…", command=self.export_tag_data, style="Secondary.TButton"),
            "Zuletzt gelesene Tag-Daten als JSON speichern.",
        ).pack(side="left", padx=(0, 8))
        tip(
            ttk.Button(btn_row, text="Spule speichern", command=self.save_current_spool, style="Secondary.TButton"),
            "Aktuelle Tag-Daten als Spule unter „Meine Spulen“ speichern.",
        ).pack(side="left")

        _canvas, scroll = scrollable_tab(root)

        sec_reader = section(scroll, "NFC-Reader")
        r1 = ttk.Frame(sec_reader)
        r1.pack(fill="x", pady=(0, 4))
        tip(
            ttk.Button(r1, text="Reader verbinden", command=self.connect_reader, style="Secondary.TButton"),
            "ACS NFC-Reader per USB verbinden (PC/SC muss laufen).",
        ).pack(side="left", padx=(0, 6), pady=2)
        tip(
            ttk.Button(
                r1, text="Smartcard starten", command=self.start_smartcard_service, style="Secondary.TButton"
            ),
            "Windows-Dienst „Smartcard“ starten (oft Admin-Rechte nötig).",
        ).pack(side="left", padx=(0, 6), pady=2)
        tip(
            ttk.Button(r1, text="Tag-Speicher…", command=self.open_tag_tools, style="Secondary.TButton"),
            "Erweiterte Tag-Tools: Sektoren anzeigen, leeren, Prüfsumme.",
        ).pack(side="left", pady=2)
        r2 = ttk.Frame(sec_reader)
        r2.pack(fill="x")
        for text, cmd, help_txt in (
            (
                "Chip-Tag.3mf speichern…",
                lambda: save_bundled_asset(
                    self,
                    CHIP_TAG_PLASTIC_3MF,
                    title="Chip-Tag für Creality-Kunststoffspule speichern",
                ),
                "RFID-Tag-Halter (3MF) für offizielle Creality-Kunststoffspulen — 2× pro Spule drucken.",
            ),
            (
                "STL Kunststoffrolle…",
                lambda: webbrowser.open(URL_PLASTIC_SPOOL_HOLDER),
                "Printables: weitere RFID-Halter für Creality-Kunststoffspulen.",
            ),
            (
                "Tag-Halter (Links)…",
                self.open_tag_holder_links,
                "Alle STL/3MF-Halter: Kunststoff, Karton, Universal — Printables & Creality Cloud.",
            ),
            (
                "Drucker wählen…",
                self.open_printer_manager,
                "Drucker-IP, Modell und SSH-Passwort verwalten und übernehmen.",
            ),
            ("DB speichern…", self.save_database_as, "Material-Datenbank als JSON-Datei speichern."),
        ):
            tip(
                ttk.Button(r2, text=text, command=cmd, style="Secondary.TButton"),
                help_txt,
            ).pack(side="left", padx=(0, 6), pady=2)
        tip(
            ttk.Button(
                r2,
                text="Gleiche Spule nochmal",
                command=self._duplicate_last_tag_template,
                style="Accent.TButton",
            ),
            "Letztes Material erneut laden — Seriennummer +1, neuer Tag.",
        ).pack(side="left", padx=(0, 6), pady=2)

        ttk.Label(
            scroll,
            text=RFID_PLACEMENT_SHORT,
            style="Muted.TLabel",
            wraplength=900,
            justify="left",
        ).pack(anchor="w", padx=2, pady=(0, 4))

        sec_mat = section(scroll, "Filament für den Tag")
        form = ttk.Frame(sec_mat)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)

        def _grid_row(row: int, label: str, widget: tk.Misc, *, pady: int = 4) -> None:
            ttk.Label(form, text=label, width=16, anchor="w").grid(
                row=row, column=0, sticky="nw", padx=(0, 8), pady=pady
            )
            widget.grid(row=row, column=1, sticky="ew", pady=pady)

        ip_wrap = ttk.Frame(form)
        ttk.Entry(ip_wrap, textvariable=self.ssh_host_var).pack(fill="x")
        _grid_row(0, "Drucker-IP", ip_wrap, pady=(0, 2))
        ttk.Label(
            form,
            text="Gleiche IP für RFID, Drucker-Tab und SSH.",
            style="Muted.TLabel",
            wraplength=520,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 6))

        self.search_var = tk.StringVar()
        search_wrap = ttk.Frame(form)
        search_e = ttk.Entry(search_wrap, textvariable=self.search_var)
        search_e.pack(side="left", fill="x", expand=True)
        self.search_var.trace_add("write", lambda *_: self._apply_material_filter())
        tip(
            ttk.Button(search_wrap, text="✕", width=3, command=self._clear_search),
            "Suchfeld leeren und alle Materialien wieder anzeigen.",
        ).pack(side="left", padx=(6, 0))
        _grid_row(2, "Suche", search_wrap)

        self.printer_var = tk.StringVar(value=DEFAULT_PRINTER)
        self.brand_var = tk.StringVar()
        self.material_var = tk.StringVar()
        self.weight_var = tk.StringVar(value="1 KG")
        self.selected_profile_var = tk.StringVar(value="—")

        self.printer_combo = ttk.Combobox(
            form, textvariable=self.printer_var, values=list(PRINTER_OPTIONS), state="readonly"
        )
        _grid_row(3, "Drucker (am Tag)", self.printer_combo)
        self.printer_combo.bind("<<ComboboxSelected>>", self._on_printer_change)
        saved_printer = normalize_printer_model(
            load_settings().get("printer", DEFAULT_PRINTER)
        )
        self.printer_var.set(saved_printer)
        ttk.Label(
            form,
            text=SUPPORTED_PRINTERS_SHORT,
            style="Muted.TLabel",
            wraplength=520,
            justify="left",
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 6))

        self.brand_combo = ttk.Combobox(form, textvariable=self.brand_var, state="readonly")
        _grid_row(5, "Marke", self.brand_combo)
        self.brand_combo.bind("<<ComboboxSelected>>", self._on_brand_change)

        mat_wrap = ttk.Frame(form)
        mat_wrap.columnconfigure(0, weight=1)
        self.material_combo = ttk.Combobox(mat_wrap, textvariable=self.material_var, state="readonly")
        self.material_combo.grid(row=0, column=0, sticky="ew")
        ttk.Label(
            mat_wrap,
            textvariable=self.selected_profile_var,
            style="Muted.TLabel",
            wraplength=480,
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))
        _grid_row(6, "Material", mat_wrap)
        self.material_combo.bind("<<ComboboxSelected>>", self._on_material_selected)

        prof_btns = ttk.Frame(form)
        prof_btns.columnconfigure(0, weight=1)
        prof_btns.columnconfigure(1, weight=1)
        tip(
            ttk.Button(
                prof_btns,
                text="Profil bearbeiten",
                command=self.edit_filament,
                style="Secondary.TButton",
            ),
            "Tab „Filament-Profil“ öffnen und Material bearbeiten.",
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4), pady=2)
        tip(
            ttk.Button(
                prof_btns,
                text="Neues Profil…",
                command=self.add_filament,
                style="Secondary.TButton",
            ),
            "Neues Filament-Profil in der Datenbank anlegen.",
        ).grid(row=0, column=1, sticky="ew", pady=2)
        tip(
            ttk.Button(
                prof_btns,
                text="Datenbank laden…",
                command=self._goto_db_tab,
                style="Secondary.TButton",
            ),
            "Zum Tab Material-Datenbank wechseln (Import vom Drucker/Cloud).",
        ).grid(row=1, column=0, columnspan=2, sticky="ew", pady=2)
        _grid_row(7, "Profil", prof_btns, pady=(6, 4))

        weight_c = ttk.Combobox(
            form, textvariable=self.weight_var, values=list(WEIGHT_CODES.keys()), state="readonly"
        )
        _grid_row(8, "Gewicht (Tag)", weight_c)

        self.spool_var = tk.StringVar()
        spool_wrap = ttk.Frame(form)
        self.spool_combo = ttk.Combobox(spool_wrap, textvariable=self.spool_var, state="readonly")
        self.spool_combo.pack(side="left", fill="x", expand=True)
        tip(
            ttk.Button(spool_wrap, text="…", width=3, command=self._goto_spools_tab),
            "Tab „Meine Spulen“ öffnen (Inventar verwalten).",
        ).pack(side="left", padx=(6, 0))
        _grid_row(9, "Meine Spule", spool_wrap)
        self.spool_combo.bind("<<ComboboxSelected>>", self._on_spool_selected)
        self._refresh_spool_combo()

        opts = ttk.LabelFrame(scroll, text="  Optionen  ", padding=6)
        opts.pack(fill="x", pady=(0, 6))
        self.auto_read_var = tk.BooleanVar(value=self.settings.auto_read_tag)
        self.auto_write_var = tk.BooleanVar(value=self.settings.auto_write_tag)
        self.batch_write_var = tk.BooleanVar(value=self.settings.batch_write_mode)
        self.auto_serial_var = tk.BooleanVar(value=self.settings.auto_increment_serial)
        self.auto_sync_spool_var = tk.BooleanVar(value=self.settings.auto_sync_spool_on_tag)
        oc = ttk.Frame(opts)
        oc.pack(fill="x")
        oc.columnconfigure(0, weight=1)
        oc.columnconfigure(1, weight=1)
        ttk.Checkbutton(
            oc,
            text="Auto lesen",
            variable=self.auto_read_var,
            command=self._sync_auto_flags,
        ).grid(row=0, column=0, sticky="w", pady=2)
        ttk.Checkbutton(
            oc,
            text="Auto schreiben",
            variable=self.auto_write_var,
            command=self._sync_auto_flags,
        ).grid(row=0, column=1, sticky="w", pady=2)
        ttk.Checkbutton(
            oc,
            text="Stapelmodus",
            variable=self.batch_write_var,
            command=self._sync_batch_flag,
        ).grid(row=1, column=0, sticky="w", pady=2)
        serial_row = ttk.Frame(oc)
        serial_row.grid(row=1, column=1, sticky="ew", pady=2)
        ttk.Label(serial_row, text="SN").pack(side="left")
        self.serial_var = tk.StringVar(value=self.settings.next_serial_str())
        ttk.Entry(serial_row, textvariable=self.serial_var, width=8).pack(side="left", padx=4)
        ttk.Checkbutton(
            serial_row,
            text="Auto +1",
            variable=self.auto_serial_var,
            command=self._on_serial_mode_change,
        ).pack(side="left")
        ttk.Checkbutton(
            oc,
            text="Spule in „Meine Spulen“ sync",
            variable=self.auto_sync_spool_var,
            command=self._sync_auto_flags,
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=2)

        tip(
            ttk.Button(
                scroll,
                text="→ Tab Filament-Profil (Druckparameter)",
                command=self._goto_profile_tab,
                style="Accent.TButton",
            ),
            "Gewähltes Material im eigenen Tab bearbeiten und in der DB speichern.",
        ).pack(anchor="w", pady=(8, 4))

        sec_diag = section(scroll, "Tag-Rohdaten (Reader-Auslesen)")
        sec_diag.pack(fill="both", expand=True, pady=(8, 4))
        diag_btns = ttk.Frame(sec_diag)
        diag_btns.pack(fill="x", pady=(0, 4))
        tip(
            ttk.Button(
                diag_btns,
                text="Jetzt vom Tag lesen",
                command=self._refresh_tag_diagnostic_manual,
                style="Secondary.TButton",
            ),
            "Tag auflegen und kompletten Speicher-Dump + Payload anzeigen.",
        ).pack(side="left")

        self.tag_diag_text = tk.Text(sec_diag, height=12, font=F_SMALL, wrap="word", padx=8, pady=8)
        apply_text_area_style(self.tag_diag_text)
        self.tag_diag_text.pack(fill="both", expand=True)
        self.tag_diag_text.insert(
            "1.0",
            "Hier erscheinen UID, Blöcke und Payload nach „Tag lesen“, „Tag leeren“ oder „Jetzt vom Tag lesen“.\n"
            "Nach „Tag leeren“: Tag 2–3 Sekunden vom Reader nehmen, wieder auflegen, dann prüfen.",
        )
        self.tag_diag_text.config(state="disabled")

    def _build_tab_profile(self) -> None:
        root = ttk.Frame(self.tab_profile)
        root.pack(fill="both", expand=True)
        ttk.Label(
            root,
            text="Druckparameter des gewählten Materials. Auswahl: Tab „RFID-Tag“ → Marke/Material.",
            style="Muted.TLabel",
            wraplength=900,
        ).pack(anchor="w", padx=8, pady=(8, 4))
        empty_db: dict = {"result": {"list": [], "count": 0}}
        self._filament_panel = FilamentEditorPanel(
            root,
            self.db_data if self.db_data else empty_db,
            self._on_filament_saved,
        )
        self._filament_panel.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _goto_profile_tab(self) -> None:
        self.notebook.select(self.tab_profile)
        self._sync_editor_to_selection()

    def _build_tab_database(self) -> None:
        top = ttk.Frame(self.tab_db)
        top.pack(fill="both", expand=True)
        top.columnconfigure(0, weight=1)
        top.rowconfigure(1, weight=1)

        sec = section(top, "Import — Material-Datenbank")
        sec.grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 2))
        self.db_label = ttk.Label(sec, text="Lade…", style="Muted.TLabel", wraplength=800)
        self.db_label.pack(anchor="w", pady=(0, 6))

        grid = ttk.Frame(sec)
        grid.pack(fill="x")
        actions = [
            (
                "Von Creality Cloud",
                self.sync_database,
                "Material-Datenbank von Creality Cloud herunterladen.",
            ),
            (
                "Vom Drucker (SSH)",
                self.sync_from_printer,
                "filament_database.json per SSH vom Drucker holen.",
            ),
            (
                "Zum Drucker (SSH)",
                self.upload_to_printer,
                "Aktuelle Datenbank per SSH auf den Drucker kopieren.",
            ),
            (
                "Cloud mergen",
                self.merge_cloud,
                "Cloud-Daten mit der lokalen Datenbank zusammenführen.",
            ),
            ("Datei öffnen…", self.pick_database, "Bestehende JSON-Datenbank von der Festplatte laden."),
            (
                "Slicer-Profile import…",
                self.import_slicer_profiles,
                "Orca/Creality JSON — Notizen: {\"id\",\"vendor\",\"type\",\"name\"}.",
            ),
            ("DB speichern…", self.save_database_as, "Datenbank als JSON-Datei exportieren."),
            (
                "CFS-RFID ZIP…",
                self.import_cfs_zip,
                "Backup-ZIP mit Datenbank und Einstellungen importieren.",
            ),
        ]
        for c in range(4):
            grid.columnconfigure(c, weight=1)
        for i, (text, cmd, help_txt) in enumerate(actions):
            r, c = divmod(i, 4)
            tip(
                ttk.Button(grid, text=text, command=cmd, style="Secondary.TButton"),
                help_txt,
            ).grid(row=r, column=c, sticky="ew", padx=3, pady=3)

        list_sec = section(top, "Alle Material-Profile")
        list_sec.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        self._profile_list_title = ttk.Label(
            list_sec,
            text="0 Profile — Suche filtert die Liste",
            style="Muted.TLabel",
        )
        self._profile_list_title.pack(anchor="w", pady=(0, 6))
        search_db = ttk.Frame(list_sec)
        search_db.pack(fill="x", pady=(0, 6))
        self._db_list_search_var = tk.StringVar()
        db_search_e = ttk.Entry(search_db, textvariable=self._db_list_search_var)
        db_search_e.pack(side="left", fill="x", expand=True)
        self._db_list_search_var.trace_add("write", lambda *_: self._refresh_profile_list())
        tip(
            ttk.Button(search_db, text="✕", width=3, command=lambda: self._db_list_search_var.set("")),
            "Filter zurücksetzen.",
        ).pack(side="left", padx=(6, 0))
        tree_wrap = ttk.Frame(list_sec)
        tree_wrap.pack(fill="both", expand=True)
        tree_scroll = ttk.Scrollbar(tree_wrap, orient=tk.VERTICAL)
        self._profile_tree = ttk.Treeview(
            tree_wrap,
            columns=("id", "brand", "name", "type"),
            show="headings",
            height=10,
            yscrollcommand=tree_scroll.set,
        )
        tree_scroll.config(command=self._profile_tree.yview)
        for col, title, width in (
            ("id", "ID", 72),
            ("brand", "Marke", 120),
            ("name", "Material", 220),
            ("type", "Typ", 80),
        ):
            self._profile_tree.heading(col, text=title)
            self._profile_tree.column(col, width=width, minwidth=50)
        self._profile_tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")
        self._profile_sort_col = "brand"
        self._profile_sort_asc = True
        self._profile_tree.bind("<Double-1>", self._on_profile_tree_double)

        tree_btns = ttk.Frame(list_sec)
        tree_btns.pack(fill="x", pady=(8, 0))
        tip(
            ttk.Button(
                tree_btns,
                text="Für RFID-Tag übernehmen",
                command=self._apply_profile_tree_selection,
                style="Accent.TButton",
            ),
            "Ausgewähltes Profil in Tab „RFID-Tag“ übernehmen.",
        ).pack(side="left", padx=(0, 8))
        tip(
            ttk.Button(
                tree_btns,
                text="Profil bearbeiten",
                command=self._edit_profile_tree_selection,
                style="Secondary.TButton",
            ),
            "Filament-Profil-Tab mit Auswahl öffnen.",
        ).pack(side="left")

        foot = ttk.Frame(top)
        foot.grid(row=2, column=0, sticky="ew", padx=4, pady=(0, 6))
        foot_row = ttk.Frame(foot)
        foot_row.pack(fill="x")
        ttk.Label(
            foot_row,
            text="Doppelklick = RFID-Tag · Bearbeiten: Tab „Filament-Profil“",
            style="Muted.TLabel",
        ).pack(side="left")
        tip(
            ttk.Button(
                foot_row,
                text="Drucker & SSH →",
                command=lambda: self.notebook.select(self.tab_printer),
                style="Secondary.TButton",
            ),
            "IP, SSH, DB-Vergleich und Upload im Tab „Drucker“.",
        ).pack(side="right")

    def _build_tab_printer(self) -> None:
        self._device_panel = PrinterDevicePanel(self.tab_printer, self)
        self._device_panel.pack(fill="both", expand=True)
        self._printer_dashboard = PrinterDashboardPanel(self.tab_printer, self)
        self._printer_dashboard.pack(fill="x", padx=4, pady=(0, 8))

    def _build_tab_spools(self) -> None:
        self._spool_panel = SpoolManagerPanel(self)
        self._spool_panel.pack(fill="both", expand=True)

    def _build_statusbar(self) -> None:
        self._statusbar_frame = tk.Frame(
            self,
            bg=BG_SUBTLE,
            height=52,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        self._statusbar_frame.pack(fill="x", side="bottom")
        self._statusbar_frame.pack_propagate(False)

        bar = tk.Frame(self._statusbar_frame, bg=BG_SUBTLE, padx=16, pady=10)
        bar.pack(fill="x")

        left = tk.Frame(bar, bg=BG_SUBTLE)
        left.pack(side="left", fill="x", expand=True)
        self.scard_dot = tk.Label(left, text="●", bg=BG_SUBTLE, fg=MUTED, font=(FONT, 11))
        self.scard_dot.pack(side="left", padx=(0, 10))
        self.status_label = ttk.Label(left, text="Bereit", style="Footer.TLabel")
        self.status_label.pack(side="left", anchor="w")

        foot_font = (FONT, 10)
        self.btn_log = tip(
            rounded_button(
                bar,
                "Protokoll",
                self._toggle_message_log,
                variant="secondary",
                font=foot_font,
                compact=True,
            ),
            "Meldungsverlauf ein- oder ausblenden.",
        )
        self.btn_log.pack(side="right", padx=(6, 0))

        self.btn_settings = tip(
            rounded_button(
                bar,
                "Einstellungen",
                self.open_settings,
                variant="secondary",
                font=foot_font,
                compact=True,
            ),
            "App-Einstellungen öffnen (Pfade, Auto-Lesen/Schreiben, NFC).",
        )
        self.btn_scard_help = tip(
            rounded_button(
                bar,
                "Anleitung",
                self.show_smartcard_help,
                variant="secondary",
                font=foot_font,
                compact=True,
            ),
            "Hilfe zum NFC-Reader und Windows Smartcard-Dienst.",
        )
        self.btn_scard = tip(
            rounded_button(
                bar,
                "Smartcard starten",
                self._start_smartcard_from_bar,
                variant="secondary",
                font=foot_font,
                compact=True,
            ),
            "PC/SC-Dienst starten, damit der NFC-Reader erkannt wird.",
        )
        self.btn_settings.pack(side="right", padx=(6, 0))
        self._apply_nfc_ui()

    def _build_message_area(self) -> None:
        """Protokoll (optional) — nicht dauerhaft sichtbar (war der schwarze Streifen unten)."""
        self._msg_outer = tk.Frame(self, bg=BG)
        self._log_visible = False

        self.confirm_frame = tk.Frame(self._msg_outer, bg=CONFIRM_BG, padx=14, pady=10)
        self.confirm_label = tk.Label(
            self.confirm_frame,
            text="",
            bg=CONFIRM_BG,
            fg=ON_HEADER,
            font=F_BODY,
            wraplength=900,
            justify="left",
        )
        self.confirm_label.pack(side="left", fill="x", expand=True)
        cf_btns = ttk.Frame(self.confirm_frame)
        cf_btns.pack(side="right")
        self._btn_confirm_yes = tip(
            ttk.Button(cf_btns, text="Ja", command=self._on_confirm_yes, style="Accent.TButton"),
            "Aktion bestätigen und ausführen.",
        )
        self._btn_confirm_yes.pack(side="left", padx=(0, 6))
        self._btn_confirm_no = tip(
            ttk.Button(cf_btns, text="Nein", command=self._on_confirm_no, style="Secondary.TButton"),
            "Aktion abbrechen.",
        )
        self._btn_confirm_no.pack(side="left")

        self._log_panel = tk.Frame(self, bg=BG)
        log_card = tk.Frame(
            self._log_panel,
            bg=CARD,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        log_card.pack(fill="x", padx=12, pady=(0, 4))
        ttk.Label(
            log_card,
            text="Protokoll",
            style="CardHeading.TLabel",
        ).pack(anchor="w", padx=10, pady=(6, 0))
        self.msg_log = scrolledtext.ScrolledText(
            log_card,
            height=4,
            font=F_SMALL,
            wrap="word",
        )
        apply_text_area_style(self.msg_log)
        self.msg_log.pack(fill="x", padx=10, pady=(4, 8))
        self.msg_log.config(state="disabled")
        self._confirm_yes_cb = None
        self._confirm_no_cb = None

    def _toggle_message_log(self) -> None:
        if self._log_visible:
            self._log_panel.pack_forget()
            self._log_visible = False
            self.btn_log.configure(text="Protokoll")
        else:
            self._log_panel.pack(fill="x", side="bottom", before=self._statusbar_frame)
            self._log_visible = True
            self.btn_log.configure(text="Protokoll ▾")

    def notify(self, text: str, level: str = "info") -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        icons = {"info": "ℹ", "ok": "✓", "warn": "⚠", "error": "✗"}
        line = f"[{ts}] {icons.get(level, '·')} {text}\n"
        self.msg_log.config(state="normal")
        self.msg_log.insert("end", line)
        self.msg_log.see("end")
        self.msg_log.config(state="disabled")
        self._set_status(text.replace("\n", " ")[:72], level)

    def ask_confirm(
        self,
        text: str,
        on_yes,
        on_no=None,
    ) -> None:
        """Sichtbarer Ja/Nein-Dialog (die Leiste unten war leicht zu übersehen)."""
        if messagebox.askyesno(APP_NAME, text):
            if on_yes:
                on_yes()
        elif on_no:
            on_no()

    def _on_confirm_yes(self) -> None:
        self.confirm_frame.pack_forget()
        cb = self._confirm_yes_cb
        self._confirm_yes_cb = None
        self._confirm_no_cb = None
        if cb:
            cb()

    def _on_confirm_no(self) -> None:
        self.confirm_frame.pack_forget()
        cb = self._confirm_no_cb
        self._confirm_yes_cb = None
        self._confirm_no_cb = None
        if cb:
            cb()

    def _apply_settings(self, settings: AppSettings) -> None:
        self.settings = settings
        self.settings.save(DEFAULT_SETTINGS_PATH)
        self.auto_read_var.set(settings.auto_read_tag)
        self.auto_write_var.set(settings.auto_write_tag)
        self.auto_serial_var.set(settings.auto_increment_serial)
        self.auto_sync_spool_var.set(settings.auto_sync_spool_on_tag)
        self.batch_write_var.set(settings.batch_write_mode)
        if settings.auto_increment_serial:
            self.serial_var.set(f"{self.settings.next_serial:06d}")
        self.notify("Einstellungen gespeichert", "ok")
        self._sync_creality_watcher()

    def _update_color_preview(self) -> None:
        self.color_hex = normalize_hex(self.color_hex)
        self.color_preview.config(bg=f"#{self.color_hex}", text=f"#{self.color_hex}")

    def _set_status(self, text: str, level: str = "info") -> None:
        styles = {
            "info": "Footer.TLabel",
            "ok": "FooterOk.TLabel",
            "warn": "FooterWarn.TLabel",
            "error": "FooterErr.TLabel",
        }
        if len(text) > 64:
            text = text[:61] + "…"
        self.status_label.configure(text=text, style=styles.get(level, "Footer.TLabel"))

    def _apply_nfc_ui(self) -> str:
        """Statusleiste an echten PC/SC-Stand anpassen. Gibt probe_pcsc() zurück."""
        state = probe_pcsc()
        self._scard_needs_start = state in ("service_down", "service_stuck")

        if state == "ok":
            self.scard_dot.config(fg=OK)
            self.btn_scard.config(text="Smartcard starten")
            self.btn_scard.pack_forget()
        elif state == "no_reader":
            self.scard_dot.config(fg=WARN)
            self.btn_scard.pack_forget()
        elif state == "service_stuck":
            self.scard_dot.config(fg=ERR)
            self.btn_scard.config(text="Neu starten (UAC)")
            self._pack_scard_buttons()
        else:
            self.scard_dot.config(fg=ERR)
            self.btn_scard.config(text="Smartcard starten")
            self._pack_scard_buttons()
        self.btn_scard_help.pack_forget()
        if state in ("service_stuck", "service_down"):
            self.btn_scard_help.pack(side="right", padx=(0, 8), before=self.btn_scard)
        return state

    def _pack_scard_buttons(self) -> None:
        if not self.btn_scard.winfo_ismapped():
            self.btn_scard.pack(side="right", padx=(0, 8), before=self.btn_settings)

    def _initial_nfc_check(self) -> None:
        state = self._apply_nfc_ui()
        if state == "ok":
            self.connect_reader(show_errors=False)
        elif state == "no_reader":
            self._set_status("Smartcard OK — Reader per USB verbinden", "warn")
        elif state == "service_stuck":
            self._set_status("Smartcard hängt — Tab Hilfe oder „Neu starten (UAC)“", "error")
            if not self._scard_help_shown:
                self._scard_help_shown = True
                self.notify(
                    "Smartcard-Dienst hängt. Tab „Hilfe“ oder unten „Neu starten (UAC)“.",
                    "warn",
                )
        else:
            self._set_status("Smartcard-Dienst aus", "error")

    def show_smartcard_help(self) -> None:
        self.notebook.select(self.tab_help)
        self.notify("Smartcard-Anleitung — Tab „Hilfe“ → Programm-Anleitung", "info")

    def _start_smartcard_from_bar(self) -> None:
        self.start_smartcard_service()

    def _nfc_error_message(self, exc: NfcReaderError) -> tuple[str, str, bool]:
        """Returns (short status text, dialog text, offer scard action)."""
        if str(exc) == "SMARTCARD_STOPPED":
            state = probe_pcsc()
            if state == "service_stuck":
                return ("Smartcard hängt — neu starten", scard_status_message(state), True)
            return ("Smartcard-Dienst aus", scard_status_message(state), True)
        msg = str(exc)
        low = msg.lower()
        if "block " in low and "lesen fehlgeschlagen" in low:
            return (msg.split("\n", 1)[0][:64], msg, False)
        if "80100069" in msg or "entfernt wurde" in low or "removed card" in low:
            return (
                "Kein Tag auf dem Reader",
                "Der NFC-Reader ist angeschlossen.\n\n"
                "Legen Sie einen MIFARE-Classic-1K-Tag (25 mm) flach auf die Lesefläche "
                "und klicken Sie „Reader verbinden“ oder „Tag lesen“.\n\n"
                "Ohne Tag auf dem Reader: nach App-Update „Reader verbinden“ erneut versuchen.",
                False,
            )
        return (msg[:64], msg, False)

    def show_alert_dialog(self, text: str, level: str = "error", title: str | None = None) -> None:
        t = title or APP_NAME
        if level == "error":
            messagebox.showerror(t, text, parent=self)
        elif level == "warn":
            messagebox.showwarning(t, text, parent=self)
        else:
            messagebox.showinfo(t, text, parent=self)

    def _ensure_reader_for_tag(self, *, show_dialog: bool = True) -> bool:
        """PC/SC prüfen, bevor Tag gelesen/geschrieben wird."""
        state = probe_pcsc()
        if state == "ok":
            return True
        if not show_dialog:
            return False
        msg = scard_status_message(state)
        if state == "service_down":
            self._set_status("Smartcard-Dienst aus", "error")
            self.ask_confirm(msg + "\n\nJetzt starten?", self.start_smartcard_service)
        elif state == "service_stuck":
            self._set_status("Smartcard hängt", "error")
            self.ask_confirm(msg + "\n\nJetzt neu starten?", self.start_smartcard_service)
        else:
            self._set_status(msg.split("\n")[0][:64], "warn")
            self.notify(msg, "warn")
            self.show_alert_dialog(
                msg + "\n\nDanach im RFID-Tab „Reader verbinden“.",
                "warn",
                title="NFC-Reader",
            )
        return False

    def _tag_finished(
        self,
        title: str,
        message: str,
        level: str = "ok",
        *,
        popup: bool = True,
    ) -> None:
        """RFID-Vorgang abgeschlossen — Status, Protokoll und sichtbarer Dialog."""
        self.notify(message, level)
        if popup:
            self.show_alert_dialog(message, level, title=title)

    def _report_tag_error(self, exc: Exception, *, silent: bool = False) -> None:
        if isinstance(exc, NfcReaderError):
            short, detail, offer = self._nfc_error_message(exc)
            self._set_status(short, "error")
            if silent:
                return
            self.notify(detail, "error")
            if offer:
                self.ask_confirm(detail + "\n\nAktion ausführen?", self.start_smartcard_service)
            else:
                self.show_alert_dialog(detail, "error", title="NFC")
            return
        msg = str(exc) or "Unbekannter Fehler"
        self._set_status(msg[:70], "error")
        if silent:
            return
        self.notify(msg, "error")
        self.show_alert_dialog(msg, "error", title="NFC")

    # ── Settings & status helpers ───────────────────────────────────

    def _sync_auto_flags(self) -> None:
        self.settings.auto_read_tag = self.auto_read_var.get()
        self.settings.auto_write_tag = self.auto_write_var.get()
        self.settings.auto_sync_spool_on_tag = self.auto_sync_spool_var.get()
        self.settings.save(DEFAULT_SETTINGS_PATH)

    def _sync_batch_flag(self) -> None:
        self.settings.batch_write_mode = self.batch_write_var.get()
        self.settings.save(DEFAULT_SETTINGS_PATH)

    def _clear_search(self) -> None:
        self.search_var.set("")
        self._apply_material_filter()

    def _apply_material_filter(self) -> None:
        q = self.search_var.get().strip().lower()
        if q:
            self._filtered_profiles = [
                p
                for p in self.profiles
                if q in f"{p.brand} {p.name} {p.filament_id} {p.material_type}".lower()
            ]
        else:
            self._filtered_profiles = list(self.profiles)
        brands = sorted({p.brand for p in self._filtered_profiles})
        self.brand_combo["values"] = brands
        if brands:
            if self.brand_var.get() not in brands:
                self.brand_var.set(brands[0])
            self._on_brand_change()
        else:
            self.material_combo["values"] = []
            self.material_var.set("")

    def _on_serial_mode_change(self) -> None:
        self.settings.auto_increment_serial = self.auto_serial_var.get()
        if self.settings.auto_increment_serial:
            self.serial_var.set(self.settings.next_serial_str())
        self.settings.save(DEFAULT_SETTINGS_PATH)

    def _sync_creality_watcher(self) -> None:
        from creality_nfc.creality_watch import start_watcher_detached, watcher_is_running

        if self.settings.launch_with_creality_print:
            if start_watcher_detached():
                self._set_status("Creality-Wächter gestartet", "ok")
        elif watcher_is_running():
            self._set_status(
                "Creality-Wächter läuft noch — nach Deaktivieren ggf. PC neu starten",
                "warn",
            )

    def _save_settings(self) -> None:
        self.settings.save(DEFAULT_SETTINGS_PATH)

    def _update_db_label(self) -> None:
        n = len(self.profiles)
        if self._demo_mode:
            txt = f"⚠  {n} Demo-Materialien — bitte DB laden"
            self.db_label.config(text=txt)
            self.db_badge.config(text=txt, fg=ON_HEADER_WARN, bg=HEADER_SURFACE)
            return
        labels = {
            "cloud": "Creality Cloud",
            "printer": "Drucker",
            "file": "Datei",
            "merged": "gemergt",
            "local": "lokal",
        }
        src = labels.get(self._db_source, "?")
        name = self.db_path.name if self.db_path else "?"
        txt = f"✓  {n} Materialien  ·  {src}  ·  {name}"
        self.db_label.config(text=txt)
        self.db_badge.config(
            text=f"{n} Profile  ·  {src}",
            fg=ON_HEADER_OK,
            bg=HEADER_SURFACE,
        )
        self._refresh_profile_list()

    # ── Database ────────────────────────────────────────────────────

    def _on_printer_change(self, _event=None) -> None:
        self._load_materials()

    def _load_materials(self) -> None:
        DATA_DIR.mkdir(exist_ok=True)
        path = db_path_for_printer(DATA_DIR, self.printer_var.get())
        if path.is_file():
            try:
                self.db_data = load_database_raw(path)
                self.profiles = profiles_from_db(self.db_data)
                self.db_path = path
                self._demo_mode = False
                self._db_source = "local"
            except Exception:
                self._use_demo()
        else:
            legacy = [p for p in DATA_DIR.glob("*.json") if p.name not in SKIP_DATA_JSON]
            if legacy:
                try:
                    self.db_path = legacy[0]
                    self.db_data = load_database_raw(self.db_path)
                    self.profiles = profiles_from_db(self.db_data)
                    self._demo_mode = False
                    self._db_source = "local"
                except Exception:
                    self._use_demo()
            else:
                self._use_demo()
        self._refresh_combos()
        self._update_db_label()
        self._refresh_profile_list()
        self._sync_filament_panel_db()
        self._sync_editor_to_selection()

    def _use_demo(self) -> None:
        self.profiles = builtin_profiles()
        self.db_data = None
        self.db_path = None
        self._demo_mode = True
        self._db_source = "demo"

    def _apply_database(self, data: dict, source: str) -> None:
        path = db_path_for_printer(DATA_DIR, self.printer_var.get().strip())
        save_database(path, data)
        self.db_data = data
        self.db_path = path
        self.profiles = profiles_from_db(data)
        self._demo_mode = False
        self._db_source = source
        self._refresh_combos()
        self._update_db_label()
        self._refresh_profile_list()
        self._sync_filament_panel_db()
        self._sync_editor_to_selection()

    def _profile_sort_key(self, profile: FilamentProfile):
        col = getattr(self, "_profile_sort_col", "brand")
        if col == "id":
            return profile.filament_id
        if col == "name":
            return profile.name.lower()
        if col == "type":
            return profile.material_type.lower()
        return profile.brand.lower()

    def _toggle_profile_sort(self, col: str) -> None:
        if self._profile_sort_col == col:
            self._profile_sort_asc = not self._profile_sort_asc
        else:
            self._profile_sort_col = col
            self._profile_sort_asc = True
        self._refresh_profile_list()

    def _update_profile_tree_headings(self) -> None:
        titles = {
            "id": "ID",
            "brand": "Marke",
            "name": "Material",
            "type": "Typ",
        }
        for col, base in titles.items():
            text = base
            if col == self._profile_sort_col:
                text += " ▲" if self._profile_sort_asc else " ▼"
            self._profile_tree.heading(col, text=text)

    def _refresh_profile_list(self) -> None:
        if not hasattr(self, "_profile_tree"):
            return
        q = self._db_list_search_var.get().strip().lower()
        self._profile_tree.delete(*self._profile_tree.get_children())
        shown = 0
        rows = sorted(self.profiles, key=self._profile_sort_key, reverse=not self._profile_sort_asc)
        for p in rows:
            hay = f"{p.brand} {p.name} {p.filament_id} {p.material_type}".lower()
            if q and q not in hay:
                continue
            self._profile_tree.insert(
                "",
                tk.END,
                iid=f"{p.filament_id}|{p.brand}|{p.name}",
                values=(p.filament_id, p.brand, p.name, p.material_type),
            )
            shown += 1
        total = len(self.profiles)
        if self._demo_mode:
            self._profile_list_title.config(
                text=f"⚠ Demo: {shown} von {total} — bitte echte DB laden (Cloud/Drucker)"
            )
        elif q:
            self._profile_list_title.config(text=f"{shown} von {total} Profilen (gefiltert)")
        else:
            self._profile_list_title.config(text=f"Alle {total} Material-Profile in der Datenbank")
        self._update_profile_tree_headings()

    def _profile_from_tree_selection(self) -> FilamentProfile | None:
        sel = self._profile_tree.selection()
        if not sel:
            return None
        iid = sel[0]
        parts = str(iid).split("|", 2)
        if len(parts) != 3:
            return None
        fid, brand, name = parts
        for p in self.profiles:
            if p.filament_id == fid and p.brand == brand and p.name == name:
                return p
        return None

    def _select_profile_in_ui(self, profile: FilamentProfile) -> None:
        self.brand_var.set(profile.brand)
        self._on_brand_change()
        label = self._profile_combo_label(profile)
        if label in self.material_combo["values"]:
            self.material_var.set(label)
        else:
            self._material_combo_map[label] = (profile.filament_id, profile.brand, profile.name)
            vals = list(self.material_combo["values"]) + [label]
            self.material_combo["values"] = vals
            self.material_var.set(label)
        self._on_material_selected()

    def _apply_profile_tree_selection(self) -> None:
        profile = self._profile_from_tree_selection()
        if not profile:
            self.notify("Bitte zuerst ein Profil in der Liste auswählen.", "warn")
            return
        self._select_profile_in_ui(profile)
        self.notebook.select(self.tab_tag)
        self.notify(f"RFID-Tag: {profile.brand} — {profile.name}", "ok")

    def _edit_profile_tree_selection(self) -> None:
        profile = self._profile_from_tree_selection()
        if not profile:
            self.notify("Bitte zuerst ein Profil in der Liste auswählen.", "warn")
            return
        self._select_profile_in_ui(profile)
        self._goto_profile_tab()

    def _on_profile_tree_double(self, event=None) -> None:
        if event is None:
            self._apply_profile_tree_selection()
            return
        region = self._profile_tree.identify_region(event.x, event.y)
        col = self._profile_tree.identify_column(event.x)
        col_key = {"#1": "id", "#2": "brand", "#3": "name", "#4": "type"}.get(col)
        if region == "heading" and col_key:
            self._toggle_profile_sort(col_key)
            return
        if region == "cell" and col_key == "type":
            self._toggle_profile_sort("type")
            return
        self._apply_profile_tree_selection()

    def _run_bg_job(self, label: str, work, *, on_ok=None) -> None:
        """Netzwerk/SSH im Hintergrund — UI bleibt reaktionsfähig."""
        if self._bg_job_running:
            self.notify("Ein Vorgang läuft bereits — bitte warten.", "warn")
            return
        self._bg_job_running = True
        self._set_status(f"{label}…", "info")
        self.notify(f"{label}… (kann 1–2 Minuten dauern)", "info")

        def runner() -> None:
            err: Exception | None = None
            result = None
            try:
                result = work()
            except Exception as exc:
                err = exc
            self.after(0, lambda: self._finish_bg_job(label, err, result, on_ok))

        threading.Thread(target=runner, daemon=True).start()

    def _finish_bg_job(self, label: str, err: Exception | None, result, on_ok) -> None:
        self._bg_job_running = False
        if err:
            self._set_status(f"{label} fehlgeschlagen", "error")
            self.notify(str(err), "error")
            messagebox.showerror(APP_NAME, f"{label}\n\n{err}")
            return
        if on_ok:
            on_ok(result)
        else:
            self._set_status(f"{label} OK", "ok")
            self.notify(f"{label} abgeschlossen.", "ok")

    def sync_database(self) -> None:
        printer = self.printer_var.get().strip() or "K2 Pro"

        def work():
            return download_material_database(printer)

        def on_ok(data: dict) -> None:
            if self.db_data and self.db_data.get("result", {}).get("list"):
                merged = merge_databases(self.db_data, data, prefer="cloud")
                added, updated, total, skipped = merge_stats(self.db_data, data)
                self._apply_database(merged, "cloud")
                msg = f"{total} Profile (Cloud gemergt)\n+{added} neu, {updated} aktualisiert."
                if skipped:
                    msg += f"\n{skipped} geschützte Profile nicht überschrieben."
            else:
                self._apply_database(data, "cloud")
                n = len(self.profiles)
                msg = f"{n} Material-Profile von Creality Cloud geladen."
            self._set_status("Cloud OK", "ok")
            self.notify(msg, "ok")
            messagebox.showinfo(APP_NAME, msg + f"\n\n(Drucker: {printer})")

        self._run_bg_job(f"Creality Cloud ({printer})", work, on_ok=on_ok)

    def merge_cloud(self) -> None:
        if not self._ensure_db():
            return
        printer = self.printer_var.get().strip() or "K2 Pro"
        local_db = self.db_data

        def work():
            incoming = download_material_database(printer)
            prefer = self.settings.merge_prefer
            merged = merge_databases(local_db, incoming, prefer=prefer)  # type: ignore[arg-type]
            added, updated, total, skipped = merge_stats(local_db, incoming)  # type: ignore[arg-type]
            return merged, added, updated, total, skipped

        def on_ok(payload) -> None:
            merged, added, updated, total, skipped = payload
            self._apply_database(merged, "merged")
            self._set_status(f"Merge OK — {total} Profile", "ok")
            extra = f"\n{skipped} geschützt (nicht überschrieben)." if skipped else ""
            self.notify(f"+{added} neu, {updated} aktualisiert. Gesamt: {total}.{extra}", "ok")
            messagebox.showinfo(
                APP_NAME,
                f"Cloud mit lokaler DB zusammengeführt.\n\n"
                f"+{added} neu\n{updated} aktualisiert\nGesamt: {total} Profile{extra}",
            )

        self._run_bg_job(f"Cloud mergen ({printer})", work, on_ok=on_ok)

    def _ssh_credentials(self, printer: str) -> tuple[str, str] | None:
        from creality_nfc.printer_ssh import default_password, normalize_host

        host = normalize_host(self.ssh_host_var.get())
        if not host:
            msg = (
                "Bitte Drucker-IP eintragen\n"
                "(Tab „Material-Datenbank“ unten oder „RFID-Tag“)."
            )
            self.notify(msg.replace("\n", " "), "warn")
            messagebox.showwarning(APP_NAME, msg)
            return None
        password = self.ssh_pass_var.get() or default_password(printer)
        try:
            save_settings(host, password, printer)
        except Exception as exc:
            self.notify(f"Drucker-Einstellungen nicht gespeichert: {exc}", "warn")
        return host, password

    def _run_ssh_job(self, label: str, work, *, on_ok=None) -> None:
        printer = self.printer_var.get().strip()
        creds = self._ssh_credentials(printer)
        if not creds:
            return
        host, password = creds

        def work_wrap():
            if not printer_reachable(host, 22):
                raise RuntimeError(
                    f"{host}: Port 22 nicht erreichbar.\n"
                    "IP prüfen, Drucker eingeschaltet, Root/SSH am K2 aktivieren."
                )
            return work(host, password, printer)

        self._run_bg_job(f"{label} → {host}", work_wrap, on_ok=on_ok)

    def sync_from_printer(self) -> None:
        def work(host: str, password: str, printer: str):
            return download_database_from_printer(host, password, printer)

        def on_ok(data: dict) -> None:
            if self.db_data and self.db_data.get("result", {}).get("list"):
                merged = merge_databases(self.db_data, data, prefer="cloud")
                added, updated, total, skipped = merge_stats(self.db_data, data)
                self._apply_database(merged, "printer")
                msg = f"{total} Profile (vom Drucker gemergt)\n+{added} neu, {updated} aktualisiert."
                if skipped:
                    msg += f"\n{skipped} geschützte Profile nicht überschrieben."
            else:
                self._apply_database(data, "printer")
                msg = f"{len(self.profiles)} Material-Profile vom Drucker geladen."
            self._set_status("Drucker-DB OK", "ok")
            self.notify(msg, "ok")
            messagebox.showinfo(APP_NAME, msg)

        self._run_ssh_job("Vom Drucker laden", work, on_ok=on_ok)

    def upload_to_printer(self) -> None:
        if not self.db_data:
            self.notify("Zuerst Material-DB laden.", "warn")
            messagebox.showwarning(
                APP_NAME,
                "Zuerst eine Material-Datenbank laden\n"
                "(z. B. „Vom Drucker“ oder „Datei öffnen…“).",
            )
            return
        printer = self.printer_var.get().strip()
        creds = self._ssh_credentials(printer)
        if not creds:
            return
        host, _password = creds

        if not messagebox.askyesno(
            APP_NAME,
            f"Material-Datenbank auf {host} schreiben?\n\n"
            "Danach am besten: „Options zum Drucker“ und „Drucker neu starten“ "
            "im Dashboard unten.",
        ):
            self.notify("Upload abgebrochen.", "info")
            return

        def work(host: str, password: str, printer: str) -> None:
            upload_database_to_printer(host, password, printer, self.db_data)

        def on_ok(_result) -> None:
            self._save_db()
            self._set_status("Upload OK", "ok")
            self.notify(
                "material_database.json auf dem Drucker geschrieben.\n"
                "Optional: „Options zum Drucker“ + „Drucker neu starten“.",
                "ok",
            )
            messagebox.showinfo(
                APP_NAME,
                "Datenbank auf dem Drucker gespeichert.\n"
                "Drucker neu starten, damit die UI die Profile lädt.",
            )

        self._run_ssh_job("Zum Drucker senden", work, on_ok=on_ok)

    def pick_database(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json"), ("Alle", "*.*")])
        if not path:
            return
        try:
            self._apply_database(load_database_raw(Path(path)), "file")
            self.notify(f"{len(self.profiles)} Profile geladen.")
        except Exception as exc:
            self.notify(str(exc), "error")

    def import_slicer_profiles(self) -> None:
        """OrcaSlicer/Creality-Print Filament-JSONs in die Material-DB."""
        if not self._ensure_db():
            return
        paths: list[Path] = []
        picked = filedialog.askopenfilenames(
            title="Slicer-Filament-Profile (JSON)",
            filetypes=[("JSON", "*.json"), ("Alle Dateien", "*.*")],
        )
        if picked:
            paths = [Path(p) for p in picked]
        else:
            folder = filedialog.askdirectory(
                title="Ordner mit Filament-JSONs (Orca user/filament …)",
            )
            if folder:
                paths = list(Path(folder).rglob("*.json"))
        if not paths:
            return
        profiles = collect_slicer_profiles_from_paths(paths)
        if not profiles:
            messagebox.showwarning(
                APP_NAME,
                "Keine Filament-Profile erkannt.\n\n"
                "In OrcaSlicer unter Filament → Notizen z. B.:\n"
                '{"id":"06099","vendor":"ELEGOO","type":"PETG","name":"Fast PETG"}',
                parent=self,
            )
            return
        template = None
        if self.db_data:
            lst = self.db_data.get("result", {}).get("list", [])
            if lst:
                template = lst[0]
        data, added, updated = merge_slicer_profiles_into_db(
            self.db_data or {"result": {"list": [], "count": 0}},
            profiles,
            template_item=template,
        )
        self._apply_database(data, "slicer")
        messagebox.showinfo(
            APP_NAME,
            f"{len(profiles)} Slicer-Profile verarbeitet.\n\n"
            f"Neu: {added}\nAktualisiert: {updated}\n\n"
            "Optional: „Zum Drucker (SSH)“ — Drucker neu starten.",
            parent=self,
        )

    def save_database_as(self) -> None:
        if not self.db_data:
            self.notify("Keine DB geladen.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("JSON", "*.json")], initialfile="material_database.json"
        )
        if path:
            save_database(Path(path), self.db_data)
            self.notify(path)

    def export_options(self) -> None:
        if not self.db_data:
            self.notify("Zuerst DB laden.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json", initialfile="material_options.json", filetypes=[("JSON", "*.json")]
        )
        if path:
            export_material_options(self.db_data, Path(path))
            self.notify(path)

    def _ensure_db(self) -> bool:
        if self.db_data is None:
            msg = (
                "Noch keine Material-Datenbank geladen.\n\n"
                "Zuerst „Von Creality Cloud“ oder „Datei öffnen…“ nutzen,\n"
                "dann erneut „Cloud mergen“."
            )
            self.notify("Zuerst Datenbank laden (Cloud oder Datei).", "warn")
            messagebox.showwarning(APP_NAME, msg)
            self.notebook.select(self.tab_db)
            return False
        return True

    def _on_filament_saved(self, db_data: dict) -> None:
        self.db_data = db_data
        self._save_db()
        self.profiles = profiles_from_db(self.db_data)
        self._refresh_combos()
        self._update_db_label()
        self._refresh_profile_list()
        self._sync_editor_to_selection()

    def _sync_filament_panel_db(self) -> None:
        if hasattr(self, "_filament_panel") and self.db_data:
            self._filament_panel.set_db_data(self.db_data)

    def add_filament(self) -> None:
        if not self._ensure_db():
            return
        self.notebook.select(self.tab_profile)
        profile = self._selected_profile()
        template = (
            find_item(
                self.db_data,
                profile.filament_id,
                brand=profile.brand,
                name=profile.name,
            )
            if profile and self.db_data
            else None
        )
        self._sync_filament_panel_db()
        self._filament_panel.load_new(template_item=template)

    def edit_filament(self) -> None:
        if not self._ensure_db():
            return
        profile = self._selected_profile()
        if not profile:
            self.notify("Bitte zuerst Marke und Material im RFID-Tab wählen.", "warn")
            self.notebook.select(self.tab_tag)
            return
        self._goto_profile_tab()

    def _save_db(self) -> None:
        if self.db_data and self.db_path:
            save_database(self.db_path, self.db_data)

    def _refresh_combos(self) -> None:
        self._apply_material_filter()

    @staticmethod
    def _profile_combo_label(profile: FilamentProfile) -> str:
        return f"{profile.name}  ·  ID {profile.filament_id}"

    def _profiles_for_brand(self, brand: str) -> list[FilamentProfile]:
        return [p for p in self._filtered_profiles if p.brand == brand]

    def _on_brand_change(self, _event=None) -> None:
        brand = self.brand_var.get()
        profs = self._profiles_for_brand(brand)
        labels = [self._profile_combo_label(p) for p in profs]
        self._material_combo_map = {
            label: (p.filament_id, p.brand, p.name) for label, p in zip(labels, profs)
        }
        self.material_combo["values"] = labels
        if not labels:
            self.material_var.set("")
            self._current_profile = ("", "", "")
            self._sync_editor_to_selection()
            return
        keep = self._current_profile
        pick = labels[0]
        if keep[0]:
            for label, key in self._material_combo_map.items():
                if key == keep:
                    pick = label
                    break
        elif self.material_var.get() in self._material_combo_map:
            pick = self.material_var.get()
        self.material_var.set(pick)
        self._on_material_selected()

    def _on_material_selected(self, _event=None) -> None:
        label = self.material_var.get()
        self._current_profile = self._material_combo_map.get(label, ("", "", ""))
        self._sync_editor_to_selection()

    def _update_filament_selection_label(self) -> None:
        profile = self._selected_profile()
        if profile:
            text = (
                f"ID {profile.filament_id}  ·  {profile.brand} — {profile.name}  ·  "
                f"{profile.material_type}"
            )
            if self.db_data:
                dup = len(list_items_for_id(self.db_data, profile.filament_id))
                if dup > 1:
                    text += f"  ·  Hinweis: {dup} DB-Einträge mit dieser ID"
            self.selected_profile_var.set(text)
        else:
            self.selected_profile_var.set("Kein Material gewählt — Suche oder Marke/Material oben wählen")

    def _sync_editor_to_selection(self) -> None:
        self._update_filament_selection_label()
        if not hasattr(self, "_filament_panel"):
            return
        profile = self._selected_profile()
        if not profile or not self.db_data:
            return
        self._sync_filament_panel_db()
        self._filament_panel.load_edit(profile)

    def _goto_db_tab(self) -> None:
        self.notebook.select(self.tab_db)

    # ── Spools ──────────────────────────────────────────────────────

    def _refresh_spool_combo(self) -> None:
        items = [("", "— keine —")]
        for s in self.inventory.sorted_spools():
            items.append((s.id, s.display_name()))
        self._spool_map = {label: sid for sid, label in items if sid}
        self.spool_combo["values"] = [label for _, label in items]
        if self._active_spool_id:
            sp = self.inventory.get(self._active_spool_id)
            if sp:
                self.spool_var.set(sp.display_name())
                return
        self.spool_var.set("— keine —")

    def _on_spool_selected(self, _event=None) -> None:
        sid = self._spool_map.get(self.spool_var.get())
        if sid:
            sp = self.inventory.get(sid)
            if sp:
                self.apply_spool(sp)

    def _fill_spool_from_tag(self, sp: Spool, uid: str, profile: FilamentProfile, serial: str) -> None:
        sp.tag_uid = uid
        sp.serial = serial
        sp.color_hex = self.color_hex
        sp.weight = self.weight_var.get()
        sp.brand = profile.brand
        sp.material_name = profile.name
        sp.filament_id = profile.filament_id
        sp.printer = self.printer_var.get().strip()
        if not sp.label or sp.label in ("Neue Spule", "Spule"):
            sp.label = f"{profile.brand} — {profile.name}".strip(" —") or profile.name

    def _sync_spool_after_tag(
        self,
        uid: str,
        profile: FilamentProfile,
        serial: str,
    ) -> str | None:
        """Meine Spulen nach Tag-Schreiben anlegen/aktualisieren. Kurztext für Meldung."""
        if not self.settings.auto_sync_spool_on_tag:
            return None

        existing = self.inventory.find_by_uid(uid)
        if existing:
            self._fill_spool_from_tag(existing, uid, profile, serial)
            self.inventory.update(existing)
            self.apply_spool(existing)
            self._spool_panel.reload()
            self._spool_panel.select_spool(existing.id)
            return f"Spule „{existing.label}“ aktualisiert"

        active = self.inventory.get(self._active_spool_id) if self._active_spool_id else None
        if active and not active.tag_uid:
            self._fill_spool_from_tag(active, uid, profile, serial)
            self.inventory.update(active)
            self.apply_spool(active)
            self._spool_panel.reload()
            self._spool_panel.select_spool(active.id)
            return f"Spule „{active.label}“ mit Tag verknüpft"

        sp = Spool(
            id=SpoolInventory.new_id(),
            label=f"{profile.brand} — {profile.name}"[:80],
            brand=profile.brand,
            material_name=profile.name,
            filament_id=profile.filament_id,
            color_hex=self.color_hex,
            weight=self.weight_var.get(),
            printer=self.printer_var.get().strip(),
            serial=serial,
            tag_uid=uid,
        )
        self.inventory.add(sp)
        self.apply_spool(sp)
        self._spool_panel.reload()
        self._spool_panel.select_spool(sp.id)
        return f"Spule „{sp.label}“ neu angelegt"

    def spool_from_form(self) -> Spool:
        profile = self._selected_profile()
        uid = self.uid_label.cget("text").strip()
        return Spool(
            id=self._active_spool_id or SpoolInventory.new_id(),
            label=profile.name if profile else "Neue Spule",
            brand=profile.brand if profile else self.brand_var.get(),
            material_name=profile.name if profile else self.material_var.get(),
            filament_id=profile.filament_id if profile else "",
            color_hex=self.color_hex,
            weight=self.weight_var.get(),
            printer=self.printer_var.get().strip(),
            serial=self.serial_var.get().strip() or "000001",
            tag_uid="" if uid == "—" else uid,
        )

    def _prefill_form_from_spool_for_write(self, spool: Spool) -> None:
        """RFID-Formular für Schreiben befüllen, ohne die Tag-leer-Anzeige oben zu überschreiben."""
        self._apply_spool_rfid_fields(spool)

    def _prompt_select_material_for_write(self) -> None:
        self._set_status("Kein Material gewählt", "warn")
        self.notify(
            "Bitte Marke und Material wählen (Abschnitt „Filament für den Tag“).",
            "warn",
        )
        hint = (
            "Im RFID-Tab nach unten zu „Filament für den Tag“ scrollen,\n"
            "Marke und Material auswählen — darunter muss eine ID-Zeile erscheinen.\n\n"
            "Oder: Tab „Meine Spulen“ → Spule wählen → „→ RFID-Tab“ "
            "(Spule braucht eine Filament-ID oder passenden DB-Eintrag).\n\n"
            "Suchfeld im RFID-Tab leeren, falls es noch Text enthält.\n\n"
            "Dann erneut „Tag schreiben“ (Tag auf dem Reader lassen)."
        )
        messagebox.showwarning(
            APP_NAME,
            f"Kein Filament für den Tag gewählt.\n\n{hint}",
            parent=self,
        )

    def apply_spool(self, spool: Spool) -> None:
        self._active_spool_id = spool.id
        self._refresh_spool_combo()
        self.spool_var.set(spool.display_name())
        self._apply_spool_rfid_fields(spool)
        if spool.color_hex:
            self._color_from_user = False
        uid = (spool.tag_uid or self.uid_label.cget("text") or "").strip()
        self._show_tag_identity(uid, spool, apply_form=False)
        prof = self._selected_profile() or self._profile_for_spool(spool)
        if prof:
            self._set_status(f"Spule: {spool.label} — {prof.name}", "ok")
        elif spool.filament_id:
            self._set_status(
                f"Spule: {spool.label} — ID {spool.filament_id} (Tag-Schreiben möglich)",
                "ok",
            )
        else:
            self._set_status(f"Spule: {spool.label}", "ok")

    def apply_cfs_slot(self, slot: CfsSlotInfo) -> None:
        """Material aus CFS-Slot (Tab Drucker) in RFID-Formular übernehmen."""
        self.notebook.select(self.tab_tag)
        if slot.vendor:
            brands = list(self.brand_combo["values"])
            if slot.vendor not in brands:
                self.brand_combo["values"] = tuple(brands) + (slot.vendor,)
            self.brand_var.set(slot.vendor)
            self._on_brand_change()
        if slot.name and slot.name not in ("?", "—"):
            names = list(self.material_combo["values"])
            if slot.name not in names:
                self.material_combo["values"] = tuple(names) + (slot.name,)
            self.material_var.set(slot.name)
        fid = match_profile_id(
            self.profiles,
            vendor=slot.vendor,
            name=slot.name,
            rfid_id=slot.rfid_id,
        )
        if fid:
            self._select_profile_by_id(fid, brand=slot.vendor, name=slot.name)
        if slot.color_hex:
            self.color_hex = normalize_hex(slot.color_hex)
            self._update_color_preview()
        self._sync_editor_to_selection()
        msg = f"Slot {slot.label}: {slot.display}"
        if fid:
            msg += f" → Profil ID {fid}"
        else:
            msg += " — kein exaktes DB-Profil, bitte Material prüfen"
        self._set_status(msg, "ok" if fid else "warn")
        self.notify(msg, "ok" if fid else "warn")
        sp = find_spool_for_slot(self.inventory, slot)
        if sp:
            self.apply_spool(sp)

    def bind_cfs_slot_dialog(self, slot_index: int, slot: CfsSlotInfo) -> None:
        """CFS-Slot mit Spule aus „Meine Spulen“ verknüpfen."""
        from ui.dialog_theme import prepare_toplevel

        dlg = tk.Toplevel(self)
        dlg.title(f"CFS {slot_label(slot_index)} — Spule zuweisen")
        prepare_toplevel(dlg, self, width=420, height=280)

        ttk.Label(
            dlg,
            text=f"Slot {slot_label(slot_index)}: {slot.display}\n"
            "Welche Spule aus „Meine Spulen“ steckt hier?",
            wraplength=380,
        ).pack(anchor="w", padx=12, pady=(12, 8))

        choices = [("", "— Spule wählen —")]
        for s in self.inventory.sorted_spools():
            choices.append((s.id, s.display_name()))
        id_map = {label: sid for sid, label in choices if sid}
        var = tk.StringVar()
        matched = find_spool_for_slot(self.inventory, slot)
        if matched:
            var.set(matched.display_name())
        combo = ttk.Combobox(dlg, textvariable=var, values=[l for _, l in choices], state="readonly")
        combo.pack(fill="x", padx=12, pady=4)

        def _auto() -> None:
            sp = find_spool_for_slot(self.inventory, slot)
            if not sp:
                self.notify(
                    "Keine passende Spule gefunden — bitte manuell wählen oder neue Spule anlegen.",
                    "warn",
                )
                return
            bind_slot(self.inventory, sp.id, slot_index)
            self._spool_panel.reload()
            if hasattr(self, "_printer_device_panel"):
                self._printer_device_panel.cfs_dashboard.set_inventory(self.inventory)
            self.notify(f"Slot {slot_label(slot_index)} → „{sp.label}“", "ok")
            dlg.destroy()

        def _save() -> None:
            sid = id_map.get(var.get())
            if not sid:
                self.notify("Bitte eine Spule wählen.", "warn")
                return
            bind_slot(self.inventory, sid, slot_index)
            self._spool_panel.reload()
            if hasattr(self, "_printer_device_panel"):
                self._printer_device_panel.cfs_dashboard.set_inventory(self.inventory)
            sp = self.inventory.get(sid)
            self.notify(f"Slot {slot_label(slot_index)} → „{sp.label if sp else sid}“", "ok")
            dlg.destroy()

        row = ttk.Frame(dlg)
        row.pack(fill="x", padx=12, pady=12)
        ttk.Button(row, text="Automatisch", command=_auto, style="Secondary.TButton").pack(
            side="left", padx=(0, 6)
        )
        ttk.Button(row, text="Zuweisen", command=_save, style="Accent.TButton").pack(side="right")

    def _gcode_entry_for_name(self, state: dict, filename: str) -> dict | None:
        if not filename:
            return None
        name = filename.replace("\\", "/").rsplit("/", 1)[-1].lower()
        for entry in parse_gcode_files(state):
            en = str(entry.get("name") or "").lower()
            if en == name or name in en:
                return entry
        return None

    def on_print_job_finished(
        self,
        active_slot: int | None,
        filename: str,
        printer_state: dict | None = None,
        *,
        manual: bool = False,
    ) -> None:
        """Nach Druckende: Verbrauch pro G-Code-Farbe/Slot von verknüpften Spulen abziehen."""
        fname = (filename or "").strip()
        if not manual:
            if not self.settings.prompt_deduct_after_print:
                return
            if self._post_print_prompted:
                return
            if fname and fname == self._post_print_deduct_file:
                return

        def _prepare_then_ask() -> None:
            state = dict(printer_state or {})
            try:
                conn = None
                if hasattr(self, "_printer_device_panel"):
                    conn = getattr(self._printer_device_panel, "_conn", None)
                fresh = refresh_state_for_filament_usage(conn)
                for key in (
                    "retGcodeFileInfo2",
                    "retGcodeFileInfo",
                    "retGcodeFileInfo3",
                    "printFileName",
                    "print_file_name",
                    "boxsInfo",
                    "cfsConnect",
                ):
                    if key in fresh:
                        state[key] = fresh[key]
                entry = self._gcode_entry_for_name(state, fname)
                host = (self.ssh_host_var.get() or "").strip() if hasattr(self, "ssh_host_var") else ""
                if entry and host:
                    from creality_nfc.printer_ssh import default_password

                    printer_name = (
                        self.printer_var.get().strip() if hasattr(self, "printer_var") else "K2 Pro"
                    )
                    password = self.ssh_pass_var.get() or default_password(printer_name)
                    if password:
                        cache_gcode_from_printer(host, password, entry)
            except Exception:
                pass
            self.after(0, lambda: self._finish_post_print_deduct(active_slot, fname, state, manual))

        import threading

        threading.Thread(target=_prepare_then_ask, daemon=True).start()

    def _finish_post_print_deduct(
        self,
        active_slot: int | None,
        filename: str,
        state: dict,
        manual: bool,
    ) -> None:
        """Dialog nach Druck — state enthält frische retGcodeFileInfo2 vom Drucker."""
        from creality_nfc.cfs_adopt import parse_cfs_slots

        fname = (filename or "").strip()
        cfs_slots: list[CfsSlotInfo] = []
        if hasattr(self, "_printer_device_panel"):
            cfs_slots = list(getattr(self._printer_device_panel, "_cfs_slots", []))
        if not cfs_slots and state:
            cfs_slots = parse_cfs_slots(state)
        file_entry = self._gcode_entry_for_name(state, filename)
        local_gcode = resolve_local_gcode_path(filename) if filename else None
        loaded_slot = find_loaded_slot_index(state) if state else None
        last_print_slot: int | None = None
        if hasattr(self, "_printer_device_panel"):
            last_print_slot = getattr(
                self._printer_device_panel, "_last_print_cfs_slot", None
            )
        prefer_slot = (
            last_print_slot
            if last_print_slot is not None
            else loaded_slot
        )
        gcode_map = None
        if filename and cfs_slots:
            gcode_map = primary_gcode_slot_mapping(
                state,
                filename,
                cfs_slots,
                file_entry=file_entry,
                prefer_slot_index=prefer_slot,
            )
        gcode_slot = gcode_map[0] if gcode_map else None
        slot_hint = (
            gcode_slot
            if gcode_slot is not None
            else (prefer_slot if prefer_slot is not None else active_slot)
        )

        dialog_rows: list[DeductRow] = []
        if filename and cfs_slots:
            for usage in build_slot_usage_plan(
                state,
                filename,
                cfs_slots,
                file_entry=file_entry,
                loaded_slot_index=prefer_slot,
            ):
                sp = find_spool_for_deduct(
                    self.inventory,
                    cfs_slots,
                    usage.slot_index,
                    usage.spec,
                    gcode_path=filename,
                )
                if sp is None:
                    continue
                cfs_name = ""
                if usage.slot_index < len(cfs_slots):
                    sl = cfs_slots[usage.slot_index]
                    cfs_name = f"{sl.vendor} {sl.name}".strip() or sl.material_type or ""
                dialog_rows.append(
                    DeductRow(
                        spool_id=sp.id,
                        slot_label=usage.slot_label,
                        spool_label=sp.label,
                        color_hex=usage.spec.color_hex,
                        material=usage.spec.material_type
                        or material_hint_from_gcode_path(filename),
                        default_grams=usage.grams,
                        source=usage.source,
                        cfs_filament=cfs_name,
                    )
                )

        if not dialog_rows and slot_hint is not None and 0 <= slot_hint <= 3:
            spec = gcode_map[1] if gcode_map else None
            sp = find_spool_for_deduct(
                self.inventory,
                cfs_slots,
                slot_hint,
                spec,
                gcode_path=filename,
            )
            cfs_name = ""
            if slot_hint < len(cfs_slots):
                sl = cfs_slots[slot_hint]
                cfs_name = f"{sl.vendor} {sl.name}".strip() or sl.material_type or ""
            if sp is not None:
                default = self.settings.default_post_print_deduct_g
                source_hint = ""
                if state or filename:
                    est = estimate_grams_for_slot(
                        state,
                        filename,
                        slot_hint,
                        cfs_slots or None,
                        file_entry=file_entry,
                        local_path=local_gcode,
                    )
                    if est:
                        default, source_hint = est
                if default <= 0 and sp.remaining_g is not None:
                    default = min(50, max(1, sp.remaining_g // 20))
                dialog_rows.append(
                    DeductRow(
                        spool_id=sp.id,
                        slot_label=slot_label(slot_hint),
                        spool_label=sp.label,
                        cfs_filament=cfs_name,
                        color_hex=spec.color_hex if spec else None,
                        material=(
                            (spec.material_type if spec else None)
                            or material_hint_from_gcode_path(filename)
                        ),
                        default_grams=default or 50,
                        source=source_hint or "G-Code → Slot",
                    )
                )
            elif cfs_name and slot_hint is not None:
                notify(
                    self,
                    f"Keine Spule für CFS {slot_label(slot_hint)} ({cfs_name}) verknüpft.\n"
                    "Bitte unter „Meine Spulen“ die richtige Spule diesem Slot zuweisen.",
                    "warn",
                )

        if not dialog_rows:
            parts = [
                "Kein automatischer Abzug möglich.",
                f"Datei: {fname or '—'}",
            ]
            if not cfs_slots:
                parts.append(
                    "CFS-Slots vom Drucker fehlen — Tab „Drucker“ verbunden lassen."
                )
            elif slot_hint is not None:
                parts.append(
                    f"Keine Spule mit CFS-Slot {slot_label(slot_hint)} verknüpft "
                    "(„Meine Spulen“ → Spule bearbeiten → CFS-Slot)."
                )
            else:
                parts.append(
                    "G-Code ohne Filament-Gewicht und kein aktiver CFS-Slot erkannt."
                )
            self.notify("\n".join(parts), "warn")
            return
        if fname:
            self._post_print_deduct_file = fname
        self._post_print_prompted = True

        def _ask() -> None:
            deductions = ask_post_print_deductions(
                self, filename=filename, rows=dialog_rows
            )
            self._post_print_prompted = False
            if not deductions:
                return
            thr = self.settings.low_filament_threshold_g
            low_msgs: list[str] = []
            for spool_id, grams in deductions:
                live = self.inventory.get(spool_id)
                if not live:
                    continue
                note = f"Druck {filename or 'beendet'}"[:40]
                deduct_grams(live, grams, note=note[:60])
                self.inventory.update(live)
                if is_low_filament(live, thr):
                    low_msgs.append(f"{live.label}: {live.remaining_g} g")
            self._spool_panel.reload()
            self._refresh_spool_combo()
            if low_msgs:
                self.notify(
                    "Abgezogen. Rest niedrig:\n" + "\n".join(low_msgs),
                    "warn",
                )
            else:
                self.notify(f"Verbrauch abgezogen ({len(deductions)} Spule(n)).", "ok")

        self.after(400, _ask)

    def _duplicate_last_tag_template(self) -> None:
        tpl = self._last_write_template
        if not tpl:
            self.notify("Noch kein Tag geschrieben — zuerst einmal „Tag schreiben“.", "warn")
            return
        self.brand_var.set(tpl.get("brand", ""))
        self._on_brand_change()
        self.material_var.set(tpl.get("material", ""))
        if tpl.get("filament_id"):
            self._select_profile_by_id(
                tpl["filament_id"],
                brand=tpl.get("brand", ""),
                name=tpl.get("material", ""),
            )
        self.color_hex = tpl.get("color_hex", self.color_hex)
        self._update_color_preview()
        self.weight_var.set(tpl.get("weight", self.weight_var.get()))
        self.printer_var.set(tpl.get("printer", self.printer_var.get()))
        if self.auto_serial_var.get():
            self.serial_var.set(self.settings.next_serial_str())
            self.settings.save(DEFAULT_SETTINGS_PATH)
        else:
            self.serial_var.set(tpl.get("serial", self.serial_var.get()))
        self.notebook.select(self.tab_tag)
        self.notify("Material geladen — neuen Tag auflegen und „Tag schreiben“.", "ok")

    def _set_tag_diagnostic_text(self, text: str) -> None:
        if not hasattr(self, "tag_diag_text"):
            return
        self.tag_diag_text.config(state="normal")
        self.tag_diag_text.delete("1.0", "end")
        self.tag_diag_text.insert("1.0", text)
        self.tag_diag_text.config(state="disabled")

    def _spool_match_line(self, matched: Spool | None) -> str:
        if matched is None:
            return "Meine Spule: nicht verknüpft (UID unter „Meine Spulen“ speichern)"
        parts = [matched.label or matched.material_name or "Spule"]
        if matched.brand:
            parts.insert(0, matched.brand)
        if matched.cfs_slot is not None and 0 <= matched.cfs_slot <= 3:
            parts.append(f"CFS {matched.cfs_slot_label()}")
        if matched.remaining_g is not None:
            parts.append(f"{matched.remaining_g} g übrig")
        return "Meine Spule: " + " · ".join(parts)

    def _show_tag_identity(
        self,
        uid: str,
        matched: Spool | None = None,
        *,
        apply_form: bool = False,
        tag_empty: bool = False,
    ) -> Spool | None:
        """Spule + UID oben in der Aktionsleiste; optional Formular befüllen."""
        if not hasattr(self, "spool_match_label"):
            return matched
        uid_n = (uid or "").replace(" ", "").upper().strip()
        if uid_n in ("—", ""):
            uid_n = ""
        if matched is None and uid_n:
            matched = self._spool_for_tag_uid(uid_n)
        self.uid_label.config(text=uid_n or "—")
        if tag_empty:
            self.spool_match_label.config(text="Tag leer — bereit zum Schreiben", fg=OK)
            if matched is not None:
                inv = matched.label or matched.material_name or "Spule"
                self.tag_extra_label.config(
                    text=f"Inventar: {inv} (nur UID verknüpft, kein Filament auf dem Chip)",
                )
            else:
                self.tag_extra_label.config(
                    text="Marke/Material unten wählen, dann „Tag schreiben“",
                )
            if matched is not None and not self._selected_profile():
                self._prefill_form_from_spool_for_write(matched)
            return matched
        if matched is not None:
            title = matched.label or matched.material_name or "Spule"
            self.spool_match_label.config(text=title, fg=TEXT)
            extras: list[str] = []
            if matched.brand and matched.brand.lower() not in title.lower():
                extras.append(matched.brand)
            if matched.material_name and matched.material_name.lower() not in title.lower():
                extras.append(matched.material_name)
            if matched.cfs_slot is not None and 0 <= matched.cfs_slot <= 3:
                extras.append(f"CFS {matched.cfs_slot_label()}")
            if matched.remaining_g is not None:
                extras.append(f"{matched.remaining_g} g übrig")
            self.tag_extra_label.config(text=" · ".join(extras))
            if apply_form:
                self.apply_spool(matched)
        elif uid_n:
            self.spool_match_label.config(text="Unbekannter Tag", fg=WARN)
            self.tag_extra_label.config(text="In „Meine Spulen“ UID speichern")
        else:
            self.spool_match_label.config(
                text="— Tag auflegen oder „Tag lesen“ —",
                fg=MUTED,
            )
            self.tag_extra_label.config(text="")
        return matched

    def _spool_for_tag_uid(self, uid: str) -> Spool | None:
        uid = (uid or "").replace(" ", "").upper()
        if not uid or uid == "—":
            return None
        return self.inventory.find_by_uid(uid)

    def _refresh_tag_diagnostic(
        self,
        session: TagSession | None = None,
        *,
        apply_form: bool = True,
    ) -> Spool | None:
        try:
            if session is None:
                if not self._ensure_reader_for_tag(show_dialog=False):
                    return None
                session = self._session()
            uid = session.uid.hex().upper()
            tag_empty = False
            try:
                tag_empty = payload_is_empty(session.read_payload())
            except Exception:
                pass
            matched = self._show_tag_identity(
                uid,
                apply_form=apply_form and not tag_empty,
                tag_empty=tag_empty,
            )
            text = session.describe_reading()
            text = f"{text}\n\n{self._spool_match_line(matched)}"
            self._set_tag_diagnostic_text(text)
            return matched
        except Exception as exc:
            self._set_tag_diagnostic_text(f"Diagnose fehlgeschlagen:\n{exc}")
            return None

    def _refresh_tag_diagnostic_manual(self) -> None:
        if not self._ensure_reader_for_tag():
            return
        try:
            session = self._session()
            uid = session.uid.hex().upper()
            matched = self._refresh_tag_diagnostic(session)
            spool_txt = self._spool_match_line(matched).replace("Meine Spule: ", "")
            self._tag_finished(
                "Auslesen — fertig",
                f"UID: {uid}\nSpule: {spool_txt}\n\n"
                "Rohdaten unten im Fenster „Tag-Rohdaten“.",
                "ok",
            )
        except Exception as exc:
            self._report_tag_error(exc)

    def format_tag_quick(self) -> None:
        """Creality-Payload auf dem Tag löschen (ohne Tag-Speicher-Dialog)."""

        def do_format() -> None:
            if not self._ensure_reader_for_tag():
                return
            self._set_status("Tag wird geleert…", "info")
            self.update_idletasks()
            try:
                import time

                session = self._session()
                report, tag_empty = session.format_tag()
                uid = session.uid.hex().upper()
                self._suppress_auto_read_until = time.monotonic() + 5.0
                self._refresh_tag_diagnostic(session)
                if tag_empty:
                    self._show_tag_identity(
                        uid,
                        self._spool_for_tag_uid(uid),
                        apply_form=False,
                        tag_empty=True,
                    )
                    self._tag_finished(
                        "Tag leeren — fertig",
                        f"UID: {uid}\n\n"
                        "Der Tag ist leer und bereit zum Neu-Beschreiben.\n\n"
                        "Hinweis: In den Rohdaten sehen Blöcke 4–6 oft so aus:\n"
                        "C3B98E0E7A3D… (verschlüsseltes Leer — ist korrekt).\n"
                        "Oben steht „Tag leer“, nicht der Spulenname vom Inventar.\n\n"
                        f"{report}",
                        "ok",
                    )
                else:
                    self._tag_finished(
                        "Tag leeren — fehlgeschlagen",
                        f"UID: {uid}\n\n"
                        "Es sind noch Filament-Daten auf dem Tag.\n"
                        "Tag kurz abheben, wieder auflegen, dann erneut „Tag leeren…“.\n\n"
                        f"{report}",
                        "warn",
                    )
            except Exception as exc:
                self._report_tag_error(exc)

        confirm(
            self,
            "Tag wirklich leeren?\n\nCreality-Daten auf dem Tag werden gelöscht.",
            do_format,
        )

    def save_current_spool(self) -> None:
        sp = self.spool_from_form()
        if self._active_spool_id:
            existing = self.inventory.get(self._active_spool_id)
            if existing:
                sp.id = existing.id
                sp.notes = existing.notes
                sp.remaining_g = existing.remaining_g
        self.notebook.select(self.tab_spools)
        self._spool_panel.prefill(sp)
        built = self._spool_panel.edit_panel.build_spool()
        if built:
            self._spool_panel._persist_spool(built)

    def _goto_spools_tab(self) -> None:
        self.notebook.select(self.tab_spools)

    def _profile_by_key(
        self,
        filament_id: str,
        brand: str = "",
        name: str = "",
    ) -> FilamentProfile | None:
        want = normalize_filament_id(filament_id)
        if not want:
            return None
        matches = [
            p for p in self.profiles if normalize_filament_id(p.filament_id) == want
        ]
        if not matches:
            return None
        brand_s = brand.strip()
        name_s = name.strip()
        if brand_s and name_s:
            for p in matches:
                if p.brand.strip() == brand_s and p.name.strip() == name_s:
                    return p
        if len(matches) == 1:
            return matches[0]
        return None

    def _selected_profile(self) -> FilamentProfile | None:
        label = self.material_var.get()
        key = self._material_combo_map.get(label) or self._current_profile
        if key[0]:
            found = self._profile_by_key(key[0], key[1], key[2])
            if found:
                return found
        brand = self.brand_var.get()
        raw_name = self.material_var.get()
        name = raw_name.split("  ·  ")[0].strip() if "  ·  " in raw_name else raw_name.strip()
        matches = [p for p in self.profiles if p.brand == brand and p.name == name]
        if len(matches) == 1:
            return matches[0]
        return None

    def _profile_for_spool(self, spool: Spool) -> FilamentProfile | None:
        """Profil aus Spulendaten — DB-Treffer oder synthetisch (wenn filament_id gesetzt)."""
        found = self._profile_by_key(
            spool.filament_id, spool.brand, spool.material_name
        )
        if found:
            return found
        return resolve_filament_profile(
            spool,
            self.profiles,
            default_printer=self.printer_var.get().strip() or DEFAULT_PRINTER,
        )

    def _spools_for_write_context(self) -> list[Spool]:
        """Spulen, die „→ RFID-Tab“ oder Tag-UID gesetzt haben."""
        seen: set[str] = set()
        out: list[Spool] = []

        def add(sp: Spool | None) -> None:
            if sp and sp.id not in seen:
                seen.add(sp.id)
                out.append(sp)

        if self._active_spool_id:
            add(self.inventory.get(self._active_spool_id))
        uid = self.uid_label.cget("text").strip()
        if uid and uid != "—":
            add(self._spool_for_tag_uid(uid))
        return out

    def _ensure_profile_for_write(self) -> FilamentProfile | None:
        """Material für Tag-Schreiben — Combo, aktive Spule oder letzte Vorlage."""
        profile = self._selected_profile()
        if profile:
            return profile
        for sp in self._spools_for_write_context():
            profile = self._profile_for_spool(sp)
            if profile:
                self._apply_spool_rfid_fields(sp, select_profile=profile)
                return profile
        tpl = self._last_write_template
        if tpl and tpl.get("filament_id"):
            if self._select_profile_by_id(
                tpl["filament_id"],
                brand=tpl.get("brand", ""),
                name=tpl.get("material", ""),
            ):
                if tpl.get("color_hex"):
                    self.color_hex = normalize_hex(tpl["color_hex"])
                    self._update_color_preview()
                if tpl.get("weight"):
                    self.weight_var.set(tpl["weight"])
                return self._selected_profile()
        return None

    def _apply_spool_rfid_fields(
        self,
        spool: Spool,
        *,
        select_profile: FilamentProfile | None = None,
    ) -> None:
        """Spule ins RFID-Formular — Suchfilter leeren, Profil in der Combo setzen."""
        if self.search_var.get().strip():
            self.search_var.set("")
            self._apply_material_filter()
        profile = select_profile or self._profile_for_spool(spool)
        if profile:
            self._select_profile_in_ui(profile)
        elif spool.brand:
            brands = list(self.brand_combo["values"])
            if spool.brand not in brands:
                self.brand_combo["values"] = tuple(brands) + (spool.brand,)
            self.brand_var.set(spool.brand)
            self._on_brand_change()
            if spool.material_name:
                self.material_var.set(spool.material_name)
        if spool.color_hex:
            self.color_hex = normalize_hex(spool.color_hex)
            self._color_from_user = True
            self._update_color_preview()
        if spool.weight:
            self.weight_var.set(spool.weight)
        if spool.printer:
            vals = list(self.printer_combo["values"])
            if spool.printer not in vals:
                self.printer_combo["values"] = tuple(vals) + (spool.printer,)
            self.printer_var.set(spool.printer)
        if spool.serial:
            self.serial_var.set(spool.serial)
        self._update_filament_selection_label()

    def _select_profile_by_id(
        self,
        material_id: str,
        *,
        brand: str = "",
        name: str = "",
    ) -> bool:
        profile = self._profile_by_key(material_id, brand, name)
        if not profile:
            want = normalize_filament_id(material_id)
            matches = [
                p
                for p in self.profiles
                if normalize_filament_id(p.filament_id) == want
            ]
            if len(matches) == 1:
                profile = matches[0]
            elif len(matches) > 1:
                cur = self._selected_profile()
                if cur and normalize_filament_id(cur.filament_id) == want:
                    profile = cur
                else:
                    names = ", ".join(p.name for p in matches[:4])
                    extra = f" (+{len(matches) - 4})" if len(matches) > 4 else ""
                    self.notify(
                        f"ID {material_id}: mehrere Profile ({names}{extra}).\n"
                        "Bitte das richtige Material in der Liste wählen.",
                        "warn",
                    )
                    return False
            else:
                return False
        self._select_profile_in_ui(profile)
        return True

    # ── NFC / Reader ────────────────────────────────────────────────

    def _do_restart_scard_uac(self) -> None:
        if not restart_scard_elevated():
            self.notify("UAC-Dialog fehlgeschlagen.", "error")
            return
        self._set_status("Smartcard wird neu gestartet…", "warn")
        self.after(4000, self._after_smartcard_start)

    def _do_start_scard_uac(self) -> None:
        if not start_scard_elevated():
            self.notify("UAC-Dialog fehlgeschlagen.", "error")
            return
        self._set_status("Smartcard startet… UAC bestätigen", "warn")
        self.after(3000, self._after_smartcard_start)

    def start_smartcard_service(self) -> None:
        state = probe_pcsc()
        if state == "ok":
            self._apply_nfc_ui()
            self.notify("Bereit — NFC-Reader erkannt.", "ok")
            self.connect_reader(show_errors=False)
            return
        if state == "no_reader":
            self._apply_nfc_ui()
            self._set_status("Reader nicht gefunden — USB prüfen", "warn")
            self.notify(
                "Dienst läuft. ACR122U per USB anschließen, dann „Reader verbinden“.",
                "warn",
            )
            return
        if state == "service_stuck":
            self.ask_confirm(
                scard_status_message(state) + "\n\nJetzt neu starten? (UAC)",
                self._do_restart_scard_uac,
            )
            return
        self.ask_confirm(
            scard_status_message() + "\n\nJetzt starten? (UAC)",
            self._do_start_scard_uac,
        )

    def _after_smartcard_start(self) -> None:
        state = self._apply_nfc_ui()
        if state == "ok":
            self._set_status("Smartcard aktiv", "ok")
            self.connect_reader(show_errors=False)
        elif state == "no_reader":
            self._set_status("Dienst OK — Reader per USB verbinden", "warn")
        elif state == "service_stuck":
            self._set_status("Noch hängend — „Anleitung“ oder PC neu starten", "error")
            self.notify("Dienst antwortet noch nicht.\n\n"
                "„Anleitung“ unten → Dienste (services.msc) → Smartcard neu starten,\n"
                "oder PC neu booten. Ohne NFC: Rest der App geht weiter.",
            )
        else:
            self._set_status("UAC mit „Ja“ bestätigen, dann erneut klicken", "warn")

    def connect_reader(self, show_errors: bool = True) -> None:
        state = self._apply_nfc_ui()
        if state == "service_down":
            self._set_status("Smartcard-Dienst aus", "error")
            if show_errors:
                self.ask_confirm(
                    scard_status_message(state) + "\n\nJetzt starten?",
                    self.start_smartcard_service,
                )
            return
        if state == "service_stuck":
            self._set_status("Smartcard hängt — neu starten", "error")
            if show_errors:
                self.start_smartcard_service()
            return
        if state == "no_reader":
            self._set_status("Kein Reader — USB anschließen", "warn")
            if show_errors:
                self.notify("Smartcard-Dienst läuft.\n\nBitte ACR122U per USB verbinden.",
                )
            return
        try:
            pref = self.settings.preferred_reader.strip() or None
            name = self.reader.connect(pref)
            self._apply_nfc_ui()
            short = name if len(name) <= 50 else name[:47] + "…"
            if self.reader.direct_mode:
                self._set_status(f"Reader bereit — Tag auflegen: {short}", "ok")
            else:
                self._set_status(f"Reader verbunden: {short}", "ok")
        except NfcReaderError as exc:
            short, detail, offer_start = self._nfc_error_message(exc)
            self._apply_nfc_ui()
            self._set_status(short, "error")
            if show_errors:
                if offer_start:
                    self.ask_confirm(detail + "\n\nAktion ausführen?", self.start_smartcard_service)
                else:
                    self.notify(detail, "error")
        except Exception as exc:
            self._set_status("Reader-Fehler", "error")
            if show_errors:
                self.notify(str(exc), "error")

    def _start_monitor(self) -> None:
        if self._monitor:
            return

        def on_insert() -> None:
            self.after(50, self._on_tag_present)

        self._monitor = NfcCardMonitor(on_inserted=on_insert)
        try:
            self._monitor.start()
        except Exception:
            self._monitor = None

    def _on_tag_present(self) -> None:
        import time

        if self._chip_dup_step:
            self.after(80, self._chip_dup_on_tag)
            return
        if time.monotonic() < self._suppress_auto_read_until:
            return
        if self._tag_busy or not (self.auto_read_var.get() or self.auto_write_var.get()):
            return
        will_auto_write = bool(
            self.auto_write_var.get()
            and self._selected_profile()
        )
        self._tag_busy = True
        try:
            if self.auto_read_var.get() and not self._batch_waiting and not will_auto_write:
                self._read_tag_quiet()
            if will_auto_write:
                uid = self.uid_label.cget("text").strip()
                if self.batch_write_var.get() and self._batch_waiting:
                    if uid and uid != "—":
                        self._batch_waiting = False
                        self.write_tag(silent=True)
                        self._last_auto_uid = uid
                        self._batch_waiting = True
                elif uid and uid != "—" and uid != self._last_auto_uid:
                    self.write_tag(silent=True)
                    self._last_auto_uid = uid
        finally:
            self._tag_busy = False

    def duplicate_chip_start(self) -> None:
        """Assistent: Quell-Chip lesen → Ziel-Chip 1:1 beschreiben."""
        if self._chip_dup_step:
            if messagebox.askyesno(
                APP_NAME,
                "Chip duplizieren läuft noch.\n\nAbbrechen?",
                default="no",
            ):
                self._chip_dup_cancel()
            return
        if not messagebox.askyesno(
            APP_NAME,
            "Chip duplizieren\n\n"
            "1. Quell-Chip (Vorlage) auf den Leser legen — wird vollständig gelesen\n"
            "2. Quell-Chip entfernen\n"
            "3. Ziel-Chip (Kopie) auflegen — wird beschrieben\n\n"
            "Es wird der komplette Tag-Inhalt kopiert (unabhängig vom Formular).\n\n"
            "Jetzt starten?",
            default="yes",
        ):
            return
        self.notebook.select(self.tab_tag)
        self._chip_dup_step = "source"
        self._chip_dup_payload = None
        self._chip_dup_source_uid = ""
        self._chip_dup_source_spool_id = ""
        self._set_status("Chip duplizieren: Quell-Chip auflegen …", "info")
        messagebox.showinfo(
            APP_NAME,
            "Bitte den Quell-Chip (Vorlage) auf den Leser legen.\n\n"
            "Der Chip wird automatisch gelesen, sobald er erkannt wird.",
        )

    def _chip_dup_link_target_uid(self, target_uid: str) -> str:
        """Ziel-Chip-UID derselben Spule zuordnen wie die Quelle (jeder Chip hat eigene UID)."""
        sp: Spool | None = None
        if self._chip_dup_source_spool_id:
            sp = self.inventory.get(self._chip_dup_source_spool_id)
        if sp is None and self._chip_dup_source_uid:
            sp = self.inventory.find_by_uid(self._chip_dup_source_uid)
        if sp is None:
            return ""
        if sp.register_tag_uid(target_uid):
            self.inventory.update(sp)
            self._active_spool_id = sp.id
            self._refresh_spool_combo()
            if hasattr(self, "_spool_panel"):
                self._spool_panel.reload()
            if hasattr(self, "_printer_device_panel"):
                self._printer_device_panel.cfs_dashboard.set_inventory(self.inventory)
            n = len(sp.all_tag_uids())
            return (
                f"Spule „{sp.label}“: Ziel-Chip in „Meine Spulen“ verknüpft "
                f"({n} Tag{'s' if n != 1 else ''})."
            )
        return f"Spule „{sp.label}“: Ziel-Chip war bereits verknüpft."

    def _chip_dup_cancel(self, *, notify: bool = True) -> None:
        self._chip_dup_step = ""
        self._chip_dup_payload = None
        self._chip_dup_source_uid = ""
        self._chip_dup_source_spool_id = ""
        try:
            self.reader.disconnect()
        except Exception:
            pass
        if notify:
            self._set_status("Chip duplizieren abgebrochen", "info")
            messagebox.showinfo(APP_NAME, "Chip duplizieren wurde abgebrochen.")

    def _chip_dup_on_tag(self) -> None:
        if not self._chip_dup_step or self._tag_busy:
            return
        if self._chip_dup_step == "source":
            self._chip_dup_read_source()
        elif self._chip_dup_step == "target":
            self._chip_dup_write_target()

    def _chip_dup_read_source(self) -> None:
        import time

        if not self._ensure_reader_for_tag():
            self._chip_dup_cancel(notify=False)
            messagebox.showerror(APP_NAME, "Reader nicht bereit — Vorgang abgebrochen.")
            return
        self._tag_busy = True
        self._suppress_auto_read_until = time.monotonic() + 60.0
        try:
            session = self._session()
            uid = session.uid.hex().upper()
            raw = session.read_payload()
            self._chip_dup_payload = payload_bytes_from_read(raw)
            self._chip_dup_source_uid = uid
            src_spool = self.inventory.find_by_uid(uid)
            self._chip_dup_source_spool_id = src_spool.id if src_spool else ""
            self.uid_label.config(text=uid)
            self._refresh_tag_diagnostic(session)
            try:
                self.reader.disconnect()
            except Exception:
                pass
            self._chip_dup_step = "target"
            empty = payload_is_empty(raw)
            detail = (
                f"Quell-Chip gelesen.\n\nUID: {uid}\n"
                f"Inhalt: {'leer' if empty else 'Filament-Daten'}\n\n"
                "Bitte den Quell-Chip vom Leser nehmen und den Ziel-Chip (Kopie) auflegen."
            )
            self._tag_finished("Quell-Chip gelesen", detail, "ok")
        except Exception as exc:
            self._report_tag_error(exc)
            self._chip_dup_cancel(notify=False)
            messagebox.showerror(APP_NAME, "Lesen fehlgeschlagen — Vorgang abgebrochen.")
        finally:
            self._tag_busy = False

    def _chip_dup_write_target(self) -> None:
        import time

        if not self._chip_dup_payload:
            self._chip_dup_cancel()
            return
        if not self._ensure_reader_for_tag():
            messagebox.showerror(APP_NAME, "Reader nicht bereit.")
            return
        self._tag_busy = True
        self._suppress_auto_read_until = time.monotonic() + 60.0
        try:
            session = self._session()
            uid = session.uid.hex().upper()
            if uid == self._chip_dup_source_uid:
                try:
                    self.reader.disconnect()
                except Exception:
                    pass
                messagebox.showwarning(
                    APP_NAME,
                    "Das ist noch der Quell-Chip (gleiche UID).\n\n"
                    "Bitte den Quell-Chip entfernen und den Ziel-Chip auflegen.",
                )
                return
            if not messagebox.askyesno(
                APP_NAME,
                f"Ziel-Chip erkannt\n\nUID: {uid}\nQuelle war: {self._chip_dup_source_uid}\n\n"
                "Jetzt den Inhalt auf diesen Chip schreiben?",
                default="yes",
            ):
                try:
                    self.reader.disconnect()
                except Exception:
                    pass
                self._set_status("Schreiben abgebrochen — Ziel-Chip erneut auflegen", "warn")
                return
            session.write_payload(self._chip_dup_payload)
            read_back = session.read_payload()
            verify_ok = payload_bytes_from_read(read_back) == self._chip_dup_payload
            self.uid_label.config(text=uid)
            self._refresh_tag_diagnostic(session, apply_form=False)
            try:
                self.reader.disconnect()
            except Exception:
                pass
            link_msg = self._chip_dup_link_target_uid(uid)
            self._show_tag_identity(uid, apply_form=True)
            self._chip_dup_step = ""
            body = (
                f"Der Ziel-Chip wurde beschrieben.\n\n"
                f"Quelle: {self._chip_dup_source_uid}\n"
                f"Ziel:   {uid}\n\n"
            )
            if verify_ok:
                body += "Prüfung: Inhalt stimmt überein.\n"
            else:
                body += "Hinweis: Rücklesen weicht ab — ggf. erneut duplizieren.\n"
            if link_msg:
                body += f"\n{link_msg}"
            else:
                body += (
                    "\nHinweis: Keine Spule zur Quelle gefunden — unter „Meine Spulen“ "
                    "die neue UID speichern."
                )
            self._chip_dup_payload = None
            keep_spool = self._chip_dup_source_spool_id
            self._chip_dup_source_uid = ""
            self._chip_dup_source_spool_id = keep_spool
            self._tag_finished("Chip kopiert", body, "ok" if verify_ok else "warn")
            if messagebox.askyesno(
                APP_NAME,
                "Noch einen weiteren Chip mit denselben Daten beschreiben?",
                default="no",
            ):
                self._chip_dup_step = "target"
                messagebox.showinfo(
                    APP_NAME,
                    "Legen Sie den nächsten Ziel-Chip auf den Leser.",
                )
            else:
                self._chip_dup_source_spool_id = ""
        except Exception as exc:
            self._report_tag_error(exc)
            if messagebox.askyesno(APP_NAME, "Fehler — Vorgang abbrechen?", default="yes"):
                self._chip_dup_cancel(notify=False)
        finally:
            self._tag_busy = False

    def pick_color(self) -> None:
        _, hex_color = colorchooser.askcolor(color="#" + self.color_hex, title="Filamentfarbe")
        if hex_color:
            self._apply_color_hex(hex_color.lstrip("#"))

    def _apply_color_hex(self, hex_code: str) -> None:
        self.color_hex = normalize_hex(hex_code)
        self._color_from_user = True
        self._update_color_preview()

    def _write_tag_color(self) -> str:
        """Farbe für Tag-Schreiben — aktueller UI-Wert, unabhängig von späteren Reads."""
        return normalize_hex(self.color_hex)

    def _apply_fields_from_tag(
        self,
        info: dict[str, str],
        *,
        matched: Spool | None = None,
    ) -> None:
        """Tag-Felder ins Formular — Farbe nicht vom alten Tag, wenn Spule/UI-Farbe gilt."""
        if matched is not None and matched.color_hex:
            self.color_hex = normalize_hex(matched.color_hex)
            self._color_from_user = False
            self._update_color_preview()
        elif not self._color_from_user and info.get("color"):
            self.color_hex = color_from_tag_field(info["color"])
            self._update_color_preview()
        wlabel = next((k for k, v in WEIGHT_CODES.items() if v == info["weight_code"]), None)
        if wlabel:
            self.weight_var.set(wlabel)
        if info.get("serial"):
            self.serial_var.set(info["serial"])
        if info.get("printer"):
            p = info["printer"]
            vals = list(self.printer_combo["values"])
            if p not in vals:
                self.printer_combo["values"] = tuple(vals) + (p,)
            self.printer_var.set(p)
        if info.get("material_id"):
            self._select_profile_by_id(info["material_id"])

    def show_color_presets(self) -> None:
        show_color_presets(self, self._btn_color_presets, self._apply_color_hex)

    def pick_color_from_image(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="Filament-Foto wählen",
            filetypes=[
                ("Bilder", "*.jpg *.jpeg *.png *.webp *.bmp"),
                ("Alle", "*.*"),
            ],
        )
        if not path:
            return
        try:
            hex_code = color_from_image_path(path)
            self._apply_color_hex(hex_code)
            self.notify(f"Farbe aus Foto: #{hex_code}", "ok")
        except Exception as exc:
            self.notify(str(exc), "error")

    def _store_tag_export(self, uid: str, info: dict[str, str]) -> None:
        profile = self._selected_profile()
        wlabel = next(
            (k for k, v in WEIGHT_CODES.items() if v == info.get("weight_code")),
            info.get("weight_code", ""),
        )
        self._last_tag_export = build_tag_export(
            uid=uid,
            parsed=info,
            color_hex=self.color_hex,
            weight_label=wlabel or self.weight_var.get(),
            serial=self.serial_var.get().strip() or info.get("serial", ""),
            printer_model=self.printer_var.get().strip() or info.get("printer", ""),
            material_brand=profile.brand if profile else "",
            material_name=profile.name if profile else "",
            filament_id=profile.filament_id if profile else info.get("material_id", ""),
        )

    def export_tag_data(self) -> None:
        if not self._last_tag_export:
            self.notify("Zuerst „Tag lesen“ — dann kann exportiert werden.", "warn")
            return
        uid = self._last_tag_export.get("uid", "tag")
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Tag-Daten exportieren",
            initialfile=f"tag_{uid}.json",
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("Alle", "*.*")],
        )
        if not path:
            return
        try:
            save_tag_export(self._last_tag_export, Path(path))
            self.notify(f"Tag-Daten gespeichert:\n{path}", "ok")
        except OSError as exc:
            self.notify(str(exc), "error")

    def _maybe_show_setup_wizard(self) -> None:
        if not self.settings.show_setup_on_startup and self.settings.setup_completed:
            return
        self._show_setup_wizard(mark_done=True)

    def _show_setup_wizard(self, *, mark_done: bool = False) -> None:
        has_db = bool(self.db_data and self.db_data.get("result", {}).get("list"))

        def on_done(show_on_startup: bool) -> None:
            self.settings.show_setup_on_startup = show_on_startup
            if mark_done and not show_on_startup:
                self.settings.setup_completed = True
            self.settings.save(DEFAULT_SETTINGS_PATH)

        SetupWizardDialog(
            self,
            has_database=has_db,
            show_on_startup=self.settings.show_setup_on_startup,
            on_open_help=lambda: self.notebook.select(self.tab_help),
            on_connect_reader=lambda: self.connect_reader(show_errors=True),
            on_load_db=self.sync_database,
            on_done=on_done,
        )

    def _session(self) -> TagSession:
        self.reader.connect(self.settings.preferred_reader.strip() or None)
        return TagSession(self.reader)

    def _current_serial(self) -> str:
        s = self.serial_var.get().strip()
        return s if len(s) == 6 and s.isdigit() else self.settings.next_serial_str()

    def _read_tag_quiet(self) -> None:
        try:
            session = self._session()
            uid = session.uid.hex().upper()
            raw = session.read_payload()
            matched = self._refresh_tag_diagnostic(session)
            if payload_is_empty(raw):
                self._set_status("Tag leer", "ok")
                return
            info = parse_tag_payload(raw)
            self._apply_fields_from_tag(info, matched=matched)
            self._store_tag_export(uid, info)
            self._set_status("Tag gelesen", "ok")
        except Exception as exc:
            self._set_status(str(exc)[:70], "error")

    def read_tag(self) -> None:
        if not self._ensure_reader_for_tag():
            return
        self._set_status("Tag wird gelesen…", "info")
        self.update_idletasks()
        try:
            session = self._session()
            uid = session.uid.hex().upper()
            raw = session.read_payload()
            matched = self._refresh_tag_diagnostic(session)
            if payload_is_empty(raw):
                spool_txt = self._spool_match_line(matched).replace("Meine Spule: ", "")
                self._tag_finished(
                    "Tag lesen — fertig",
                    f"UID: {uid}\nSpule: {spool_txt}\n\n"
                    "Der Tag ist leer (keine Filament-Daten).\n"
                    "Normal nach „Tag leeren“ — jetzt „Tag schreiben“.",
                    "ok",
                )
                return
            info = parse_tag_payload(raw)
            self._apply_fields_from_tag(info, matched=matched)
            wlabel = next(
                (k for k, v in WEIGHT_CODES.items() if v == info["weight_code"]),
                info["weight_code"],
            )
            self._store_tag_export(uid, info)
            spool_txt = self._spool_match_line(matched).replace("Meine Spule: ", "")
            self._tag_finished(
                "Tag lesen — fertig",
                f"UID: {uid}\nSpule: {spool_txt}\n\n"
                f"Material-ID: {info['material_id']}\n"
                f"Farbe: {info['color']}\n"
                f"Gewicht: {wlabel}\n"
                f"Serie: {info.get('serial', '?')}\n"
                f"Drucker: {info.get('printer', '') or '—'}",
                "ok",
            )
        except Exception as exc:
            self._report_tag_error(exc)

    def write_tag(self, silent: bool = False, *, _demo_ok: bool = False) -> None:
        profile = self._ensure_profile_for_write()
        if not profile:
            if not silent:
                self._prompt_select_material_for_write()
            return
        if self._demo_mode and not silent and not _demo_ok:
            self.notify(
                "Demo-Materialien aktiv — für echte Profile „Datenbank laden…“ nutzen.",
                "warn",
            )
        if not self._ensure_reader_for_tag(show_dialog=not silent):
            return
        import time

        write_color = self._write_tag_color()
        serial = self._current_serial()
        if not silent:
            self._set_status("Tag wird geschrieben…", "info")
            self.update_idletasks()
        prev_busy = self._tag_busy
        self._tag_busy = True
        self._suppress_auto_read_until = time.monotonic() + 8.0
        try:
            if not self.reader.is_ready:
                self.connect_reader(show_errors=not silent)
            session = self._session()
            if self.settings.protect_tag_overwrite:
                try:
                    raw_existing = session.read_payload()
                    if not payload_is_empty(raw_existing) and not silent:
                        info = parse_tag_payload(raw_existing)
                        wlabel = next(
                            (
                                k
                                for k, v in WEIGHT_CODES.items()
                                if v == info.get("weight_code")
                            ),
                            info.get("weight_code") or "?",
                        )
                        if not messagebox.askyesno(
                            APP_NAME,
                            "Der Tag enthält bereits Filament-Daten:\n\n"
                            f"Material-ID: {info.get('material_id', '?')}\n"
                            f"Farbe: {info.get('color', '?')}\n"
                            f"Gewicht: {wlabel}\n"
                            f"Serie: {info.get('serial', '?')}\n\n"
                            "Wirklich überschreiben?",
                            default="no",
                            parent=self,
                        ):
                            self._set_status("Schreiben abgebrochen", "warn")
                            return
                except NfcReaderError:
                    pass
            session.write_payload(
                build_tag_payload(
                    profile.filament_id,
                    write_color,
                    self.weight_var.get(),
                    self.printer_var.get().strip(),
                    serial=serial,
                )
            )
            read_back = parse_tag_payload(session.read_payload())
            verify_errors = verify_tag_payload(
                read_back,
                material_id=profile.filament_id,
                color_hex=write_color,
                weight_label=self.weight_var.get(),
                printer_model=self.printer_var.get().strip(),
                serial=serial,
            )
            uid = session.uid.hex().upper()
            self.color_hex = write_color
            self._update_color_preview()
            self._show_tag_identity(uid, apply_form=False)
            self._last_write_template = {
                "brand": profile.brand,
                "material": profile.name,
                "filament_id": profile.filament_id,
                "color_hex": write_color,
                "weight": self.weight_var.get(),
                "printer": self.printer_var.get().strip(),
                "serial": serial,
            }
            if self.auto_serial_var.get():
                self.settings.bump_serial()
                self.serial_var.set(self.settings.next_serial_str())
                self._save_settings()
            spool_msg = self._sync_spool_after_tag(uid, profile, serial)
            self._refresh_tag_diagnostic(session, apply_form=False)
            if self.batch_write_var.get():
                self._batch_waiting = True
                self._last_auto_uid = uid
                if not silent:
                    self._tag_finished(
                        "Tag schreiben — fertig",
                        f"UID: {uid}\n\n{profile.brand} — {profile.name}\n"
                        f"ID {profile.filament_id}, SN {serial}\n\n"
                        "Nächsten Tag auflegen (Stapelmodus).",
                        "ok" if not verify_errors else "warn",
                    )
            elif not silent:
                body = (
                    f"UID: {uid}\n\n"
                    f"{profile.brand} — {profile.name}\n"
                    f"ID {profile.filament_id}, SN {serial}\n"
                )
                if verify_errors:
                    body += "\nGeschrieben, Prüfung meldet:\n" + "\n".join(
                        f"• {e}" for e in verify_errors
                    )
                else:
                    body += "\nGeschrieben und geprüft — stimmt."
                if spool_msg:
                    body += f"\n\n{spool_msg}"
                self._tag_finished(
                    "Tag schreiben — fertig" if not verify_errors else "Tag schreiben — Prüfung",
                    body,
                    "warn" if verify_errors else "ok",
                )
            elif silent and spool_msg:
                self._set_status(spool_msg[:64], "ok")
        except Exception as exc:
            self._report_tag_error(exc, silent=silent)
        finally:
            self._tag_busy = prev_busy

    def open_tag_tools(self) -> None:
        TagToolsDialog(self, self.reader)

    def open_tag_holder_links(self) -> None:
        TagHolderLinksDialog(self)

    def open_settings(self) -> None:
        self.notebook.select(self.tab_settings)
        self.notify("Einstellungen — Tab „Einstellungen“ oben", "info")

    def open_printer_manager(self) -> None:
        def apply_profile(p) -> None:
            self.ssh_host_var.set(p.host)
            self.ssh_pass_var.set(p.password)
            model = normalize_printer_model(p.model or DEFAULT_PRINTER)
            if p.model and p.model.strip() != model:
                self.notify(
                    f"Modell „{p.model}“ wird nicht unterstützt — es gilt „{model}“ (K2/CFS).",
                    "warn",
                )
            self.printer_var.set(model)
            save_settings(p.host, p.password, model)
            self._set_status(f"Drucker „{p.name}“ übernommen ({p.host})", "ok")
            self.notify(f"IP {p.host} · Modell {p.model}", "ok")

        PrinterManagerDialog(self, on_apply=apply_profile)

    def _factory_reset_app(self) -> None:
        def do_reset() -> None:
            def really_reset() -> None:
                try:
                    if self._monitor:
                        self._monitor.stop()
                        self._monitor = None
                    factory_reset_data_dir(DATA_DIR)
                except OSError as exc:
                    messagebox.showerror(APP_NAME, f"Zurücksetzen fehlgeschlagen:\n{exc}", parent=self)
                    return
                messagebox.showinfo(
                    APP_NAME,
                    "Alle Daten wurden gelöscht.\n\nDas Programm startet jetzt neu.",
                    parent=self,
                )
                self.destroy()
                if getattr(sys, "frozen", False):
                    os.execv(sys.executable, [sys.executable, *sys.argv[1:]])
                else:
                    main_py = Path(__file__).resolve().parent.parent / "main.py"
                    os.execv(sys.executable, [sys.executable, str(main_py), *sys.argv[1:]])

            self.ask_confirm(
                "Letzte Warnung:\n\n"
                "Wirklich ALLES löschen?\n"
                "(Material-DB, Spulen, Modell-Bibliothek, Drucker, Einstellungen)",
                really_reset,
            )

        self.ask_confirm(
            "Programm auf Werkseinstellung zurücksetzen?\n\n"
            "Der komplette Ordner data/ wird gelöscht — wie bei einer Neuinstallation.\n\n"
            "Tipp: Vorher „Datei → Daten sichern (ZIP)…“.\n\n"
            "Fortfahren?",
            do_reset,
        )

    def backup_data(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".zip",
            initialfile=default_backup_name(),
            filetypes=[("ZIP", "*.zip")],
        )
        if not path:
            return
        try:
            backup_data_dir(DATA_DIR, Path(path))
            self.notify(f"Gesichert:\n{path}")
        except Exception as exc:
            self.notify(str(exc), "error")

    def restore_data(self) -> None:
        def proceed() -> None:
            path = filedialog.askopenfilename(filetypes=[("ZIP", "*.zip")])
            if not path:
                return
            try:
                n = restore_data_dir(Path(path), DATA_DIR)
                self._load_materials()
                self._refresh_spool_combo()
                self.notify(f"{n} Dateien wiederhergestellt. App neu starten empfohlen.", "ok")
            except Exception as exc:
                self.notify(str(exc), "error")

        self.ask_confirm("data/ wird aus der ZIP überschrieben.\nFortfahren?", proceed)

    def import_cfs_zip(self) -> None:
        path = filedialog.askopenfilename(
            title="CFS-RFID.zip",
            filetypes=[("ZIP", "*.zip"), ("Alle", "*.*")],
        )
        if not path:
            return
        try:
            out = import_cfs_rfid_zip(Path(path), DATA_DIR, self.printer_var.get().strip())
            self._load_materials()
            self.notify(f"Material-DB importiert:\n{out.name}")
        except Exception as exc:
            self.notify(str(exc), "error")

    def _schedule_reader_poll(self) -> None:
        sec = max(5, int(self.settings.poll_reader_sec))
        self._poll_reader()
        self.after(sec * 1000, self._schedule_reader_poll)

    def _poll_reader(self) -> None:
        state = probe_pcsc()
        if state == "ok":
            try:
                pref = self.settings.preferred_reader.strip() or None
                self.reader.connect(pref)
                self._apply_nfc_ui()
                short = self.reader._reader_name or "Reader"
                if len(short) > 45:
                    short = short[:42] + "…"
                self._set_status(f"Reader: {short}", "ok")
            except Exception:
                pass
        elif state == "no_reader":
            self._apply_nfc_ui()
            if self.uid_label.cget("text") == "—":
                self._set_status("Reader einstecken…", "warn")

    def _check_updates_quiet(self) -> None:
        try:
            tag = fetch_latest_release_tag()
            if tag and is_newer(tag.lstrip("v"), APP_VERSION):
                self._set_status(f"Update: {tag}", "warn")
        except Exception:
            pass

    def check_updates(self) -> None:
        tag = fetch_latest_release_tag()
        if not tag:
            self.notify("Keine Versionsinfo.")
            return
        if is_newer(tag.lstrip("v"), APP_VERSION):
            self.notify(f"Neu: {tag} — installiert: {APP_VERSION}", "warn")
        else:
            self.notify(f"Aktuell ({APP_VERSION}).", "ok")

    def destroy(self) -> None:
        if self._monitor:
            self._monitor.stop()
        if hasattr(self, "_device_panel"):
            self._device_panel.disconnect()
        self._save_settings()
        super().destroy()
