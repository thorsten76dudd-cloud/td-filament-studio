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
    normalize_printer_model,
    printer_int_to_display,
)
from creality_nfc.app_settings import DEFAULT_SETTINGS_PATH, AppSettings
from creality_nfc.config import (
    APP_NAME,
    APP_TAGLINE,
    APP_VERSION,
    GITHUB_RELEASES_REPO,
    GITHUB_URL,
    MATERIAL_DB_PRINTER_ONLY,
)
from creality_nfc.i18n import t as _t
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
from creality_nfc.material_options import build_material_options, export_material_options
from creality_nfc.materials import (
    FilamentProfile,
    builtin_profiles,
    normalize_filament_id,
)
from creality_nfc.printer_camera import printer_reachable
from creality_nfc.printer_ssh import (
    download_database_from_printer,
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
from creality_nfc.spool_profile import format_spool_label, resolve_filament_profile
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
from creality_nfc.update_check import (
    ReleaseInfo,
    fetch_latest_release,
    is_newer,
    release_stats_lines,
)
from printer_connect import load_settings, save_settings
from printer_manager import PrinterManagerDialog
from tag_tools import TagToolsDialog
from creality_nfc.color_from_image import color_from_image_path
from creality_nfc.tag_export import build_tag_export, save_tag_export
from ui.color_presets_menu import show_color_presets
from ui.color_swatch import color_from_tag_field, normalize_hex
from ui.setup_wizard import SetupWizardDialog
from app.bundled_assets import save_bundled_plastic_holder_stls
from ui.app_icon import apply_window_icon, load_header_logo
from ui.tag_holder_links import TagHolderLinksDialog
from ui.components import labeled_row, scrollable_tab, section
from ui.rounded_widgets import rounded_button
from ui.dialog_theme import prepare_toplevel
from ui.messaging import confirm
from ui.theme import BG, ON_HEADER
from ui.post_print_deduct_dialog import DeductRow, ask_post_print_deductions
from ui.chip_duplicate_help import (
    CHIP_DUP_INTRO,
    CHIP_DUP_STEP_HINTS,
    CHIP_DUP_TOOLTIP,
)
from ui.rfid_placement_help import RFID_PLACEMENT_SHORT
from ui.panels.filament_editor_panel import FilamentEditorPanel
from ui.panels.help_panel import HelpPanel
from ui.panels.model_library_panel import ModelLibraryPanel
from ui.panels.printer_device_panel import PrinterDevicePanel
from ui.panels.printer_panel import PrinterDashboardPanel
from ui.panels.settings_panel import SettingsPanel
from ui.panels.spool_panel import SpoolManagerPanel
from ui.system_tray import BackgroundTray, tray_supported
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

        self.reader = CrealityNfcReader()
        apply_window_icon(self)
        self.settings = AppSettings.load(DEFAULT_SETTINGS_PATH)
        from creality_nfc.i18n import set_language

        set_language(self.settings.language or "de")
        from ui.window_geometry import (
            WindowGeometryManager,
            clear_table_dialog_geometries,
            repair_stored_window_geometries,
            set_window_geometry_manager,
        )

        geom_changed = clear_table_dialog_geometries(self.settings.window_geometry)
        geom_changed = repair_stored_window_geometries(
            self.settings.window_geometry,
            screen_w=self.winfo_screenwidth(),
            screen_h=self.winfo_screenheight(),
        ) or geom_changed
        if geom_changed:
            self.settings.save(DEFAULT_SETTINGS_PATH)
        self._window_geom = WindowGeometryManager(self.settings, self._save_settings)
        set_window_geometry_manager(self._window_geom)
        self._window_geom.attach_root(self)
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
        from creality_nfc.print_history import PrintHistoryStore

        self.print_history = PrintHistoryStore(DATA_DIR / "print_history.json")
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
        self._chip_dup_poll_after: str | None = None
        self._last_write_template: dict | None = None
        self._post_print_prompted = False
        self._post_print_deduct_file = ""
        self._shutdown_done = False
        self._reader_poll_after: str | None = None
        self._background_tray: BackgroundTray | None = None
        self._tray_hidden = False
        migrate_legacy_settings()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build_menu()
        # Statusleiste zuerst (unten), dann Kopf + Inhalt — sonst überlappt der Body die Leiste.
        self._build_statusbar()
        self._build_header()
        self._build_body()
        self._build_message_area()

        self._load_materials()
        self.after(300, self._initial_nfc_check)
        self.after(600, self._start_monitor)
        self._update_prompted_tag = ""
        self._update_check_running = False
        if self.settings.check_updates:
            self._schedule_automatic_update_check()
        if self.settings.show_setup_on_startup or not self.settings.setup_completed:
            self.after(900, self._maybe_show_setup_wizard)
        self._schedule_reader_poll()
        self.after(1200, self._sync_creality_watcher)
        from creality_nfc.creality_watch import register_main_app

        register_main_app()

    # ── UI construction ─────────────────────────────────────────────

    def _build_menu(self) -> None:
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        from creality_nfc.i18n import t as _t

        m_file = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("menu.file"), menu=m_file)
        m_import = tk.Menu(m_file, tearoff=0)
        m_file.add_cascade(label=_t("menu.file.import"), menu=m_import)
        if not MATERIAL_DB_PRINTER_ONLY:
            m_import.add_command(label=_t("menu.file.import.cloud"), command=self.sync_database)
        m_import.add_command(label=_t("menu.file.import.printer_ssh"), command=self.sync_from_printer)
        if not MATERIAL_DB_PRINTER_ONLY:
            m_import.add_command(label=_t("menu.file.import.orca"), command=self.import_slicer_profiles)
            m_import.add_command(label=_t("menu.file.import.db_file"), command=self.pick_database)
            m_import.add_command(label=_t("menu.file.import.cloud_merge"), command=self.merge_cloud)
        m_import.add_command(label=_t("menu.file.import.cfs_zip"), command=self.import_cfs_zip)
        m_file.add_separator()
        if not MATERIAL_DB_PRINTER_ONLY:
            m_file.add_command(label=_t("menu.file.db_open"), command=self.pick_database)
            m_file.add_command(label=_t("menu.file.db_save_as"), command=self.save_database_as)
        m_file.add_command(label=_t("menu.file.export_options"), command=self.export_options)
        m_file.add_separator()
        m_file.add_command(label=_t("menu.file.backup_zip"), command=self.backup_data)
        m_file.add_command(label=_t("menu.file.restore_zip"), command=self.restore_data)
        m_file.add_command(label=_t("menu.file.cfs_zip_import"), command=self.import_cfs_zip)
        m_file.add_command(label=_t("menu.file.export_tag"), command=self.export_tag_data)
        m_file.add_command(label=_t("menu.file.history"), command=self.show_print_history)
        m_file.add_command(label=_t("menu.file.format_tag"), command=self.format_tag_quick)
        m_file.add_command(label=_t("menu.file.duplicate_chip"), command=self.duplicate_chip_start)
        m_file.add_separator()
        m_file.add_command(label=_t("menu.file.tray"), command=self._hide_to_tray)
        m_file.add_separator()
        m_file.add_command(label=_t("menu.file.exit"), command=lambda: self._on_close(force=True))

        m_extra = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("menu.nav"), menu=m_extra)
        m_extra.add_command(label=_t("menu.nav.tab.rfid"), command=lambda: self.notebook.select(self.tab_tag))
        m_extra.add_command(label=_t("menu.file.format_tag"), command=self.format_tag_quick)
        m_extra.add_command(label=_t("menu.file.duplicate_chip"), command=self.duplicate_chip_start)
        m_extra.add_command(label=_t("menu.nav.tab.profile"), command=lambda: self.notebook.select(self.tab_profile))
        m_extra.add_command(label=_t("menu.nav.tab.material_db"), command=lambda: self.notebook.select(self.tab_db))
        m_extra.add_command(label=_t("menu.nav.tab.printer"), command=lambda: self.notebook.select(self.tab_printer))
        m_extra.add_command(label=_t("menu.nav.tab.spools"), command=lambda: self.notebook.select(self.tab_spools))
        m_extra.add_command(
            label=_t("menu.nav.tab.library"), command=lambda: self.notebook.select(self.tab_models)
        )
        m_extra.add_command(label=_t("menu.nav.tab.help"), command=lambda: self.notebook.select(self.tab_help))
        m_extra.add_separator()
        m_extra.add_command(label=_t("menu.nav.tag_holder_links"), command=self.open_tag_holder_links)
        m_extra.add_command(label=_t("menu.nav.tab.settings"), command=lambda: self.notebook.select(self.tab_settings))
        m_extra.add_command(label=_t("menu.file.printers"), command=self.open_printer_manager)
        self._cfs_preview_var = tk.BooleanVar(value=False)
        m_extra.add_checkbutton(
            label=_t("menu.nav.cfs_preview"),
            variable=self._cfs_preview_var,
            command=self._toggle_cfs_preview,
        )
        m_extra.add_command(label=_t("menu.nav.check_updates"), command=self.check_updates)
        m_extra.add_command(label=_t("menu.nav.reinstall_setup"), command=self.check_updates_reinstall)

    def _build_header(self) -> None:
        hdr = tk.Frame(self, bg=HEADER)
        hdr.pack(fill="x", side="top")

        row = tk.Frame(hdr, bg=HEADER)
        row.pack(fill="x", padx=28, pady=(14, 16))

        left = tk.Frame(row, bg=HEADER)
        left.pack(side="left", fill="x", expand=True)

        title_row = tk.Frame(left, bg=HEADER)
        title_row.pack(anchor="w", fill="x")
        self._header_logo = load_header_logo(self, size=48)
        if self._header_logo is not None:
            tk.Label(title_row, image=self._header_logo, bg=HEADER).pack(side="left", padx=(0, 12))
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

        self._header_subtitle = tk.Label(
            left,
            text=f"{APP_TAGLINE}  ·  Version {APP_VERSION}",
            bg=HEADER,
            fg=ON_HEADER_SUB,
            font=F_HEADER_SUB,
            justify="left",
            anchor="nw",
            wraplength=820,
        )
        self._header_subtitle.pack(anchor="w", fill="x", pady=(10, 0), ipady=2)

        def _resize_header_subtitle(event: tk.Event | None = None) -> None:
            w = left.winfo_width()
            if w > 120 and hasattr(self, "_header_subtitle"):
                self._header_subtitle.configure(wraplength=max(320, w - 8))

        left.bind("<Configure>", _resize_header_subtitle)

        right = tk.Frame(row, bg=HEADER)
        right.pack(side="right", anchor="n", padx=(16, 0))
        self.db_badge = tk.Label(
            right,
            text=_t("mw.ui.database_loading"),
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

        from creality_nfc.i18n import t as _t

        self.notebook.add(self.tab_tag, text=f" {_t('tab.rfid')} ")
        self.notebook.add(self.tab_profile, text=f" {_t('tab.profile')} ")
        self.notebook.add(self.tab_db, text=f" {_t('tab.material_db')} ")
        self.notebook.add(self.tab_printer, text=f" {_t('tab.printer')} ")
        self.notebook.add(self.tab_spools, text=f" {_t('tab.spools')} ")
        self.notebook.add(self.tab_models, text=f" {_t('tab.library')} ")
        self.notebook.add(self.tab_help, text=f" {_t('tab.help')} ")
        self.notebook.add(self.tab_settings, text=f" {_t('tab.settings')} ")

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
        panel = getattr(self, "_device_panel", None)
        if panel is None:
            return
        if tab is self.tab_printer:
            panel.on_tab_shown()
        else:
            panel.on_tab_hidden()

    def _build_tab_tag(self) -> None:
        root = ttk.Frame(self.tab_tag)
        root.pack(fill="both", expand=True)

        # Feste Aktionsleiste — bleibt sichtbar, kein Überlappen mit Formular
        action_bar = ttk.LabelFrame(root, text=_t("mw.ui.actions"), padding=(14, 12))
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
            text=_t("mw.spool.placeholder_read"),
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
            text=_t("mw.ui.uid"),
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
            ttk.Button(btn_row, text=_t("mw.btn.color"), command=self.pick_color, style="Secondary.TButton"),
            _t("mw.tag.color_pick_tip"),
        ).pack(side="left", padx=(0, 4))
        self._btn_color_presets = tip(
            ttk.Button(btn_row, text=_t("mw.btn.presets"), command=self.show_color_presets, style="Secondary.TButton"),
            _t("mw.tag.color_defaults_tip"),
        )
        self._btn_color_presets.pack(side="left", padx=(0, 4))
        tip(
            ttk.Button(btn_row, text=_t("mw.btn.photo"), command=self.pick_color_from_image, style="Secondary.TButton"),
            _t("mw.tag.color_photo_tip"),
        ).pack(side="left", padx=(0, 8))
        tip(
            ttk.Button(btn_row, text=_t("mw.btn.read_tag"), command=self.read_tag, style="Secondary.TButton"),
            "Aktuellen Inhalt vom NFC-Tag einlesen (UID, Farbe, Gewicht, Filament-ID).",
        ).pack(side="left", padx=(0, 8))
        tip(
            ttk.Button(btn_row, text=_t("mw.btn.write_tag"), command=self.write_tag, style="Accent.TButton"),
            _t("mw.tag.write_tip"),
        ).pack(side="left", padx=(0, 4))
        tip(
            ttk.Button(btn_row, text=_t("mw.btn.format_tag"), command=self.format_tag_quick, style="Secondary.TButton"),
            _t("mw.tag.format_tip"),
        ).pack(side="left", padx=(0, 4))
        tip(
            ttk.Button(btn_row, text=_t("mw.btn.duplicate_chip"), command=self.duplicate_chip_start, style="Secondary.TButton"),
            CHIP_DUP_TOOLTIP,
        ).pack(side="left", padx=(0, 8))
        self._chip_dup_hint_frame = tk.Frame(action_bar, bg=ACCENT_SOFT)
        self._chip_dup_hint_label = tk.Label(
            self._chip_dup_hint_frame,
            text="",
            bg=ACCENT_SOFT,
            fg=ACCENT_LIGHT,
            font=(FONT, 11),
            justify="left",
            anchor="nw",
            wraplength=860,
        )
        self._chip_dup_hint_label.pack(fill="x", padx=12, pady=8)
        self._chip_dup_hint_frame.bind(
            "<Configure>",
            lambda e, lbl=self._chip_dup_hint_label: lbl.configure(
                wraplength=max(280, e.width - 28)
            ),
        )
        tip(
            ttk.Button(btn_row, text=_t("mw.btn.export_tag"), command=self.export_tag_data, style="Secondary.TButton"),
            "Zuletzt gelesene Tag-Daten als JSON speichern.",
        ).pack(side="left", padx=(0, 8))
        tip(
            ttk.Button(btn_row, text=_t("mw.btn.save_spool"), command=self.save_current_spool, style="Secondary.TButton"),
            _t("mw.tip.save_spool"),
        ).pack(side="left")

        self._placement_box = tk.Frame(
            action_bar,
            bg=BG_SUBTLE,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        self._placement_box.pack(fill="x", pady=(12, 2))
        self._placement_hint_label = tk.Label(
            self._placement_box,
            text=RFID_PLACEMENT_SHORT,
            bg=BG_SUBTLE,
            fg=TEXT,
            font=F_BODY,
            justify="left",
            anchor="nw",
            wraplength=880,
        )
        self._placement_hint_label.pack(fill="x", padx=12, pady=10)
        self._placement_box.bind(
            "<Configure>",
            lambda e, lbl=self._placement_hint_label: lbl.configure(
                wraplength=max(280, e.width - 28)
            ),
        )

        _canvas, scroll = scrollable_tab(root)

        sec_reader = section(scroll, _t("mw.section.nfc_reader"))
        r1 = ttk.Frame(sec_reader)
        r1.pack(fill="x", pady=(0, 4))
        tip(
            ttk.Button(r1, text=_t("mw.btn.connect_reader"), command=self.connect_reader, style="Secondary.TButton"),
            _t("mw.tip.connect_reader"),
        ).pack(side="left", padx=(0, 6), pady=2)
        tip(
            ttk.Button(
                r1, text=_t("mw.btn.smartcard_start"), command=self.start_smartcard_service, style="Secondary.TButton"
            ),
            _t("mw.tag.smartcard_start_tip"),
        ).pack(side="left", padx=(0, 6), pady=2)
        tip(
            ttk.Button(r1, text=_t("mw.btn.tag_memory"), command=self.open_tag_tools, style="Secondary.TButton"),
            _t("mw.tag.advanced_tools_tip"),
        ).pack(side="left", pady=2)
        r2 = ttk.Frame(sec_reader)
        r2.pack(fill="x")
        reader_actions: list[tuple[str, object, str]] = [
            (
                _t("mw.btn.holder_stl"),
                lambda: save_bundled_plastic_holder_stls(self),
                _t("mw.tag.holder_links_tip"),
            ),
            (
                "Tag-Halter (Links)…",
                self.open_tag_holder_links,
                _t("mw.tip.holder_links"),
            ),
            (
                _t("mw.tag.choose_printer"),
                self.open_printer_manager,
                _t("mw.tag.choose_printer_tip"),
            ),
        ]
        if not MATERIAL_DB_PRINTER_ONLY:
            reader_actions.append(
                (_t("mw.db.save_as"), self.save_database_as, _t("mw.tip.save_db_json")),
            )
        for text, cmd, help_txt in reader_actions:
            tip(
                ttk.Button(r2, text=text, command=cmd, style="Secondary.TButton"),
                help_txt,
            ).pack(side="left", padx=(0, 6), pady=2)
        tip(
            ttk.Button(
                r2,
                text=_t("mw.btn.same_spool_again"),
                command=self._duplicate_last_tag_template,
                style="Accent.TButton",
            ),
            _t("mw.tip.same_spool_again"),
        ).pack(side="left", padx=(0, 6), pady=2)

        sec_mat = section(scroll, _t("mw.section.filament_for_tag"))
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
        _grid_row(0, _t("mw.label.printer_ip"), ip_wrap, pady=(0, 2))
        ttk.Label(
            form,
            text=_t("mw.tag.same_ip_hint"),
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
            _t("mw.tip.clear_search"),
        ).pack(side="left", padx=(6, 0))
        _grid_row(2, _t("mw.label.search"), search_wrap)

        self.printer_var = tk.StringVar(value=DEFAULT_PRINTER)
        self.brand_var = tk.StringVar()
        self.material_var = tk.StringVar()
        self.weight_var = tk.StringVar(value="1 KG")
        self.selected_profile_var = tk.StringVar(value="—")

        self.printer_combo = ttk.Combobox(
            form, textvariable=self.printer_var, values=list(PRINTER_OPTIONS), state="readonly"
        )
        _grid_row(3, _t("mw.label.printer_on_tag"), self.printer_combo)
        self.printer_combo.bind("<<ComboboxSelected>>", self._on_printer_change)
        saved_printer = normalize_printer_model(
            load_settings().get("printer", DEFAULT_PRINTER)
        )
        self.printer_var.set(saved_printer)
        ttk.Label(
            form,
            text=_t("app.supported_printers_short"),
            style="Muted.TLabel",
            wraplength=520,
            justify="left",
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 6))

        self.brand_combo = ttk.Combobox(form, textvariable=self.brand_var, state="readonly")
        _grid_row(5, _t("mw.label.brand"), self.brand_combo)
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
        _grid_row(6, _t("mw.label.material"), mat_wrap)
        self.material_combo.bind("<<ComboboxSelected>>", self._on_material_selected)

        prof_btns = ttk.Frame(form)
        prof_btns.columnconfigure(0, weight=1)
        prof_btns.columnconfigure(1, weight=1)
        self._btn_edit_profile = tip(
            ttk.Button(
                prof_btns,
                text=_t("mw.btn.edit_profile"),
                command=self.edit_filament,
                style="Secondary.TButton",
            ),
            _t("mw.tip.edit_profile_readonly")
            if MATERIAL_DB_PRINTER_ONLY
            else _t("mw.profile.open_tab"),
        )
        self._btn_edit_profile.grid(row=0, column=0, sticky="ew", padx=(0, 4), pady=2)
        self._btn_new_profile = tip(
            ttk.Button(
                prof_btns,
                text=_t("mw.btn.new_profile"),
                command=self.add_filament,
                style="Secondary.TButton",
            ),
            _t("mw.tip.new_profile"),
        )
        self._btn_new_profile.grid(row=0, column=1, sticky="ew", pady=2)
        if MATERIAL_DB_PRINTER_ONLY:
            self._btn_new_profile.grid_remove()
            self._btn_edit_profile.grid(row=0, column=0, columnspan=2, sticky="ew", padx=0, pady=2)
        tip(
            ttk.Button(
                prof_btns,
                text=_t("mw.btn.load_database"),
                command=self._goto_db_tab,
                style="Secondary.TButton",
            ),
            _t("mw.tip.goto_db_printer")
            if MATERIAL_DB_PRINTER_ONLY
            else _t("mw.tip.goto_db_cloud"),
        ).grid(row=1, column=0, columnspan=2, sticky="ew", pady=2)
        _grid_row(7, _t("mw.label.profile"), prof_btns, pady=(6, 4))

        weight_c = ttk.Combobox(
            form, textvariable=self.weight_var, values=list(WEIGHT_CODES.keys()), state="readonly"
        )
        _grid_row(8, _t("mw.label.weight_tag"), weight_c)

        self.spool_var = tk.StringVar()
        spool_wrap = ttk.Frame(form)
        self.spool_combo = ttk.Combobox(spool_wrap, textvariable=self.spool_var, state="readonly")
        self.spool_combo.pack(side="left", fill="x", expand=True)
        tip(
            ttk.Button(spool_wrap, text="…", width=3, command=self._goto_spools_tab),
            _t("mw.spool.open_tab_tip"),
        ).pack(side="left", padx=(6, 0))
        _grid_row(9, _t("mw.label.my_spool"), spool_wrap)
        self.spool_combo.bind("<<ComboboxSelected>>", self._on_spool_selected)
        self._refresh_spool_combo()

        opts = ttk.LabelFrame(scroll, text=_t("mw.ui.options"), padding=6)
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
            text=_t("settings.auto_read"),
            variable=self.auto_read_var,
            command=self._sync_auto_flags,
        ).grid(row=0, column=0, sticky="w", pady=2)
        ttk.Checkbutton(
            oc,
            text=_t("settings.auto_write"),
            variable=self.auto_write_var,
            command=self._sync_auto_flags,
        ).grid(row=0, column=1, sticky="w", pady=2)
        ttk.Checkbutton(
            oc,
            text=_t("settings.batch_write"),
            variable=self.batch_write_var,
            command=self._sync_batch_flag,
        ).grid(row=1, column=0, sticky="w", pady=2)
        serial_row = ttk.Frame(oc)
        serial_row.grid(row=1, column=1, sticky="ew", pady=2)
        ttk.Label(serial_row, text=_t("mw.ui.sn")).pack(side="left")
        self.serial_var = tk.StringVar(value=self.settings.next_serial_str())
        ttk.Entry(serial_row, textvariable=self.serial_var, width=8).pack(side="left", padx=4)
        ttk.Checkbutton(
            serial_row,
            text=_t("settings.auto_serial"),
            variable=self.auto_serial_var,
            command=self._on_serial_mode_change,
        ).pack(side="left")
        ttk.Checkbutton(
            oc,
            text=_t("settings.auto_sync_spool"),
            variable=self.auto_sync_spool_var,
            command=self._sync_auto_flags,
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=2)

        tip(
            ttk.Button(
                scroll,
                text=_t("mw.label.goto_profile_tab"),
                command=self._goto_profile_tab,
                style="Accent.TButton",
            ),
            _t("mw.profile.view_tip")
            if MATERIAL_DB_PRINTER_ONLY
            else _t("mw.profile.edit_tip"),
        ).pack(anchor="w", pady=(8, 4))

        sec_diag = section(scroll, _t("mw.section.tag_raw"))
        sec_diag.pack(fill="both", expand=True, pady=(8, 4))
        diag_btns = ttk.Frame(sec_diag)
        diag_btns.pack(fill="x", pady=(0, 4))
        tip(
            ttk.Button(
                diag_btns,
                text=_t("mw.btn.read_now"),
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
            _t("mw.tag.read_hint"),
        )
        self.tag_diag_text.config(state="disabled")

    def _build_tab_profile(self) -> None:
        root = ttk.Frame(self.tab_profile)
        root.pack(fill="both", expand=True)
        ttk.Label(
            root,
            text=_t("mw.profile.params_hint"),
            style="Muted.TLabel",
            wraplength=900,
        ).pack(anchor="w", padx=8, pady=(8, 4))
        empty_db: dict = {"result": {"list": [], "count": 0}}
        self._filament_panel = FilamentEditorPanel(
            root,
            self.db_data if self.db_data else empty_db,
            self._on_filament_saved,
            readonly=MATERIAL_DB_PRINTER_ONLY,
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

        sec = section(top, _t("mw.section.material_db_printer"))
        sec.grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 2))
        if MATERIAL_DB_PRINTER_ONLY:
            intro = (
                _t("mw.profile.db_printer_only_intro")
                + " "
                + _t("mw.profile.read_only_hint")
            )
        else:
            intro = (
                _t("mw.profile.db_safe_mode_intro")
                + " "
                + _t("mw.profile.printer_creality_print")
            )
        ttk.Label(sec, text=intro, style="Muted.TLabel", wraplength=820).pack(
            anchor="w", pady=(0, 6)
        )
        self.db_label = ttk.Label(sec, text=_t("mw.ui.db_loading"), style="Muted.TLabel", wraplength=800)
        self.db_label.pack(anchor="w", pady=(0, 6))

        grid = ttk.Frame(sec)
        grid.pack(fill="x")
        if MATERIAL_DB_PRINTER_ONLY:
            actions = [
                (
                    _t("mw.db.from_printer_ssh"),
                    self.sync_from_printer,
                    _t("mw.tip.db_ssh"),
                ),
                (
                    _t("mw.db.cfs_zip"),
                    self.import_cfs_zip,
                    "Backup-ZIP mit Datenbank und Einstellungen importieren.",
                ),
            ]
        else:
            actions = [
                (
                    _t("mw.db.from_cloud"),
                    self.sync_database,
                    _t("mw.tip.db_cloud"),
                ),
                (
                    _t("mw.db.from_printer_ssh"),
                    self.sync_from_printer,
                    _t("mw.tip.db_ssh_readonly"),
                ),
                (
                    _t("mw.db.cloud_merge"),
                    self.merge_cloud,
                    _t("mw.db.cloud_merge_tip"),
                ),
                (_t("mw.db.open_file"), self.pick_database, _t("mw.db.open_file_tip")),
                (
                    _t("mw.db.slicer_import"),
                    self.import_slicer_profiles,
                    "Orca/Creality JSON — Notizen: {\"id\",\"vendor\",\"type\",\"name\"}.",
                ),
                (_t("mw.db.save_as"), self.save_database_as, "Datenbank als JSON-Datei exportieren."),
                (
                    _t("mw.db.cfs_zip"),
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

        list_sec = section(top, _t("mw.section.all_profiles"))
        list_sec.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        self._profile_list_title = ttk.Label(
            list_sec,
            text=_t("mw.ui.profile_list_empty"),
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
            _t("mw.db.reset_filter"),
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
            ("name", _t("mw.label.material"), 220),
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
                text=_t("mw.db.adopt_for_rfid"),
                command=self._apply_profile_tree_selection,
                style="Accent.TButton",
            ),
            _t("mw.db.adopt_rfid_tip"),
        ).pack(side="left", padx=(0, 8))
        tip(
            ttk.Button(
                tree_btns,
                text=_t("mw.btn.edit_profile"),
                command=self._edit_profile_tree_selection,
                style="Secondary.TButton",
            ),
            _t("mw.db.open_profile_tab_tip"),
        ).pack(side="left")

        foot = ttk.Frame(top)
        foot.grid(row=2, column=0, sticky="ew", padx=4, pady=(0, 6))
        foot_row = ttk.Frame(foot)
        foot_row.pack(fill="x")
        ttk.Label(
            foot_row,
            text=_t("mw.ui.db_list_hint"),
            style="Muted.TLabel",
        ).pack(side="left")
        tip(
            ttk.Button(
                foot_row,
                text=_t("mw.ui.goto_printer_ssh"),
                command=lambda: self.notebook.select(self.tab_printer),
                style="Secondary.TButton",
            ),
            _t("mw.tip.printer_ssh"),
        ).pack(side="right")

    def _build_tab_printer(self) -> None:
        self._device_panel = PrinterDevicePanel(self.tab_printer, self)
        self._printer_device_panel = self._device_panel
        self._device_panel.pack(fill="both", expand=True)
        self._printer_dashboard = PrinterDashboardPanel(self.tab_printer, self)
        self._printer_dashboard.pack(fill="x", padx=4, pady=(0, 8))
        self._cfs_preview_var.set(False)
        self._device_panel.set_cfs_preview(None)

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
        self.status_label = ttk.Label(left, text=_t("scard.state.ok"), style="Footer.TLabel")
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
            _t("mw.settings.open_tip"),
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
            _t("mw.tip.smartcard_help"),
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
        self._pack_statusbar_actions()
        self._apply_nfc_ui()

    def _pack_statusbar_actions(self) -> None:
        """Protokoll und Einstellungen immer sichtbar (rechts unten)."""
        if not self.btn_log.winfo_ismapped():
            self.btn_log.pack(side="right", padx=(6, 0))
        if not self.btn_settings.winfo_ismapped():
            self.btn_settings.pack(side="right", padx=(6, 0))

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
            ttk.Button(cf_btns, text=_t("btn.yes"), command=self._on_confirm_yes, style="Accent.TButton"),
            _t("mw.confirm_run_tip"),
        )
        self._btn_confirm_yes.pack(side="left", padx=(0, 6))
        self._btn_confirm_no = tip(
            ttk.Button(cf_btns, text=_t("btn.no"), command=self._on_confirm_no, style="Secondary.TButton"),
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
            text=_t("statusbar.log"),
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
            self.btn_log.configure(text=_t("statusbar.log"))
        else:
            self._log_panel.pack(fill="x", side="bottom", before=self._statusbar_frame)
            self._log_visible = True
            self.btn_log.configure(text=_t("statusbar.log") + " ▾")

    def notify(self, text: str, level: str = "info") -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        icons = {"info": "ℹ", "ok": "✓", "warn": "⚠", "error": "✗"}
        line = f"[{ts}] {icons.get(level, '·')} {text}\n"
        self.msg_log.config(state="normal")
        self.msg_log.insert("end", line)
        self.msg_log.see("end")
        self.msg_log.config(state="disabled")
        self._set_status(text.replace("\n", " ")[:72], level)

    def notify_print_job_alert(self, title: str, detail: str, level: str = "warn") -> None:
        """Pause/Fehler am K2: Status, Protokoll, optional Dialog + Windows-Toast."""
        if not getattr(self.settings, "alert_print_pause_error", True):
            return
        summary = f"{title} — {detail.splitlines()[0]}"
        self.notify(summary, level)
        try:
            self.bell()
        except tk.TclError:
            pass
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
        except tk.TclError:
            pass
        if getattr(self.settings, "alert_print_popup", True):
            self.show_alert_dialog(detail, level=level, title=title)
        if getattr(self.settings, "alert_print_windows_toast", True):

            def _toast() -> None:
                from creality_nfc.windows_toast import show_windows_toast

                show_windows_toast(title, detail.replace("\n", " — "))

            threading.Thread(target=_toast, name="print-toast", daemon=True).start()

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
        self.notify(_t("mw.notify.settings_saved"), "ok")
        self._sync_creality_watcher()
        if not settings.tray_run_in_background:
            self._stop_background_tray()
            if self._tray_hidden:
                self._show_from_tray()
        if settings.check_updates:
            self._update_prompted_tag = ""
            self.after(1000, self._check_updates_quiet)

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
            self.btn_scard.config(text=_t("mw.btn.smartcard_start"))
            self.btn_scard.pack_forget()
        elif state == "no_reader":
            self.scard_dot.config(fg=WARN)
            self.btn_scard.pack_forget()
        elif state == "service_stuck":
            self.scard_dot.config(fg=ERR)
            self.btn_scard.config(text=_t("mw.btn.smartcard_restart_uac"))
            self._pack_scard_buttons()
        else:
            self.scard_dot.config(fg=ERR)
            self.btn_scard.config(text=_t("mw.btn.smartcard_start"))
            self._pack_scard_buttons()
        self.btn_scard_help.pack_forget()
        self.btn_scard.pack_forget()
        if state in ("service_stuck", "service_down"):
            self._pack_scard_buttons()
            self.btn_scard_help.pack(side="right", padx=(0, 8), before=self.btn_scard)
        else:
            self.btn_scard_help.pack(side="right", padx=(0, 8), before=self.btn_settings)
        self._pack_statusbar_actions()
        return state

    def _pack_scard_buttons(self) -> None:
        if not self.btn_scard.winfo_ismapped():
            self.btn_scard.pack(side="right", padx=(0, 8), before=self.btn_settings)

    def _initial_nfc_check(self) -> None:
        state = self._apply_nfc_ui()
        if state == "ok":
            self.connect_reader(show_errors=False)
        elif state == "no_reader":
            self._set_status(_t("mw.notify.smartcard_ok_connect_usb"), "warn")
        elif state == "service_stuck":
            self._set_status(_t("mw.smartcard.hangs_status"), "error")
            if not self._scard_help_shown:
                self._scard_help_shown = True
                self.notify(
                    _t("mw.smartcard.hangs_explanation"),
                    "warn",
                )
        else:
            self._set_status(_t("mw.notify.smartcard_off"), "error")

    def show_smartcard_help(self) -> None:
        self.notebook.select(self.tab_help)
        self.notify(_t("mw.notify.smartcard_help"), "info")

    def _start_smartcard_from_bar(self) -> None:
        self.start_smartcard_service()

    def _nfc_error_message(self, exc: NfcReaderError) -> tuple[str, str, bool]:
        """Returns (short status text, dialog text, offer scard action)."""
        if str(exc) == "SMARTCARD_STOPPED":
            state = probe_pcsc()
            if state == "service_stuck":
                return (_t("mw.smartcard.hangs_restart_status"), scard_status_message(state), True)
            return (_t("mw.notify.smartcard_off"), scard_status_message(state), True)
        msg = str(exc)
        low = msg.lower()
        if "block " in low and "lesen fehlgeschlagen" in low:
            return (msg.split("\n", 1)[0][:64], msg, False)
        if "80100069" in msg or "entfernt wurde" in low or "removed card" in low:
            return (
                _t("mw.smartcard.no_tag_short"),
                _t("mw.smartcard.no_tag_long"),
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
            self._set_status(_t("mw.notify.smartcard_off"), "error")
            self.ask_confirm(msg + _t("mw.notify.start_now_q"), self.start_smartcard_service)
        elif state == "service_stuck":
            self._set_status(_t("mw.smartcard.hangs_short"), "error")
            self.ask_confirm(msg + _t("mw.notify.restart_now_q"), self.start_smartcard_service)
        else:
            self._set_status(msg.split("\n")[0][:64], "warn")
            self.notify(msg, "warn")
            self.show_alert_dialog(
                msg + "\n\nDanach im RFID-Tab „Reader verbinden“.",
                "warn",
                title=_t("mw.notify.title_nfc"),
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
                self.ask_confirm(detail + _t("mw.confirm.run_action"), self.start_smartcard_service)
            else:
                self.show_alert_dialog(detail, "error", title=_t("mw.notify.title_nfc_short"))
            return
        msg = str(exc) or _t("error.unknown")
        self._set_status(msg[:70], "error")
        if silent:
            return
        self.notify(msg, "error")
        self.show_alert_dialog(msg, "error", title=_t("mw.notify.title_nfc_short"))

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
        from creality_nfc.creality_watch import sync_creality_watch

        started, msg = sync_creality_watch(self.settings.launch_with_creality_print)
        if self.settings.launch_with_creality_print:
            from creality_nfc.creality_watch import watcher_is_running

            if watcher_is_running():
                msg = f"{msg}{_t('mw.watcher.active_short')}" if msg else _t("mw.watcher.active")
            elif msg and "konnte nicht" not in msg and "could not" not in msg:
                msg = f"{msg}{_t('mw.watcher.inactive_short')}"
        if msg:
            self._set_status(msg, "ok" if started or _t("mw.status.active_keyword") in msg else "warn")

    def _save_settings(self) -> None:
        self.settings.save(DEFAULT_SETTINGS_PATH)

    def _update_db_label(self) -> None:
        n = len(self.profiles)
        if self._demo_mode:
            txt = _t("mw.status.demo_materials", n=n)
            self.db_label.config(text=txt)
            self.db_badge.config(text=txt, fg=ON_HEADER_WARN, bg=HEADER_SURFACE)
            return
        labels = {
            "cloud": "Creality Cloud",
            "printer": _t("mw.src.printer"),
            "file": "Datei",
            "merged": "gemergt",
            "local": "lokal",
        }
        src = labels.get(self._db_source, "?")
        name = self.db_path.name if self.db_path else "?"
        txt = _t("mw.status.materials_ok", n=n, src=src, name=name)
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
        DATA_DIR.mkdir(parents=True, exist_ok=True)
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
            "name": _t("mw.label.material"),
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
        try:
            yview = self._profile_tree.yview()
        except tk.TclError:
            yview = (0.0, 1.0)
        sel = list(self._profile_tree.selection())
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
                text=_t("mw.profile.demo_banner", shown=shown, total=total)
            )
        elif q:
            self._profile_list_title.config(text=f"{shown} von {total} Profilen (gefiltert)")
        else:
            self._profile_list_title.config(text=_t("mw.profile.all_count", total=total))
        self._update_profile_tree_headings()
        restore = [i for i in sel if self._profile_tree.exists(i)]
        if restore:
            self._profile_tree.selection_set(restore)
        try:
            self._profile_tree.yview_moveto(yview[0])
        except tk.TclError:
            pass

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
            from creality_nfc.i18n import t as _t
            self.notify(_t("notify.select_profile_first"), "warn")
            return
        self._select_profile_in_ui(profile)
        self.notebook.select(self.tab_tag)
        self.notify(_t("mw.notify.rfid_tag_profile", brand=profile.brand, name=profile.name), "ok")

    def _edit_profile_tree_selection(self) -> None:
        profile = self._profile_from_tree_selection()
        if not profile:
            from creality_nfc.i18n import t as _t
            self.notify(_t("notify.select_profile_first"), "warn")
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
            from creality_nfc.i18n import t as _t
            self.notify(_t("notify.task_running"), "warn")
            return
        self._bg_job_running = True
        self._set_status(f"{label}…", "info")
        self.notify(_t("mw.notify.task_duration", label=label), "info")

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
            self._set_status(_t("mw.status.task_failed", label=label), "error")
            self.notify(str(err), "error")
            messagebox.showerror(APP_NAME, f"{label}\n\n{err}")
            return
        if on_ok:
            on_ok(result)
        else:
            self._set_status(_t("mw.status.task_ok", label=label), "ok")
            self.notify(_t("mw.notify.task_done", label=label), "ok")

    def sync_database(self) -> None:
        if MATERIAL_DB_PRINTER_ONLY:
            self.notify(_t("mw.notify.cloud_import_disabled"), "warn")
            return
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
                    msg += "\n" + _t("mw.db.protected_skipped", n=skipped)
            else:
                self._apply_database(data, "cloud")
                n = len(self.profiles)
                msg = _t("mw.notify.cloud_loaded", n=n)
            self._set_status(_t("mw.status.cloud_ok"), "ok")
            self.notify(msg, "ok")
            messagebox.showinfo(APP_NAME,  + _t("mw.notify.printer_line", printer=printer))

        self._run_bg_job(f"Creality Cloud ({printer})", work, on_ok=on_ok)

    def merge_cloud(self) -> None:
        if MATERIAL_DB_PRINTER_ONLY:
            self.notify(_t("mw.notify.cloud_merge_disabled"), "warn")
            return
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
            self._set_status(_t("mw.status.merge_ok", total=total), "ok")
            extra = ("\n" + _t("mw.db.protected_short", n=skipped)) if skipped else ""
            self.notify(_t("mw.notify.merge_result", added=added, updated=updated, total=total, extra=extra), "ok")
            messagebox.showinfo(
                APP_NAME,
                _t("mw.db.cloud_merged")
                + _t("mw.db.cloud_merged_stats", added=added, updated=updated, total=total, extra=extra),
            )

        self._run_bg_job(f"Cloud mergen ({printer})", work, on_ok=on_ok)

    def _ssh_credentials(self, printer: str, *, quiet: bool = False) -> tuple[str, str] | None:
        from creality_nfc.printer_ssh import default_password, normalize_host

        host = normalize_host(self.ssh_host_var.get())
        if not host:
            msg = (
                _t("mw.notify.enter_ip_msg")
            )
            if quiet:
                from creality_nfc.i18n import t as _t
                self.notify(_t("notify.no_printer_ip"), "warn")
            else:
                self.notify(msg.replace("\n", " "), "warn")
                messagebox.showwarning(APP_NAME, msg)
            return None
        password = self.ssh_pass_var.get() or default_password(printer)
        try:
            save_settings(host, password, printer)
        except Exception as exc:
            self.notify(_t("mw.notify.printer_settings_not_saved", exc=exc), "warn")
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
                    _t("mw.ssh.port_unreachable", host=host)
                    + "\n"
                    + _t("mw.ssh.check_hint")
                )
            return work(host, password, printer)

        self._run_bg_job(f"{label} → {host}", work_wrap, on_ok=on_ok)

    def sync_from_printer(self) -> None:
        def work(host: str, password: str, printer: str):
            return download_database_from_printer(host, password, printer)

        def on_ok(data: dict) -> None:
            if MATERIAL_DB_PRINTER_ONLY:
                self._apply_database(data, "printer")
                cache = self.db_path.name if self.db_path else "data/"
                msg = (
                    _t("mw.sync.loaded_profiles", n=len(self.profiles))
                    + "\n"
                    + _t("mw.sync.cache_saved", cache=cache)
                )
            elif self.db_data and self.db_data.get("result", {}).get("list"):
                merged = merge_databases(self.db_data, data, prefer="cloud")
                added, updated, total, skipped = merge_stats(self.db_data, data)
                self._apply_database(merged, "printer")
                msg = _t("mw.sync.merged_summary", total=total, added=added, updated=updated)
                if skipped:
                    msg += "\n" + _t("mw.db.protected_skipped", n=skipped)
            else:
                self._apply_database(data, "printer")
                msg = _t("mw.sync.loaded_profiles", n=len(self.profiles))
            self._set_status(_t("mw.sync.printer_db_ok"), "ok")
            self.notify(msg, "ok")
            messagebox.showinfo(APP_NAME, msg)

        self._run_ssh_job(_t("mw.job.from_printer"), work, on_ok=on_ok)

    def pick_database(self) -> None:
        if MATERIAL_DB_PRINTER_ONLY:
            self.notify(_t("mw.notify.file_import_disabled"), "warn")
            return
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json"), ("Alle", "*.*")])
        if not path:
            return
        try:
            self._apply_database(load_database_raw(Path(path)), "file")
            self.notify(_t("mw.notify.profiles_loaded", n=len(self.profiles)))
        except Exception as exc:
            self.notify(str(exc), "error")

    def import_slicer_profiles(self) -> None:
        """OrcaSlicer/Creality-Print Filament-JSONs in die Material-DB."""
        if MATERIAL_DB_PRINTER_ONLY:
            self.notify(_t("mw.notify.slicer_import_disabled"), "warn")
            return
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
            _t("mw.slicer.processed_summary", n=len(profiles), added=added, updated=updated)
            + "\n\n"
            + _t("mw.local_save_only"),
            parent=self,
        )

    def save_database_as(self) -> None:
        if MATERIAL_DB_PRINTER_ONLY:
            self.notify(_t("mw.notify.save_db_disabled"), "warn")
            return
        if not self.db_data:
            self.notify(_t("mw.notify.no_db_loaded"))
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("JSON", "*.json")], initialfile="material_database.json"
        )
        if path:
            save_database(Path(path), self.db_data)
            self.notify(path)

    def export_options(self) -> None:
        if not self.db_data:
            self.notify(_t("mw.notify.load_db_first"))
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
                _t("mw.db.not_loaded_yet")
                + "\n\n"
                + _t("mw.no_db_hint")
                + _t("mw.db.then_merge")
            )
            self.notify(_t("mw.db.load_first"), "warn")
            messagebox.showwarning(APP_NAME, msg)
            self.notebook.select(self.tab_db)
            return False
        return True

    def _apply_filament_db_state(self, db_data: dict) -> None:
        self.db_data = db_data
        self._save_db()
        self.profiles = profiles_from_db(self.db_data)
        self._refresh_combos()
        self._update_db_label()
        self._refresh_profile_list()
        self._sync_editor_to_selection()

    def _on_filament_saved(self, db_data: dict) -> None:
        self._apply_filament_db_state(db_data)

    def _sync_filament_panel_db(self) -> None:
        if hasattr(self, "_filament_panel") and self.db_data:
            self._filament_panel.set_db_data(self.db_data)

    def add_filament(self) -> None:
        if MATERIAL_DB_PRINTER_ONLY:
            self.notify(_t("mw.notify.new_profiles_printer_only"), "warn")
            return
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
            from creality_nfc.i18n import t as _t
            self.notify(_t("notify.no_brand_material"), "warn")
            self.notebook.select(self.tab_tag)
            return
        self._goto_profile_tab()

    def _save_db(self) -> None:
        if MATERIAL_DB_PRINTER_ONLY:
            return
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
                    text += _t("mw.profile.dup_hint", dup=dup)
            self.selected_profile_var.set(text)
        else:
            self.selected_profile_var.set(_t("mw.profile.none_selected"))

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
        sp.printer = printer_int_to_display(self.printer_var.get().strip())
        if not sp.label or sp.label in (_t("mw.label.new_spool"), _t("mw.label.spool_default")):
            sp.label = format_spool_label(profile.brand, profile.name)[:80]

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
            return _t("mw.spools.updated", label=existing.label)

        active = self.inventory.get(self._active_spool_id) if self._active_spool_id else None
        if active and not active.tag_uid:
            self._fill_spool_from_tag(active, uid, profile, serial)
            self.inventory.update(active)
            self.apply_spool(active)
            self._spool_panel.reload()
            self._spool_panel.select_spool(active.id)
            return _t("mw.spools.tag_linked_short", label=active.label)

        sp = Spool(
            id=SpoolInventory.new_id(),
            label=format_spool_label(profile.brand, profile.name)[:80],
            brand=profile.brand,
            material_name=profile.name,
            filament_id=profile.filament_id,
            color_hex=self.color_hex,
            weight=self.weight_var.get(),
            printer=printer_int_to_display(self.printer_var.get().strip()),
            serial=serial,
            tag_uid=uid,
        )
        self.inventory.add(sp)
        self.apply_spool(sp)
        self._spool_panel.reload()
        self._spool_panel.select_spool(sp.id)
        return _t("mw.spools.created_new", label=sp.label)

    def spool_from_form(self) -> Spool:
        profile = self._selected_profile()
        uid = self.uid_label.cget("text").strip()
        if profile:
            label = format_spool_label(profile.brand, profile.name)[:80]
            brand = profile.brand
            material = profile.name
            fid = profile.filament_id
        else:
            label = _t("mw.label.new_spool")
            brand = self.brand_var.get()
            material = self.material_var.get()
            fid = ""
        return Spool(
            id=self._active_spool_id or SpoolInventory.new_id(),
            label=label,
            brand=brand,
            material_name=material,
            filament_id=fid,
            color_hex=self.color_hex,
            weight=self.weight_var.get(),
            printer=printer_int_to_display(self.printer_var.get().strip()),
            serial=self.serial_var.get().strip() or "000001",
            tag_uid="" if uid == "—" else uid,
        )

    def _prefill_form_from_spool_for_write(self, spool: Spool) -> None:
        """RFID-Formular für Schreiben befüllen, ohne die Tag-leer-Anzeige oben zu überschreiben."""
        self._apply_spool_rfid_fields(spool)

    def _prompt_select_material_for_write(self) -> None:
        self._set_status(_t("mw.tag.no_material"), "warn")
        self.notify(
            _t("mw.tag.no_brand_material"),
            "warn",
        )
        hint = (
            _t("mw.tag.choose_filament_first")
            + _t("mw.tag.choose_filament_spool_hint")
            + _t("mw.tag.clear_search_hint")
            + _t("mw.tag.then_write_again")
        )
        messagebox.showwarning(
            APP_NAME,
            _t("mw.tag.no_filament_chosen", hint=hint),
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
            self._set_status(_t("mw.status.spool_with_profile", label=spool.label, name=prof.name), "ok")
        elif spool.filament_id:
            self._set_status(
                _t("mw.tag.spool_ready", label=spool.label, filament_id=spool.filament_id),
                "ok",
            )
        else:
            self._set_status(_t("mw.status.spool_only", label=spool.label), "ok")

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
            msg += _t("mw.cfs.no_exact_db")
        self._set_status(msg, "ok" if fid else "warn")
        self.notify(msg, "ok" if fid else "warn")
        sp = find_spool_for_slot(self.inventory, slot)
        if sp:
            from creality_nfc.spool_passport import sync_passport_from_cfs_slot

            pname = self.printer_var.get().strip() if hasattr(self, "printer_var") else ""
            res = sync_passport_from_cfs_slot(sp, slot, printer_name=pname)
            if res.updated_fields:
                self.inventory.save()
            for w in res.warnings:
                self.notify(w, "warn")
            self.apply_spool(sp)

    def bind_cfs_slot_dialog(self, slot_index: int, slot: CfsSlotInfo) -> None:
        """CFS-Slot mit Spule aus „Meine Spulen“ verknüpfen."""
        from ui.dialog_theme import prepare_toplevel

        dlg = tk.Toplevel(self)
        dlg.title(_t("mw.cfs.bind_title", label=slot.label))
        prepare_toplevel(
            dlg, self, width=420, height=280, geometry_key="cfs_bind_spool"
        )

        ttk.Label(
            dlg,
            text=_t("mw.cfs.bind_prompt", slot=slot_label(slot_index), display=slot.display),
            wraplength=380,
        ).pack(anchor="w", padx=12, pady=(12, 8))

        choices = [("", _t("mw.choose_spool_placeholder"))]
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
                    _t("mw.spool.no_match"),
                    "warn",
                )
                return
            bind_slot(self.inventory, sp.id, slot_index)
            self._spool_panel.reload()
            if hasattr(self, "_printer_device_panel"):
                self._printer_device_panel.cfs_dashboard.set_inventory(self.inventory)
            self.notify(_t("mw.notify.slot_linked", slot=slot_label(slot_index), label=sp.label), "ok")
            dlg.destroy()

        def _save() -> None:
            sid = id_map.get(var.get())
            if not sid:
                from creality_nfc.i18n import t as _t
                self.notify(_t("notify.select_spool"), "warn")
                return
            bind_slot(self.inventory, sid, slot_index)
            self._spool_panel.reload()
            if hasattr(self, "_printer_device_panel"):
                self._printer_device_panel.cfs_dashboard.set_inventory(self.inventory)
            sp = self.inventory.get(sid)
            self.notify(_t("mw.notify.slot_linked", slot=slot_label(slot_index), label=sp.label if sp else sid), "ok")
            dlg.destroy()

        row = ttk.Frame(dlg)
        row.pack(fill="x", padx=12, pady=12)
        ttk.Button(row, text=_t("mw.btn.auto"), command=_auto, style="Secondary.TButton").pack(
            side="left", padx=(0, 6)
        )
        ttk.Button(row, text=_t("mw.btn.assign"), command=_save, style="Accent.TButton").pack(side="right")

    def _gcode_entry_for_name(self, state: dict, filename: str) -> dict | None:
        if not filename:
            return None
        name = filename.replace("\\", "/").rsplit("/", 1)[-1].lower()
        for entry in parse_gcode_files(state):
            en = str(entry.get("name") or "").lower()
            if en == name or name in en:
                return entry
        return None

    def _printer_cfs_context(self) -> tuple[dict, list[CfsSlotInfo]]:
        """Aktueller Drucker-State und CFS-Slots (falls Tab verbunden)."""
        from creality_nfc.cfs_layout import parse_cfs_layout

        state: dict = {}
        cfs_slots: list[CfsSlotInfo] = []
        panel = getattr(self, "_printer_device_panel", None)
        if panel is not None:
            cfs_slots = list(getattr(panel, "_cfs_slots", []) or [])
            state = dict(getattr(panel, "_printer_state", {}) or {})
        if not cfs_slots and state:
            cfs_slots = parse_cfs_layout(state).all_slots()
        if not cfs_slots:
            cfs_slots = parse_cfs_layout({}).all_slots()
        return state, cfs_slots

    def _collect_post_print_deduct_rows(
        self,
        filename: str,
        state: dict,
        cfs_slots: list[CfsSlotInfo],
        *,
        slot_hint: int | None = None,
        file_entry: dict | None = None,
    ) -> list[DeductRow]:
        """Zeilen für Verbrauchs-Dialog (G-Code + verknüpfte Spulen)."""
        fname = (filename or "").strip()
        if not fname or not cfs_slots:
            return []
        local_gcode = resolve_local_gcode_path(fname)
        from creality_nfc.cfs_feed import find_loaded_flat_index

        loaded_slot = find_loaded_flat_index(state, cfs_slots) if state and cfs_slots else None
        prefer_slot = slot_hint if slot_hint is not None else loaded_slot
        gcode_map = primary_gcode_slot_mapping(
            state,
            fname,
            cfs_slots,
            file_entry=file_entry,
            prefer_slot_index=prefer_slot,
        )
        gcode_slot = gcode_map[0] if gcode_map else None
        use_slot = gcode_slot if gcode_slot is not None else prefer_slot

        dialog_rows: list[DeductRow] = []
        for usage in build_slot_usage_plan(
            state,
            fname,
            cfs_slots,
            file_entry=file_entry,
            loaded_slot_index=prefer_slot,
        ):
            sp = find_spool_for_deduct(
                self.inventory,
                cfs_slots,
                usage.slot_index,
                usage.spec,
                gcode_path=fname,
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
                    or material_hint_from_gcode_path(fname),
                    default_grams=usage.grams,
                    source=usage.source,
                    cfs_filament=cfs_name,
                )
            )

        if not dialog_rows and use_slot is not None and 0 <= use_slot < len(cfs_slots):
            spec = gcode_map[1] if gcode_map else None
            sp = find_spool_for_deduct(
                self.inventory,
                cfs_slots,
                use_slot,
                spec,
                gcode_path=fname,
            )
            sl = cfs_slots[use_slot]
            cfs_name = f"{sl.vendor} {sl.name}".strip() or sl.material_type or ""
            slot_lbl = sl.label
            if sp is not None:
                default = self.settings.default_post_print_deduct_g
                source_hint = ""
                if state or fname:
                    est = estimate_grams_for_slot(
                        state,
                        fname,
                        sl.index,
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
                        slot_label=slot_lbl,
                        spool_label=sp.label,
                        cfs_filament=cfs_name,
                        color_hex=spec.color_hex if spec else None,
                        material=(
                            (spec.material_type if spec else None)
                            or material_hint_from_gcode_path(fname)
                        ),
                        default_grams=default or 50,
                        source=source_hint or "G-Code → Slot",
                    )
                )

        if not dialog_rows and use_slot is not None and 0 <= use_slot < len(cfs_slots):
            from creality_nfc.gcode_filament import total_job_filament_grams

            sl = cfs_slots[use_slot]
            sp = find_spool_for_deduct(
                self.inventory,
                cfs_slots,
                use_slot,
                gcode_map[1] if gcode_map else None,
                gcode_path=fname,
            )
            est = total_job_filament_grams(
                state,
                fname,
                file_entry=file_entry,
                local_path=local_gcode,
            )
            default_g = int(est[0]) if est else 0
            if default_g <= 0:
                default_g = self.settings.default_post_print_deduct_g or 50
            if sp is not None:
                cfs_name = f"{sl.vendor} {sl.name}".strip() or sl.material_type or ""
                spec = gcode_map[1] if gcode_map else None
                dialog_rows.append(
                    DeductRow(
                        spool_id=sp.id,
                        slot_label=sl.label,
                        spool_label=sp.label,
                        cfs_filament=cfs_name,
                        color_hex=spec.color_hex if spec else None,
                        material=(
                            (spec.material_type if spec else None)
                            or material_hint_from_gcode_path(fname)
                        ),
                        default_grams=default_g,
                        source=est[1] if est else _t("mw.deduct.estimate_source"),
                    )
                )
        return dialog_rows

    def _apply_deductions_to_spools(
        self,
        deductions: list[tuple[str, int]],
        *,
        note: str,
    ) -> None:
        thr = self.settings.low_filament_threshold_g
        low_msgs: list[str] = []
        for spool_id, grams in deductions:
            live = self.inventory.get(spool_id)
            if not live or grams <= 0:
                continue
            deduct_grams(live, grams, note=note[:60])
            self.inventory.update(live)
            if is_low_filament(live, thr):
                low_msgs.append(f"{live.label}: {live.remaining_g} g")
        self.inventory.save()
        self._spool_panel.reload()
        self._refresh_spool_combo()
        if low_msgs:
            self.notify(
                "Abgezogen. Rest niedrig:\n" + "\n".join(low_msgs),
                "warn",
            )
            if getattr(self.settings, "alert_low_filament_toast", True):
                from creality_nfc.desktop_notify import show_desktop_notification

                show_desktop_notification(
                    "Filament niedrig",
                    "\n".join(low_msgs),
                    settings=self.settings,
                )
        else:
            self.notify(_t("mw.notify.deduct_done", n=len(deductions)), "ok")

    def retroactive_deduct_from_history(self, record) -> None:
        """Verbrauch für einen Historie-Eintrag nachträglich abziehen."""
        from creality_nfc.cfs_adopt import SLOT_LABELS
        from creality_nfc.print_history import PrintJobRecord

        if not isinstance(record, PrintJobRecord):
            return
        fname = (record.filename or "").strip()
        if not fname:
            self.notify(
                _t("mw.deduct.retro_no_filename")
                + _t("mw.deduct.retro_manual_hint"),
                "warn",
            )
            return

        state, cfs_slots = self._printer_cfs_context()
        file_entry = self._gcode_entry_for_name(state, fname)
        slot_hint = record.cfs_slot
        dialog_rows = self._collect_post_print_deduct_rows(
            fname,
            state,
            cfs_slots,
            slot_hint=slot_hint,
            file_entry=file_entry,
        )

        if not dialog_rows and record.spool_id:
            sp = self.inventory.get(record.spool_id)
            if sp is not None:
                default = (
                    record.estimated_total_g
                    or self.settings.default_post_print_deduct_g
                    or 50
                )
                slot_lbl = record.cfs_slot_label or (
                    SLOT_LABELS[record.cfs_slot]
                    if record.cfs_slot is not None
                    else "—"
                )
                dialog_rows = [
                    DeductRow(
                        spool_id=sp.id,
                        slot_label=slot_lbl,
                        spool_label=sp.label,
                        color_hex=sp.color_hex,
                        material=sp.material_name or None,
                        default_grams=int(default),
                        source="Historie / Spule",
                        cfs_filament="",
                    )
                ]

        if not dialog_rows:
            self._retroactive_deduct_pick_spool(record)
            return

        short = fname.replace("\\", "/").rsplit("/", 1)[-1]
        title_hint = f" (bisher: {record.deducted_g} g)" if record.deducted_g else ""
        deductions = ask_post_print_deductions(
            self,
            filename=f"{short}{title_hint}",
            rows=dialog_rows,
        )
        if not deductions:
            return
        self._apply_retroactive_history_deduction(record, deductions)

    def _retroactive_deduct_pick_spool(self, record) -> None:
        """Manuell Spule + Gramm wählen, wenn G-Code/CFS keine Zeilen liefern."""
        from creality_nfc.print_history import PrintJobRecord

        spools = list(self.inventory.sorted_spools())
        if not spools:
            self.notify(_t("mw.notify.no_spools_create_first"), "warn")
            return

        dlg = tk.Toplevel(self)
        dlg.title(_t("mw.deduct.retro_title"))
        prepare_toplevel(dlg, self, width=440, height=220, geometry_key="retro_deduct")
        fname = (record.filename or "").replace("\\", "/").rsplit("/", 1)[-1]
        ttk.Label(
            dlg,
            text=_t("mw.deduct.retro_print_line", fname=(fname or "—"))
            + "\n"
            + _t("mw.deduct.retro_hint"),
            wraplength=400,
        ).pack(anchor="w", padx=12, pady=(12, 8))

        choices = [(s.id, s.display_name()) for s in spools]
        id_map = {label: sid for sid, label in choices}
        var = tk.StringVar()
        if isinstance(record, PrintJobRecord) and record.spool_id:
            sp0 = self.inventory.get(record.spool_id)
            if sp0:
                var.set(sp0.display_name())
        elif choices:
            var.set(choices[0][1])
        combo = ttk.Combobox(
            dlg,
            textvariable=var,
            values=[label for _, label in choices],
            state="readonly",
        )
        combo.pack(fill="x", padx=12, pady=4)

        grams_var = tk.StringVar(
            value=str(
                record.estimated_total_g
                or self.settings.default_post_print_deduct_g
                or 50
            )
        )
        row_g = ttk.Frame(dlg)
        row_g.pack(fill="x", padx=12, pady=8)
        ttk.Label(row_g, text=_t("deduct.grams")).pack(side="left")
        ttk.Entry(row_g, textvariable=grams_var, width=10).pack(side="left", padx=8)

        result: list[tuple[str, int]] | None = None

        def _ok() -> None:
            nonlocal result
            sid = id_map.get(var.get())
            if not sid:
                from creality_nfc.i18n import t as _t
                self.notify(_t("notify.select_spool"), "warn")
                return
            try:
                grams = int(grams_var.get().strip())
            except ValueError:
                self.notify(_t("mw.notify.enter_grams_number"), "warn")
                return
            if grams <= 0:
                from creality_nfc.i18n import t as _t
                self.notify(_t("notify.grams_positive"), "warn")
                return
            result = [(sid, grams)]
            dlg.destroy()

        def _cancel() -> None:
            dlg.destroy()

        btn_row = ttk.Frame(dlg)
        btn_row.pack(fill="x", padx=12, pady=12)
        ttk.Button(btn_row, text=_t("btn.cancel"), command=_cancel).pack(side="left")
        ttk.Button(btn_row, text=_t("deduct.btn_apply"), command=_ok, style="Accent.TButton").pack(
            side="right"
        )
        dlg.wait_window()
        if result:
            self._apply_retroactive_history_deduction(record, result)

    def _apply_retroactive_history_deduction(
        self,
        record,
        deductions: list[tuple[str, int]],
    ) -> None:
        from creality_nfc.print_history import PrintJobRecord, resolve_history_deduct_meta
        from creality_nfc.spool_passport import touch_passport_after_print

        if not isinstance(record, PrintJobRecord) or not deductions:
            return
        total_new = sum(g for _sid, g in deductions if g > 0)
        if total_new <= 0:
            return
        fname = (record.filename or "").strip()
        note_print = _t("mw.history.note_print", fname=fname[:36]) if fname else _t("mw.history.note_print_retro")
        self._apply_deductions_to_spools(deductions, note=note_print)

        prev = int(record.deducted_g or 0)
        new_total = prev + total_new if prev else total_new
        sid = deductions[0][0]
        sp = self.inventory.get(sid)
        slot_idx, slot_label, spool_display, _ = resolve_history_deduct_meta(
            deductions,
            None,
            get_spool=self.inventory.get,
            fallback_slot=sp.cfs_slot if sp and sp.cfs_slot is not None else record.cfs_slot,
        )
        hist_note = (record.note or "").strip()
        if "nachträg" not in hist_note.lower() and "later" not in hist_note.lower():
            hist_note = (
                _t("mw.history.combined", hist_note=hist_note).strip(" ·")
                if hist_note and hist_note != "—"
                else _t("mw.history.retro_added")
            )
        if not self.print_history.update_record(
            record,
            deducted_g=new_total,
            note=hist_note,
            spool_id=sid,
            spool_label=spool_display or (sp.label if sp else record.spool_label),
            cfs_slot=slot_idx,
            cfs_slot_label=slot_label or record.cfs_slot_label,
        ):
            self.notify(
                _t("mw.history.save_failed"),
                "warn",
            )
            return
        if sp:
            touch_passport_after_print(
                sp,
                filename=fname,
                deducted_g=total_new,
            )
            self.inventory.save()

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
            if fname and self.settings.is_post_print_deduct_handled(fname):
                return
            if self._post_print_prompted:
                return
            if not self.settings.prompt_deduct_after_print:
                self._record_print_history(
                    filename=fname, deductions=[], dialog_rows=[], state=printer_state or {}
                )
                if fname:
                    self.settings.remember_post_print_deduct(fname)
                    self.settings.save(DEFAULT_SETTINGS_PATH)
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
        from creality_nfc.cfs_feed import find_loaded_flat_index

        fname = (filename or "").strip()
        cfs_slots: list[CfsSlotInfo] = []
        if hasattr(self, "_printer_device_panel"):
            cfs_slots = list(getattr(self._printer_device_panel, "_cfs_slots", []))
        if not cfs_slots and state:
            from creality_nfc.cfs_layout import parse_cfs_layout

            cfs_slots = parse_cfs_layout(state).all_slots()
        file_entry = self._gcode_entry_for_name(state, filename)
        loaded_slot = (
            find_loaded_flat_index(state, cfs_slots) if state and cfs_slots else None
        )
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

        dialog_rows = self._collect_post_print_deduct_rows(
            fname,
            state,
            cfs_slots,
            slot_hint=slot_hint,
            file_entry=file_entry,
        )

        if not dialog_rows:
            parts = [
                _t("mw.deduct.no_auto"),
                _t("mw.deduct.file_line", fname=(fname or "—")),
            ]
            if not cfs_slots:
                parts.append(_t("mw.deduct.no_cfs_slots"))
            elif slot_hint is not None and 0 <= slot_hint < len(cfs_slots):
                parts.append(
                    _t("mw.deduct.no_slot", slot=cfs_slots[slot_hint].label)
                    + _t("mw.deduct.edit_cfs_hint")
                )
            else:
                parts.append(_t("mw.deduct.no_weight_no_slot"))
            parts.append(
                _t("mw.deduct.tip_manual") + _t("mw.deduct.use_retro")
            )
            self.notify("\n".join(parts), "warn")
            try:
                self._record_print_history(
                    filename=filename,
                    deductions=[],
                    dialog_rows=[],
                    state=state,
                )
            except Exception:
                pass
            try:
                self.settings.remember_post_print_deduct(fname)
                self.settings.save(DEFAULT_SETTINGS_PATH)
                self._post_print_deduct_file = fname
            except Exception:
                pass
            return

        def _remember_deduct_handled() -> None:
            if not fname:
                return
            self.settings.remember_post_print_deduct(fname)
            self.settings.save(DEFAULT_SETTINGS_PATH)
            self._post_print_deduct_file = fname

        def _ask() -> None:
            self._post_print_prompted = True
            try:
                deductions = ask_post_print_deductions(
                    self, filename=filename, rows=dialog_rows
                )
            finally:
                self._post_print_prompted = False
            try:
                self._record_print_history(
                    filename=filename,
                    deductions=deductions or [],
                    dialog_rows=dialog_rows,
                    state=state,
                )
            except Exception:
                pass
            # Dialog geschlossen (Abziehen oder Abbrechen) — nicht bei jedem Start erneut zeigen.
            _remember_deduct_handled()
            if not deductions:
                return
            note = f"Druck {filename or 'beendet'}"[:40]
            self._apply_deductions_to_spools(deductions, note=note)

        self.after(400, _ask)

    def show_print_history(self) -> None:
        from creality_nfc.print_history import repair_history_slots_from_inventory
        from ui.extras_dialogs import show_print_history_dialog

        if repair_history_slots_from_inventory(
            self.print_history.list_entries(),
            get_spool=self.inventory.get,
        ):
            self.print_history.save()
        show_print_history_dialog(
            self,
            self.print_history,
            threshold_g=self.settings.low_filament_threshold_g,
            on_retro_deduct=self.retroactive_deduct_from_history,
        )

    def notify_print_finished(self, filename: str) -> None:
        fn = (filename or "").strip() or "Druck"
        self.notify(_t("notify.print_finished", filename=fn), "ok")
        if getattr(self.settings, "alert_print_complete_toast", True):
            from creality_nfc.desktop_notify import show_desktop_notification

            show_desktop_notification("Druck fertig", fn, settings=self.settings)

    def _record_print_history(
        self,
        *,
        filename: str,
        deductions: list[tuple[str, int]] | None = None,
        dialog_rows: list | None = None,
        state: dict | None = None,
    ) -> None:
        import time

        from creality_nfc.print_history import PrintJobRecord, _now, resolve_history_deduct_meta

        panel = getattr(self, "_printer_device_panel", None)
        duration_sec = None
        if panel is not None:
            started = getattr(panel, "_print_job_started_mono", None)
            if started:
                duration_sec = max(0, int(time.monotonic() - float(started)))
        ded = deductions or []
        total_g = sum(g for _sid, g in ded) if ded else None
        fallback_slot = (
            getattr(panel, "_last_print_cfs_slot", None) if panel is not None else None
        )
        slot_idx, slot_label, spool_label, spool_id = resolve_history_deduct_meta(
            ded,
            dialog_rows,
            get_spool=self.inventory.get,
            fallback_slot=fallback_slot,
        )
        est_g = None
        try:
            from creality_nfc.gcode_filament import total_job_filament_grams

            job = total_job_filament_grams(state, filename)
            if job:
                est_g = job[0]
        except Exception:
            pass
        self.print_history.add(
            PrintJobRecord(
                id=PrintJobRecord.new_id(),
                ts=_now(),
                filename=filename,
                duration_sec=duration_sec,
                progress_pct=100,
                estimated_total_g=est_g,
                deducted_g=total_g,
                cfs_slot=slot_idx,
                cfs_slot_label=slot_label,
                spool_label=spool_label,
                spool_id=spool_id,
                note=_t("mw.history.confirmed") if ded else _t("mw.history.no_deduct"),
            )
        )
        if spool_id:
            sp = self.inventory.get(spool_id)
            if sp:
                from creality_nfc.spool_passport import touch_passport_after_print

                touch_passport_after_print(
                    sp,
                    filename=filename,
                    deducted_g=total_g,
                    ts=_now(),
                )
                self.inventory.save()

    def _duplicate_last_tag_template(self) -> None:
        tpl = self._last_write_template
        if not tpl:
            self.notify(_t("notify.tag_template_missing"), "warn")
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
        self.notify(_t("mw.notify.material_loaded_rewrite"), "ok")

    def _set_tag_diagnostic_text(self, text: str) -> None:
        if not hasattr(self, "tag_diag_text"):
            return
        self.tag_diag_text.config(state="normal")
        self.tag_diag_text.delete("1.0", "end")
        self.tag_diag_text.insert("1.0", text)
        self.tag_diag_text.config(state="disabled")

    def _spool_match_line(self, matched: Spool | None) -> str:
        if matched is None:
            return _t("mw.spool.my_unlinked")
        parts = [matched.label or matched.material_name or _t("mw.label.spool_default")]
        if matched.brand:
            parts.insert(0, matched.brand)
        if matched.cfs_slot is not None and 0 <= matched.cfs_slot <= 3:
            parts.append(f"CFS {matched.cfs_slot_label()}")
        if matched.remaining_g is not None:
            parts.append(_t("mw.spool.remaining_g", grams=matched.remaining_g))
        return _t("mw.spool.my_prefix") + " · ".join(parts)

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
            self.spool_match_label.config(text=_t("mw.tag.empty_ready"), fg=OK)
            if matched is not None:
                inv = matched.label or matched.material_name or _t("mw.label.spool_default")
                self.tag_extra_label.config(
                    text=_t("mw.spool.inventory_only_uid", info=inv),
                )
            else:
                self.tag_extra_label.config(
                    text=_t("mw.spool.choose_brand_then"),
                )
            if matched is not None and not self._selected_profile():
                self._prefill_form_from_spool_for_write(matched)
            return matched
        if matched is not None:
            title = matched.label or matched.material_name or _t("mw.label.spool_default")
            self.spool_match_label.config(text=title, fg=TEXT)
            extras: list[str] = []
            if matched.brand and matched.brand.lower() not in title.lower():
                extras.append(matched.brand)
            if matched.material_name and matched.material_name.lower() not in title.lower():
                extras.append(matched.material_name)
            if matched.cfs_slot is not None and 0 <= matched.cfs_slot <= 3:
                extras.append(f"CFS {matched.cfs_slot_label()}")
            if matched.remaining_g is not None:
                extras.append(_t("mw.spool.remaining_g", grams=matched.remaining_g))
            self.tag_extra_label.config(text=" · ".join(extras))
            if apply_form:
                self.apply_spool(matched)
        elif uid_n:
            self.spool_match_label.config(text=_t("mw.spool.not_in_my_spools"), fg=WARN)
            self.tag_extra_label.config(
                text=_t("mw.spool.chip_has_data")
                + _t("mw.spool.chip_has_data_or_dup"),
            )
        else:
            self.spool_match_label.config(
                text=_t("mw.spool.placeholder_read"),
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
            self._set_tag_diagnostic_text(_t("mw.tag.diagnostic_failed", exc=exc))
            return None

    def _refresh_tag_diagnostic_manual(self) -> None:
        if not self._ensure_reader_for_tag():
            return
        try:
            session = self._session()
            uid = session.uid.hex().upper()
            matched = self._refresh_tag_diagnostic(session)
            spool_txt = self._spool_match_line(matched).replace(_t("mw.spool.my_prefix"), "")
            self._tag_finished(
                _t("mw.tag.read_done_title"),
                f"{_t('mw.tag.uid_line', uid=uid)}\n{_t('mw.tag.spool_line', spool=spool_txt)}\n\n"
                + _t("mw.tag.raw_data_below"),
                "ok",
            )
        except Exception as exc:
            self._report_tag_error(exc)

    def format_tag_quick(self) -> None:
        """Creality-Payload auf dem Tag löschen (ohne Tag-Speicher-Dialog)."""

        def do_format() -> None:
            if not self._ensure_reader_for_tag():
                return
            self._set_status(_t("mw.status.clearing_tag"), "info")
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
                        _t("mw.tag.format_done_title"),
                        _t("mw.tag.format_done_body", uid=uid)
                        + _t("mw.tag.encrypted_empty_hint")
                        + _t("mw.tag.format_done_inventory_hint")
                        + f"{report}",
                        "ok",
                    )
                else:
                    self._tag_finished(
                        _t("mw.tag.format_failed_title"),
                        _t("mw.tag.format_failed_body", uid=uid)
                        + f"{report}",
                        "warn",
                    )
            except Exception as exc:
                self._report_tag_error(exc)

        confirm(
            self,
            _t("mw.tag.format_confirm"),
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
                        _t(
                            "mw.tag.multiple_profiles",
                            material_id=material_id,
                            names=names,
                            extra=extra,
                        )
                        + _t("mw.tag.pick_correct_material"),
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
            self.notify(_t("mw.notify.uac_failed"), "error")
            return
        self._set_status(_t("mw.status.scard_restarting"), "warn")
        self.after(4000, self._after_smartcard_start)

    def _do_start_scard_uac(self) -> None:
        if not start_scard_elevated():
            self.notify(_t("mw.notify.uac_failed"), "error")
            return
        self._set_status(_t("mw.smartcard.starting_uac"), "warn")
        self.after(3000, self._after_smartcard_start)

    def start_smartcard_service(self) -> None:
        state = probe_pcsc()
        if state == "ok":
            self._apply_nfc_ui()
            self.notify(_t("mw.notify.reader_ready"), "ok")
            self.connect_reader(show_errors=False)
            return
        if state == "no_reader":
            self._apply_nfc_ui()
            self._set_status(_t("mw.smartcard.no_reader_usb"), "warn")
            self.notify(
                _t("mw.smartcard.service_running"),
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
            self._set_status(_t("mw.status.scard_active"), "ok")
            self.connect_reader(show_errors=False)
        elif state == "no_reader":
            self._set_status(_t("mw.status.scard_ok_usb"), "warn")
        elif state == "service_stuck":
            self._set_status(_t("mw.smartcard.still_hanging"), "error")
            self.notify(_t("mw.notify.service_stuck_restart"), "warn")
        else:
            self._set_status(_t("mw.smartcard.uac_confirm"), "warn")

    def connect_reader(self, show_errors: bool = True) -> None:
        state = self._apply_nfc_ui()
        if state == "service_down":
            self._set_status(_t("mw.notify.smartcard_off"), "error")
            if show_errors:
                self.ask_confirm(
                    scard_status_message(state) + "\n\nJetzt starten?",
                    self.start_smartcard_service,
                )
            return
        if state == "service_stuck":
            self._set_status(_t("mw.smartcard.hangs_restart"), "error")
            if show_errors:
                self.start_smartcard_service()
            return
        if state == "no_reader":
            self._set_status(_t("mw.smartcard.no_reader_connect"), "warn")
            if show_errors:
                self.notify(_t("mw.smartcard.service_running_long"),
                )
            return
        try:
            pref = self.settings.preferred_reader.strip() or None
            name = self.reader.connect(pref)
            self._apply_nfc_ui()
            short = name if len(name) <= 50 else name[:47] + "…"
            if self.reader.direct_mode:
                self._set_status(_t("mw.status.reader_ready", short=short), "ok")
            else:
                self._set_status(_t("mw.status.reader_connected", short=short), "ok")
        except NfcReaderError as exc:
            short, detail, offer_start = self._nfc_error_message(exc)
            self._apply_nfc_ui()
            self._set_status(short, "error")
            if show_errors:
                if offer_start:
                    self.ask_confirm(detail + _t("mw.confirm.run_action"), self.start_smartcard_service)
                else:
                    self.notify(detail, "error")
        except Exception as exc:
            self._set_status(_t("mw.status.reader_error"), "error")
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
            if self._chip_dup_poll_after:
                try:
                    self.after_cancel(self._chip_dup_poll_after)
                except Exception:
                    pass
            self._chip_dup_poll_after = self.after(120, self._chip_dup_on_tag)
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

    def _chip_dup_show_step_hint(self, step: str) -> None:
        if not hasattr(self, "_chip_dup_hint_frame"):
            return
        hint = CHIP_DUP_STEP_HINTS.get(step, "")
        if hint:
            self._chip_dup_hint_label.configure(text=hint)
            self._chip_dup_hint_frame.pack(fill="x", pady=(8, 0), before=self._placement_box)
        else:
            self._chip_dup_hint_frame.pack_forget()

    def duplicate_chip_start(self) -> None:
        """Assistent: Quell-Chip lesen → Ziel-Chip 1:1 beschreiben."""
        if self._chip_dup_step:
            if messagebox.askyesno(
                APP_NAME,
                _t("mw.copy.in_progress"),
                default="no",
            ):
                self._chip_dup_cancel()
            return
        if not messagebox.askyesno(
            APP_NAME,
            str(CHIP_DUP_INTRO) + "\n\n" + _t("mw.dup.start_q"),
            default="yes",
        ):
            return
        self.notebook.select(self.tab_tag)
        self._chip_dup_step = "source"
        self._chip_dup_payload = None
        self._chip_dup_source_uid = ""
        self._chip_dup_source_spool_id = ""
        self._chip_dup_show_step_hint("source")
        self._set_status(_t("mw.notify.dup_step1_status"), "info")
        messagebox.showinfo(
            APP_NAME,
            _t("mw.dup.step1_dialog"),
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
                _t("mw.duplicate.target_linked", label=sp.label)
                + _t("mw.duplicate.tag_count", n=n, s=("s" if n != 1 else ""))
            )
        return _t("mw.duplicate.target_already_linked", label=sp.label)

    def _chip_dup_cancel(self, *, notify: bool = True) -> None:
        if self._chip_dup_poll_after:
            try:
                self.after_cancel(self._chip_dup_poll_after)
            except Exception:
                pass
            self._chip_dup_poll_after = None
        self._chip_dup_step = ""
        self._chip_dup_payload = None
        self._chip_dup_source_uid = ""
        self._chip_dup_source_spool_id = ""
        try:
            self.reader.disconnect()
        except Exception:
            pass
        self._chip_dup_show_step_hint("")
        if notify:
            self._set_status(_t("mw.dup.cancelled_status"), "info")
            messagebox.showinfo(APP_NAME, _t("mw.duplicate.cancelled"))

    def _chip_dup_on_tag(self) -> None:
        self._chip_dup_poll_after = None
        if not self._chip_dup_step:
            return
        if self._tag_busy:
            self._chip_dup_poll_after = self.after(250, self._chip_dup_on_tag)
            return
        if self._chip_dup_step == "source":
            self._chip_dup_read_source()
        elif self._chip_dup_step == "target":
            self._chip_dup_write_target()

    def _chip_dup_read_payload_reliable(self, session: TagSession, *, attempts: int = 3) -> tuple[str, bytes]:
        """Mehrfach lesen bis zwei Lesungen übereinstimmen (ACR122U-Stabilität)."""
        import time

        last_blob: bytes | None = None
        last_raw = ""
        for attempt in range(attempts):
            raw = session.read_payload()
            if payload_is_empty(raw):
                raise NfcReaderError(
                    _t("mw.duplicate.chip_empty_or_unreadable")
                    + _t("mw.duplicate.write_template_first")
                )
            blob = payload_bytes_from_read(raw)
            if last_blob is not None and blob == last_blob:
                return raw, blob
            last_blob = blob
            last_raw = raw
            if attempt < attempts - 1:
                time.sleep(0.12)
        if last_blob is None:
            raise NfcReaderError(_t("mw.duplicate.read_failed"))
        return last_raw, last_blob

    def _chip_dup_read_source(self) -> None:
        import time

        if not self._ensure_reader_for_tag():
            self._chip_dup_cancel(notify=False)
            messagebox.showerror(APP_NAME, _t("mw.notify.reader_not_ready_abort"))
            return
        self._tag_busy = True
        self._suppress_auto_read_until = time.monotonic() + 60.0
        try:
            session = self._session()
            uid = session.uid.hex().upper()
            raw, blob = self._chip_dup_read_payload_reliable(session)
            self._chip_dup_payload = blob
            self._chip_dup_source_uid = uid
            src_spool = self.inventory.find_by_uid(uid)
            self._chip_dup_source_spool_id = src_spool.id if src_spool else ""
            self.uid_label.config(text=uid)
            matched = src_spool
            self._show_tag_identity(uid, matched=matched, apply_form=bool(matched))
            try:
                info = parse_tag_payload(raw)
                if matched:
                    self._apply_fields_from_tag(info, matched=matched)
            except ValueError:
                pass
            try:
                self.reader.disconnect()
            except Exception:
                pass
            self._chip_dup_step = "target"
            self._chip_dup_show_step_hint("target")
            spool_hint = (
                _t("mw.duplicate.linked_spool", label=(src_spool.label or src_spool.material_name))
                if src_spool
                else _t("mw.dup.not_in_spools")
            )
            detail = _t(
                "mw.dup.step1_read_ok",
                uid=uid,
                spool_hint=spool_hint,
            )
            self._tag_finished(_t("mw.notify.dup_step1_done"), detail, "ok")
        except Exception as exc:
            self._report_tag_error(exc)
            self._chip_dup_cancel(notify=False)
            messagebox.showerror(APP_NAME, _t("mw.dup.read_failed_abort"))
        finally:
            self._tag_busy = False

    def _chip_dup_write_target(self) -> None:
        import time

        if not self._chip_dup_payload:
            self._chip_dup_cancel()
            return
        if not self._ensure_reader_for_tag():
            messagebox.showerror(APP_NAME, _t("mw.notify.reader_not_ready"))
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
                    _t("mw.dup.same_uid_title") + "\n\n" + _t("mw.dup.swap_chip_warn"),
                )
                return
            if not messagebox.askyesno(
                APP_NAME,
                _t(
                    "mw.dup.copy_confirm",
                    new_uid=uid,
                    source_uid=self._chip_dup_source_uid,
                ),
                default="yes",
            ):
                try:
                    self.reader.disconnect()
                except Exception:
                    pass
                self._set_status(_t("mw.dup.write_cancelled"), "warn")
                return
            verify_ok = False
            read_back = ""
            for write_try in range(2):
                session.write_payload(self._chip_dup_payload)
                time.sleep(0.1)
                read_back = session.read_payload()
                verify_ok = payload_bytes_from_read(read_back) == self._chip_dup_payload
                if verify_ok:
                    break
                time.sleep(0.15)
            self.uid_label.config(text=uid)
            link_msg = self._chip_dup_link_target_uid(uid)
            matched = self.inventory.find_by_uid(uid)
            if matched is None and self._chip_dup_source_spool_id:
                matched = self.inventory.get(self._chip_dup_source_spool_id)
            tag_empty = payload_is_empty(read_back)
            self._show_tag_identity(
                uid,
                matched=matched,
                apply_form=False,
                tag_empty=tag_empty,
            )
            if not tag_empty and matched is not None:
                try:
                    info = parse_tag_payload(read_back)
                    self._apply_fields_from_tag(info, matched=matched)
                except ValueError:
                    pass
            try:
                diag = session.describe_reading()
                diag = f"{diag}\n\n{self._spool_match_line(matched)}"
                self._set_tag_diagnostic_text(diag)
            except Exception:
                pass
            try:
                self.reader.disconnect()
            except Exception:
                pass
            self._suppress_auto_read_until = time.monotonic() + 5.0
            spool_title = (matched.label or matched.material_name or _t("mw.label.spool_default")) if matched else ""
            body = _t(
                "mw.dup.copy_success",
                source_uid=self._chip_dup_source_uid,
                new_uid=uid,
            )
            if spool_title:
                body += _t("mw.dup.spool_in_app", title=spool_title) + "\n"
            body += "\n"
            if verify_ok:
                body += _t("mw.verify.content_matches")
            else:
                body += (
                    _t("mw.verify.ambiguous")
                    + _t("mw.verify.try_again_hint")
                )
            if link_msg:
                body += f"\n{link_msg}"
            elif matched is None:
                body += (
                    _t("mw.duplicate.save_uid_hint")
                    + _t("mw.duplicate.save_uid_hint_extra")
                )
            self._chip_dup_payload = None
            keep_spool = self._chip_dup_source_spool_id
            self._chip_dup_source_uid = ""
            self._chip_dup_source_spool_id = keep_spool
            self._tag_finished(_t("mw.duplicate.step2_done_title"), body, "ok" if verify_ok else "warn")
            if messagebox.askyesno(
                APP_NAME,
                _t("mw.duplicate.copy_another_q"),
                default="no",
            ):
                self._chip_dup_step = "target"
                self._chip_dup_show_step_hint("target")
                self._suppress_auto_read_until = time.monotonic() + 60.0
                self._set_status(_t("mw.duplicate.next_chip_status"), "info")
                messagebox.showinfo(
                    APP_NAME,
                    _t("mw.duplicate.next_chip_inst"),
                )
            else:
                self._chip_dup_step = ""
                self._chip_dup_source_spool_id = ""
                self._chip_dup_show_step_hint("")
                self._suppress_auto_read_until = time.monotonic() + 3.0
        except Exception as exc:
            self._report_tag_error(exc)
            if messagebox.askyesno(APP_NAME, _t("mw.notify.dup_abort_q"), default="yes"):
                self._chip_dup_cancel(notify=False)
        finally:
            self._tag_busy = False

    def pick_color(self) -> None:
        _, hex_color = colorchooser.askcolor(color="#" + self.color_hex, title=_t("mw.color.title"))
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
            title=_t("mw.tag.color_photo_title"),
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
            self.notify(_t("mw.notify.color_from_photo", hex_code=hex_code), "ok")
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
            self.notify(_t("mw.notify.read_before_export"), "warn")
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
            self.notify(_t("mw.notify.tag_exported", path=path), "ok")
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
            on_load_db=self.sync_from_printer if MATERIAL_DB_PRINTER_ONLY else self.sync_database,
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
                self._set_status(_t("mw.status.tag_empty"), "ok")
                return
            info = parse_tag_payload(raw)
            self._apply_fields_from_tag(info, matched=matched)
            self._store_tag_export(uid, info)
            self._set_status(_t("mw.status.tag_read"), "ok")
        except Exception as exc:
            self._set_status(str(exc)[:70], "error")

    def read_tag(self) -> None:
        if not self._ensure_reader_for_tag():
            return
        self._set_status(_t("mw.status.tag_reading"), "info")
        self.update_idletasks()
        try:
            session = self._session()
            uid = session.uid.hex().upper()
            raw = session.read_payload()
            matched = self._refresh_tag_diagnostic(session)
            if payload_is_empty(raw):
                spool_txt = self._spool_match_line(matched).replace(_t("mw.spool.my_prefix"), "")
                self._tag_finished(
                    _t("mw.tag.read_empty_title"),
                    f"{_t('mw.tag.uid_line', uid=uid)}\n{_t('mw.tag.spool_line', spool=spool_txt)}\n\n"
                    + _t("mw.tag.read_empty_body"),
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
            spool_txt = self._spool_match_line(matched).replace(_t("mw.spool.my_prefix"), "")
            self._tag_finished(
                "Tag lesen — fertig",
                f"{_t('mw.tag.uid_line', uid=uid)}\n{_t('mw.tag.spool_line', spool=spool_txt)}\n\n"
                f"{_t('mw.tag.material_id', id=info['material_id'])}\n"
                f"Farbe: {info['color']}\n"
                f"Gewicht: {wlabel}\n"
                f"Serie: {info.get('serial', '?')}\n"
                f"{_t('mw.tag.printer_label', printer=info.get('printer', '') or '—')}",
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
                _t("mw.materials.demo_hint"),
                "warn",
            )
        if not self._ensure_reader_for_tag(show_dialog=not silent):
            return
        import time

        write_color = self._write_tag_color()
        serial = self._current_serial()
        if not silent:
            self._set_status(_t("mw.status.tag_writing"), "info")
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
                            _t("mw.tag.already_has_data")
                            + _t(
                                "mw.tag.existing_details",
                                material_id=info.get("material_id", "?"),
                                color=info.get("color", "?"),
                                weight=wlabel,
                                serial=info.get("serial", "?"),
                            )
                            + _t("mw.tag.overwrite_confirm"),
                            default="no",
                            parent=self,
                        ):
                            self._set_status(_t("mw.tag.write_cancelled"), "warn")
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
                        _t("mw.tag.write_done_short"),
                        _t(
                            "mw.tag.write_done_body",
                            uid=uid,
                            brand=profile.brand,
                            name=profile.name,
                            filament_id=profile.filament_id,
                            serial=serial,
                        )
                        + _t("mw.tag.next_in_batch"),
                        "ok" if not verify_errors else "warn",
                    )
            elif not silent:
                body = (
                    f"UID: {uid}\n\n"
                    f"{profile.brand} — {profile.name}\n"
                    f"ID {profile.filament_id}, SN {serial}\n"
                )
                if verify_errors:
                    body += _t("mw.tag.written_verify_reports") + "\n".join(
                        f"• {e}" for e in verify_errors
                    )
                else:
                    body += _t("mw.tag.written_verified_ok")
                if spool_msg:
                    body += f"\n\n{spool_msg}"
                self._tag_finished(
                    _t("mw.tag.write_done_short") if not verify_errors else _t("mw.tag.write_verify_short"),
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
        self.notify(_t("mw.notify.open_settings_tab"), "info")

    def _printer_panel(self) -> PrinterDevicePanel | None:
        return getattr(self, "_device_panel", None) or getattr(
            self, "_printer_device_panel", None
        )

    def _toggle_cfs_preview(self) -> None:
        """Menü-Haken: Zustand vom Panel (nicht vom Haken lesen — Tk-Reihenfolge-Bug)."""
        panel = self._printer_panel()
        if panel is None:
            self._cfs_preview_var.set(False)
            self.notify(_t("mw.notify.printer_tab_not_ready"), "warn")
            return
        if panel._cfs_preview_boxes:
            self._cfs_preview_var.set(False)
            panel.force_cfs_demo_off()
            self.notify(_t("mw.notify.cfs_preview_ended"), "ok")
        else:
            self._cfs_preview_var.set(True)
            panel.set_cfs_preview(4)
            self.notebook.select(self.tab_printer)
            nb = getattr(panel, "_main_nb", None)
            if nb is not None:
                try:
                    nb.select(2)
                except tk.TclError:
                    pass
            self.notify(_t("mw.notify.cfs_preview_on"), "info")

    def open_printer_manager(self) -> None:
        def apply_profile(p) -> None:
            self.ssh_host_var.set(p.host)
            self.ssh_pass_var.set(p.password)
            model = normalize_printer_model(p.model or DEFAULT_PRINTER)
            if p.model and p.model.strip() != model:
                self.notify(
                    _t("mw.printer.unsupported_model", p_model=p.model, model=model),
                    "warn",
                )
            self.printer_var.set(model)
            save_settings(p.host, p.password, model)
            self._set_status(_t("mw.printer.adopted", name=p.name, host=p.host), "ok")
            self.notify(_t("mw.notify.printer_ip_model", host=p.host, model=p.model), "ok")

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
                    messagebox.showerror(APP_NAME, _t("mw.reset.failed", exc=exc), parent=self)
                    return
                messagebox.showinfo(
                    APP_NAME,
                    _t("mw.reset.success"),
                    parent=self,
                )
                self.destroy()
                if getattr(sys, "frozen", False):
                    os.execv(sys.executable, [sys.executable, *sys.argv[1:]])
                else:
                    main_py = Path(__file__).resolve().parent.parent / "main.py"
                    os.execv(sys.executable, [sys.executable, str(main_py), *sys.argv[1:]])

            self.ask_confirm(
                _t("mw.reset.last_warning")
                + _t("mw.reset.confirm_all")
                + _t("mw.reset.confirm_all_targets"),
                really_reset,
            )

        self.ask_confirm(
            _t("mw.reset.title")
            + _t("mw.reset.backup_tip")
            + _t("mw.reset.continue_q"),
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
            self.notify(_t("mw.notify.saved_backup", path=path))
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
                self.notify(_t("mw.notify.restore_count", n=n), "ok")
            except Exception as exc:
                self.notify(str(exc), "error")

        self.ask_confirm(_t("mw.restore.confirm"), proceed)

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
            self.notify(_t("mw.notify.db_imported", name=out.name))
        except Exception as exc:
            self.notify(str(exc), "error")

    def _schedule_reader_poll(self) -> None:
        if self._shutdown_done:
            return
        sec = max(5, int(self.settings.poll_reader_sec))
        self._poll_reader()
        self._reader_poll_after = self.after(sec * 1000, self._schedule_reader_poll)

    def _poll_reader(self) -> None:
        if self._shutdown_done:
            return
        state = probe_pcsc()
        if state == "ok":
            try:
                pref = self.settings.preferred_reader.strip() or None
                self.reader.connect(pref)
                self._apply_nfc_ui()
                short = self.reader._reader_name or "Reader"
                if len(short) > 45:
                    short = short[:42] + "…"
                self._set_status(_t("mw.status.reader_label", short=short), "ok")
            except Exception:
                pass
        elif state == "no_reader":
            self._apply_nfc_ui()
            if self.uid_label.cget("text") == "—":
                self._set_status(_t("mw.status.reader_plug_in"), "warn")

    def _schedule_automatic_update_check(self) -> None:
        """Beim Start und alle 4 h: GitHub-Release prüfen."""
        delay_ms = 4500
        if self.settings.show_setup_on_startup or not self.settings.setup_completed:
            delay_ms = 7000
        self.after(delay_ms, self._check_updates_quiet)
        self._schedule_periodic_update_checks()

    def _schedule_periodic_update_checks(self) -> None:
        if not self.settings.check_updates:
            return
        self.after(4 * 60 * 60 * 1000, self._periodic_update_check)

    def _periodic_update_check(self) -> None:
        if not self.settings.check_updates:
            return
        self._check_updates_quiet()
        self._schedule_periodic_update_checks()

    def _check_updates_quiet(self) -> None:
        if self._update_check_running:
            return
        self._update_check_running = True

        def work() -> None:
            try:
                info = fetch_latest_release()
                if info and is_newer(info.version, APP_VERSION):

                    def prompt() -> None:
                        self._prompt_update_available(info)

                    self.after(0, prompt)
                elif info:
                    self.after(
                        0,
                        lambda: self._set_status(
                            f"Version {APP_VERSION} — GitHub {info.tag} aktuell",
                            "ok",
                        ),
                    )
            except Exception:
                pass
            finally:

                def done() -> None:
                    self._update_check_running = False

                self.after(0, done)

        threading.Thread(target=work, name="update-check", daemon=True).start()

    def _prompt_update_available(self, info: ReleaseInfo) -> None:
        """Automatischer Hinweis beim Start / periodisch (einmal pro Tag pro Session)."""
        if self._update_prompted_tag == info.tag:
            return
        self._update_prompted_tag = info.tag
        self._set_status(_t("mw.update.available_status", tag=info.tag), "warn")
        self.notify(
            _t("mw.update.new_version_line", tag=info.tag, installed=APP_VERSION)
            + "\n"
            + _t("mw.update.dialog_opening"),
            "warn",
        )
        self.after(200, lambda: self._offer_update_download(info))

    def check_updates(self) -> None:
        from tkinter import messagebox

        info = fetch_latest_release()
        if not info:
            self.notify(
                _t("mw.update.no_release_info")
                + _t("mw.update.repo_line", repo=GITHUB_RELEASES_REPO, url=GITHUB_URL)
                + _t("mw.update.upload_hint")
                + _t("mw.update.no_setup_yet"),
                "warn",
            )
            return
        if is_newer(info.version, APP_VERSION):
            self._offer_update_download(info)
        else:
            self._focus_app_for_dialog()
            messagebox.showinfo(
                _t("mw.update.up_to_date_title"),
                _t("mw.update.up_to_date_body", version=APP_VERSION, tag=info.tag),
                parent=self,
            )
            self._set_status(
                _t("mw.update.up_to_date_status", version=APP_VERSION, tag=info.tag),
                "ok",
            )

    def check_updates_reinstall(self) -> None:
        """Setup vom aktuellen Release erneut laden (Reparatur nach fehlgeschlagenem Update)."""
        from tkinter import messagebox

        info = fetch_latest_release()
        if not info:
            self.notify(
                _t("mw.update.no_release_info")
                + _t("mw.update.repo_line", repo=GITHUB_RELEASES_REPO, url=GITHUB_URL)
                + _t("mw.update.upload_hint")
                + _t("mw.update.no_setup_yet"),
                "warn",
            )
            return
        if not info.download_url:
            messagebox.showwarning(
                APP_NAME,
                _t("mw.update.no_setup_asset", tag=info.tag),
                parent=self,
            )
            return
        self._offer_update_download(info, allow_reinstall=True)

    def _ensure_window_visible(self) -> None:
        """Fenster aus Tray holen — sonst sind Dialoge/Update unsichtbar."""
        if getattr(self, "_tray_hidden", False):
            self._do_show_from_tray()
        else:
            try:
                self.deiconify()
                self.lift()
            except tk.TclError:
                pass

    def _focus_app_for_dialog(self) -> None:
        self._ensure_window_visible()
        try:
            self.lift()
            self.attributes("-topmost", True)
            self.after(80, lambda: self.attributes("-topmost", False))
            self.focus_force()
        except tk.TclError:
            pass

    def _offer_update_download(self, info: ReleaseInfo, *, allow_reinstall: bool = False) -> None:
        self._ensure_window_visible()
        if getattr(self, "_update_dialog", None) is not None:
            try:
                if self._update_dialog.winfo_exists():
                    self._update_dialog.lift()
                    return
            except tk.TclError:
                pass

        if allow_reinstall:
            lines = [
                _t("mw.update.reinstall_intro", version=APP_VERSION, tag=info.tag),
                "",
            ]
        else:
            lines = [
                f"Neue Version: {info.tag}",
                f"Installiert: {APP_VERSION}",
                "",
            ]
        if info.name and info.name != info.tag:
            lines.append(info.name)
            lines.append("")
        lines.extend(release_stats_lines(info))
        lines.append("")
        if info.download_url and info.download_label:
            lines.append(f"Datei: {info.download_label} (~60 MB)")
        lines.append(f"Seite: {info.html_url}")
        body = "\n".join(lines)

        self._focus_app_for_dialog()
        dlg = tk.Toplevel(self)
        self._update_dialog = dlg
        dlg.title(
            _t("mw.update.reinstall_title") if allow_reinstall else _t("mw.update.title")
        )
        prepare_toplevel(
            dlg, parent=self, width=520, height=340, geometry_key="update_dialog", modal=True
        )
        tk.Label(
            dlg,
            text=body,
            bg=BG,
            fg=ON_HEADER,
            justify="left",
            wraplength=480,
            padx=16,
            pady=12,
        ).pack(fill="both", expand=True)

        def close() -> None:
            try:
                dlg.grab_release()
            except tk.TclError:
                pass
            dlg.destroy()
            self._update_dialog = None

        btn_row = tk.Frame(dlg, bg=BG)
        btn_row.pack(side="bottom", fill="x", padx=14, pady=12)

        def on_later() -> None:
            close()

        def on_browser() -> None:
            close()
            webbrowser.open(info.download_url or info.html_url)

        def on_install() -> None:
            close()
            if self._bg_job_running:
                messagebox.showwarning(
                    APP_NAME,
                    _t("mw.update.bg_task_running"),
                    parent=self,
                )
                return
            self._run_in_app_update(info, confirm_before_install=allow_reinstall)

        rounded_button(btn_row, _t("mw.update.later"), on_later, variant="secondary", compact=True).pack(
            side="right", padx=(8, 0)
        )
        if info.download_url:
            rounded_button(btn_row, _t("mw.update.browser_btn"), on_browser, variant="secondary", compact=True).pack(
                side="right", padx=(8, 0)
            )
            rounded_button(
                btn_row,
                _t("mw.update.download_install")
                if not allow_reinstall
                else _t("mw.update.reinstall_setup"),
                on_install,
                variant="accent",
                compact=True,
            ).pack(side="right")
        else:
            rounded_button(btn_row, _t("mw.update.open_in_browser"), on_browser, variant="accent", compact=True).pack(
                side="right"
            )
        dlg.protocol("WM_DELETE_WINDOW", on_later)

    def _run_in_app_update(self, info: ReleaseInfo, *, confirm_before_install: bool = False) -> None:
        if not info.download_url:
            webbrowser.open(info.html_url)
            return
        if self._bg_job_running:
            messagebox.showwarning(
                APP_NAME,
                _t("mw.update.task_running_short"),
                parent=self,
            )
            return
        self._set_status(_t("mw.update.downloading"), "info")
        self.notify(
            "Update-Download gestartet — kann einige Minuten dauern.\n"
            "Fortschritt in der Statuszeile unten.",
            "info",
        )
        progress_state = {"last_pct": -1}

        def work() -> tuple[Path | None, str]:
            from creality_nfc.app_update import default_setup_download_path, download_setup

            dest = default_setup_download_path()

            def on_progress(received: int, total: int) -> None:
                if total <= 0:
                    text = _t("mw.update.downloaded_mb", mb=received // (1024 * 1024))
                else:
                    pct = min(100, int(received * 100 / total))
                    if pct == progress_state["last_pct"]:
                        return
                    progress_state["last_pct"] = pct
                    mb = received / (1024 * 1024)
                    total_mb = total / (1024 * 1024)
                    text = f"Update: {mb:.0f} / {total_mb:.0f} MB ({pct}%)"
                self.after(0, lambda t=text: self._set_status(t, "info"))

            try:
                download_setup(info.download_url or "", dest, on_progress=on_progress)
                return dest, ""
            except Exception as exc:
                log_exception("update-download", exc)
                return None, str(exc)

        def on_ok(result: tuple[Path | None, str]) -> None:
            path, err = result
            if not path:
                self._set_status(_t("mw.update.download_failed_status"), "error")
                self.notify(_t("mw.update.download_failed", err=err), "error")
                if messagebox.askyesno(
                    APP_NAME,
                    _t("mw.update.download_failed", err=err)
                    + "\n\n"
                    + _t("mw.update.setup_page_browser"),
                    parent=self,
                ):
                    webbrowser.open(info.download_url or info.html_url)
                return
            self._ensure_window_visible()
            self._set_status(_t("mw.update.ready_install"), "ok")
            from creality_nfc.app_update import (
                confirm_install_ok,
                open_updates_folder,
                write_install_now_helper,
            )

            open_updates_folder()
            from creality_nfc.app_update import default_setup_download_path

            staged = default_setup_download_path()
            helper = write_install_now_helper(path)
            if confirm_before_install:
                confirm_body = (
                    _t("mw.update.setup_ready", path=path)
                    + _t("mw.update.ok_quit_hint")
                    + _t("mw.update.smartscreen_hint")
                    + _t("mw.update.manual_start_hint")
                    + _t("mw.update.helper_bat", path=helper)
                    + _t("mw.update.cancel_keeps")
                )
                if not confirm_install_ok(_t("mw.update.install_title"), confirm_body):
                    self.notify(_t("mw.update.setup_saved", path=path), "info")
                    return
            else:
                self.notify(_t("mw.update.auto_install_notify", path=path, helper=helper), "ok")
                if sys.platform == "win32":
                    try:
                        import winsound

                        winsound.MessageBeep(winsound.MB_ICONASTERISK)
                    except Exception:
                        pass
            self.update_idletasks()
            self.after(500, lambda p=staged: self._finish_in_app_install(p))

        self._run_bg_job("Update-Download", work, on_ok=on_ok)

    def _finish_in_app_install(self, path: Path) -> None:
        """Setup starten und App beenden (nach kurzer Pause für Tray/Notify)."""
        from tkinter import messagebox

        from creality_nfc.app_update import (
            install_downloaded_setup,
            notify_install_starting,
            write_install_now_helper,
        )

        try:
            from creality_nfc.creality_watch import unregister_main_app

            self._stop_background_tray()
            unregister_main_app()
            helper = write_install_now_helper(path)
            notify_install_starting(path, helper)
            self._set_status(_t("mw.update.installer_starting"), "ok")
            install_downloaded_setup(path)
        except Exception as exc:
            log_exception("update-install", exc)
            messagebox.showerror(
                APP_NAME,
                _t("mw.update.installer_failed", exc=exc)
                + _t("mw.update.run_manual", path=path),
                parent=self,
            )

    def _get_background_tray(self) -> BackgroundTray:
        if self._background_tray is None:
            self._background_tray = BackgroundTray()
        return self._background_tray

    def _tray_mode_enabled(self) -> bool:
        return bool(getattr(self.settings, "tray_run_in_background", False))

    def _hide_to_tray(self) -> None:
        if self._shutdown_done or self._tray_hidden:
            return
        if not self._tray_mode_enabled():
            self.notify(
                "Hintergrund (Tray) ist aus — unter Einstellungen aktivieren und speichern.",
                "warn",
            )
            return
        if not tray_supported():
            self.notify(
                _t("mw.tray.unavailable"),
                "warn",
            )
            return
        tray = self._get_background_tray()
        if not tray.start(
            on_show=self._show_from_tray,
            on_quit=lambda: self.after(0, lambda: self._on_close(force=True)),
            tooltip=f"{APP_NAME} — im Hintergrund",
        ):
            self.notify(_t("mw.notify.tray_start_failed"), "warn")
            return
        self._tray_hidden = True
        try:
            self.withdraw()
        except tk.TclError:
            pass
        self._set_status(_t("mw.tray.hidden_status"), "ok")

    def _show_from_tray(self) -> None:
        try:
            self.after(0, self._do_show_from_tray)
        except tk.TclError:
            pass

    def _do_show_from_tray(self) -> None:
        self._tray_hidden = False
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
        except tk.TclError:
            pass

    def _stop_background_tray(self) -> None:
        if self._background_tray is not None:
            self._background_tray.stop()

    def _on_close(self, force: bool = False) -> None:
        if not force and self._tray_mode_enabled() and tray_supported():
            self._hide_to_tray()
            return
        if self._shutdown_done:
            return
        self._shutdown_done = True
        try:
            if hasattr(self, "_window_geom"):
                self._window_geom.save_root(self)
        except Exception:
            pass
        try:
            self._save_settings()
        except Exception:
            pass
        from app.shutdown import hard_exit_frozen, shutdown_application
        from creality_nfc.creality_watch import unregister_main_app

        unregister_main_app()
        self._stop_background_tray()
        shutdown_application(self)
        hard_exit_frozen(0)
        try:
            self.quit()
        except tk.TclError:
            pass
        super().destroy()

    def destroy(self) -> None:
        if not self._shutdown_done:
            self._on_close()
            return
        super().destroy()
