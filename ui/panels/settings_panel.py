"""Einstellungen als eingebettetes Panel (kein Popup)."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from creality_nfc.app_settings import DEFAULT_SETTINGS_PATH, AppSettings
from creality_nfc.reader import CrealityNfcReader
from ui.dialog_theme import theme_dialog
from ui.tooltip import tip


class SettingsPanel(ttk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        settings: AppSettings,
        on_save,
        on_show_setup: Callable[[], None] | None = None,
        on_factory_reset: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        theme_dialog(self)
        self._settings = settings
        self._on_save = on_save
        self._on_factory_reset = on_factory_reset
        frame_pad = {"padx": 12, "pady": 8}

        auto = ttk.LabelFrame(self, text="Automatik")
        auto.pack(fill="x", **frame_pad)
        self.auto_read = tk.BooleanVar(value=settings.auto_read_tag)
        self.auto_write = tk.BooleanVar(value=settings.auto_write_tag)
        self.batch_write = tk.BooleanVar(value=settings.batch_write_mode)
        self.auto_sync_spool = tk.BooleanVar(value=settings.auto_sync_spool_on_tag)
        ttk.Checkbutton(auto, text="Tag automatisch lesen", variable=self.auto_read).pack(anchor="w", padx=8)
        ttk.Checkbutton(auto, text="Tag automatisch schreiben", variable=self.auto_write).pack(anchor="w", padx=8)
        ttk.Checkbutton(auto, text="Stapelmodus", variable=self.batch_write).pack(anchor="w", padx=8)
        ttk.Checkbutton(
            auto,
            text="Nach Tag-Schreiben: Spule in „Meine Spulen“ anlegen/aktualisieren",
            variable=self.auto_sync_spool,
        ).pack(anchor="w", padx=8)
        self.launch_with_creality = tk.BooleanVar(value=settings.launch_with_creality_print)
        ttk.Checkbutton(
            auto,
            text="Mit Creality Print starten (Hintergrund-Wächter)",
            variable=self.launch_with_creality,
        ).pack(anchor="w", padx=8)
        ttk.Label(
            auto,
            text="Ein kleiner Helfer läuft im Hintergrund und öffnet TD Filament Studio, "
            "wenn Creality Print startet. Nach dem Speichern einmal aktiv lassen oder PC neu starten.",
            style="Muted.TLabel",
            wraplength=520,
        ).pack(anchor="w", padx=8, pady=(0, 6))

        serial = ttk.LabelFrame(self, text="Seriennummer")
        serial.pack(fill="x", **frame_pad)
        self.auto_serial = tk.BooleanVar(value=settings.auto_increment_serial)
        ttk.Checkbutton(serial, text="Automatisch hochzählen", variable=self.auto_serial).pack(anchor="w", padx=8)
        row = ttk.Frame(serial)
        row.pack(fill="x", padx=8, pady=4)
        ttk.Label(row, text="Fest:").pack(side="left")
        self.fixed_serial = tk.StringVar(value=settings.fixed_serial)
        ttk.Entry(row, textvariable=self.fixed_serial, width=10).pack(side="left", padx=6)

        filament = ttk.LabelFrame(self, text="Spulen & CFS")
        filament.pack(fill="x", **frame_pad)
        self.low_filament_g = tk.IntVar(value=settings.low_filament_threshold_g)
        fl_row = ttk.Frame(filament)
        fl_row.pack(fill="x", padx=8, pady=4)
        ttk.Label(fl_row, text="Warnung Rest unter (g):").pack(side="left")
        ttk.Spinbox(fl_row, from_=50, to=2000, textvariable=self.low_filament_g, width=6).pack(
            side="left", padx=6
        )
        self.prompt_deduct = tk.BooleanVar(value=settings.prompt_deduct_after_print)
        ttk.Checkbutton(
            filament,
            text="Nach Druckende: Verbrauch von CFS-Spule abfragen",
            variable=self.prompt_deduct,
        ).pack(anchor="w", padx=8)
        self.protect_tag = tk.BooleanVar(value=getattr(settings, "protect_tag_overwrite", True))
        ttk.Checkbutton(
            filament,
            text="Vor Tag-Schreiben: warnen wenn Chip schon Daten hat",
            variable=self.protect_tag,
        ).pack(anchor="w", padx=8, pady=(2, 0))
        self.default_deduct_g = tk.IntVar(value=settings.default_post_print_deduct_g)
        d_row = ttk.Frame(filament)
        d_row.pack(fill="x", padx=8, pady=(2, 4))
        ttk.Label(d_row, text="Standard-Abzug (g, 0 = schätzen):").pack(side="left")
        ttk.Spinbox(d_row, from_=0, to=500, textvariable=self.default_deduct_g, width=6).pack(
            side="left", padx=6
        )
        reader = ttk.LabelFrame(self, text="NFC-Reader")
        reader.pack(fill="x", **frame_pad)
        names = [""] + CrealityNfcReader.list_readers_safe()
        self.reader_var = tk.StringVar(value=settings.preferred_reader)
        ttk.Combobox(reader, textvariable=self.reader_var, values=names).pack(fill="x", padx=8, pady=4)

        db_sync = ttk.LabelFrame(self, text="Material-Datenbank → Drucker (SSH)")
        db_sync.pack(fill="x", **frame_pad)
        self.auto_push_db = tk.BooleanVar(value=getattr(settings, "auto_push_db_to_printer", False))
        self.auto_push_options = tk.BooleanVar(
            value=getattr(settings, "auto_push_options_with_db", True)
        )
        self.auto_reboot_db = tk.BooleanVar(
            value=getattr(settings, "auto_reboot_after_db_push", False)
        )
        ttk.Checkbutton(
            db_sync,
            text="Nach „In Datenbank speichern“ automatisch zum Drucker senden",
            variable=self.auto_push_db,
        ).pack(anchor="w", padx=8)
        ttk.Checkbutton(
            db_sync,
            text="Dabei Display-Menü (material_options.json) mit aktualisieren",
            variable=self.auto_push_options,
        ).pack(anchor="w", padx=8)
        ttk.Checkbutton(
            db_sync,
            text="Danach Drucker neu starten (SSH + WLAN; sonst am Display)",
            variable=self.auto_reboot_db,
        ).pack(anchor="w", padx=8, pady=(0, 4))
        for var in (self.auto_push_db, self.auto_push_options, self.auto_reboot_db):
            var.trace_add("write", lambda *_a: self._persist_db_sync_flags())
        ttk.Label(
            db_sync,
            text="Voraussetzung: Drucker-IP und SSH-Passwort (Tab Material-Datenbank). "
            "Haken fuer Upload/Neustart gelten sofort (ohne extra Speichern). "
            "Creality Print bekommt die Daten nicht automatisch — nur der K2.",
            style="Muted.TLabel",
            wraplength=520,
        ).pack(anchor="w", padx=8, pady=(0, 6))

        merge = ttk.LabelFrame(self, text="DB-Merge")
        merge.pack(fill="x", **frame_pad)
        self.merge_var = tk.StringVar(value=settings.merge_prefer)
        ttk.Radiobutton(merge, text="Konflikt: lokal behalten", value="local", variable=self.merge_var).pack(anchor="w", padx=8)
        ttk.Radiobutton(merge, text="Konflikt: Cloud überschreiben", value="cloud", variable=self.merge_var).pack(anchor="w", padx=8)
        ttk.Label(
            merge,
            text="Geschützte Profile (Haken im Filament-Editor) werden bei Cloud/Drucker nie überschrieben.",
            style="Muted.TLabel",
            wraplength=480,
        ).pack(anchor="w", padx=8, pady=(4, 0))

        self.check_updates = tk.BooleanVar(value=settings.check_updates)
        ttk.Checkbutton(self, text="Beim Start auf Updates prüfen", variable=self.check_updates).pack(anchor="w", padx=12)
        self.show_setup_startup = tk.BooleanVar(value=settings.show_setup_on_startup)
        ttk.Checkbutton(
            self,
            text="Ersteinrichtung bei jedem Programmstart anzeigen",
            variable=self.show_setup_startup,
        ).pack(anchor="w", padx=12, pady=(4, 0))

        btn_row = ttk.Frame(self)
        btn_row.pack(anchor="w", padx=12, pady=16)
        tip(
            ttk.Button(btn_row, text="Einstellungen speichern", command=self._save, style="Accent.TButton"),
            "Alle Einstellungen dauerhaft speichern und anwenden.",
        ).pack(side="left", padx=(0, 8))
        if on_show_setup:
            tip(
                ttk.Button(btn_row, text="Ersteinrichtung…", command=on_show_setup, style="Secondary.TButton"),
                "Checkliste: Smartcard, Reader, Datenbank.",
            ).pack(side="left", padx=(0, 8))
        if on_factory_reset:
            tip(
                ttk.Button(
                    btn_row,
                    text="Programm zurücksetzen…",
                    command=on_factory_reset,
                    style="Secondary.TButton",
                ),
                "Alle lokalen Daten löschen (wie Neuinstallation). Vorher ZIP-Backup empfohlen!",
            ).pack(side="left")

    def _persist_db_sync_flags(self) -> None:
        """DB-Sync-Haken sofort in app_settings.json (ohne Popup)."""
        s = self._settings
        s.auto_push_db_to_printer = self.auto_push_db.get()
        s.auto_push_options_with_db = self.auto_push_options.get()
        s.auto_reboot_after_db_push = self.auto_reboot_db.get()
        s.save(DEFAULT_SETTINGS_PATH)

    def _save(self) -> None:
        s = self._settings
        s.auto_read_tag = self.auto_read.get()
        s.auto_write_tag = self.auto_write.get()
        s.auto_sync_spool_on_tag = self.auto_sync_spool.get()
        s.batch_write_mode = self.batch_write.get()
        s.auto_increment_serial = self.auto_serial.get()
        s.fixed_serial = self.fixed_serial.get().strip() or "000001"
        s.preferred_reader = self.reader_var.get().strip()
        s.merge_prefer = self.merge_var.get()
        s.check_updates = self.check_updates.get()
        s.show_setup_on_startup = self.show_setup_startup.get()
        s.low_filament_threshold_g = int(self.low_filament_g.get())
        s.prompt_deduct_after_print = self.prompt_deduct.get()
        s.default_post_print_deduct_g = int(self.default_deduct_g.get())
        s.protect_tag_overwrite = self.protect_tag.get()
        s.launch_with_creality_print = self.launch_with_creality.get()
        s.auto_push_db_to_printer = self.auto_push_db.get()
        s.auto_push_options_with_db = self.auto_push_options.get()
        s.auto_reboot_after_db_push = self.auto_reboot_db.get()
        self._on_save(s)
