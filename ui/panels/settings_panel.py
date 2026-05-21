"""Einstellungen als eingebettetes Panel (kein Popup)."""

from __future__ import annotations

import threading
import tkinter as tk
import webbrowser
from collections.abc import Callable
from tkinter import ttk

from creality_nfc.app_settings import DEFAULT_SETTINGS_PATH, AppSettings
from creality_nfc.config import APP_VERSION, GITHUB_URL
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
            text="Ein Helfer läuft im Hintergrund (auch nach Windows-Anmeldung) und öffnet TD Filament Studio, "
            "wenn Creality Print startet. Einstellung speichern — danach reicht Creality Print allein.",
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

        db_sync = ttk.LabelFrame(self, text="Material-Datenbank (nur Lesen)")
        db_sync.pack(fill="x", **frame_pad)
        ttk.Label(
            db_sync,
            text="Der Drucker wird nicht per SSH beschrieben (sicherer Modus). "
            "Profile nur mit „Vom Drucker“ holen und lokal bearbeiten. "
            "Druckparameter am K2 änderst du in Creality Print.",
            style="Muted.TLabel",
            wraplength=520,
        ).pack(anchor="w", padx=8, pady=(4, 8))

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

        updates = ttk.LabelFrame(self, text="Updates & GitHub")
        updates.pack(fill="x", **frame_pad)
        self.check_updates = tk.BooleanVar(value=settings.check_updates)
        ttk.Checkbutton(
            updates,
            text="Automatisch auf Updates hinweisen (beim Start und alle 4 Stunden)",
            variable=self.check_updates,
        ).pack(anchor="w", padx=8)
        ttk.Label(
            updates,
            text="Bei neuer Version erscheint ein Dialog mit Installations-Optionen.",
            style="Muted.TLabel",
            wraplength=520,
        ).pack(anchor="w", padx=8, pady=(0, 6))
        self._github_stats_var = tk.StringVar(value="GitHub-Statistik: wird geladen …")
        ttk.Label(
            updates,
            textvariable=self._github_stats_var,
            wraplength=520,
        ).pack(anchor="w", padx=8)
        gh_row = ttk.Frame(updates)
        gh_row.pack(anchor="w", padx=8, pady=(4, 8))
        tip(
            ttk.Button(gh_row, text="GitHub-Statistik aktualisieren", command=self._refresh_github_stats),
            "Lädt Release-Tag und Setup-Download-Zähler von GitHub (API).",
        ).pack(side="left", padx=(0, 8))
        tip(
            ttk.Button(
                gh_row,
                text="Releases im Browser",
                command=lambda: webbrowser.open(f"{GITHUB_URL}/releases"),
                style="Secondary.TButton",
            ),
            "GitHub-Releases-Seite öffnen.",
        ).pack(side="left")
        self.after(500, self._refresh_github_stats)

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

    def _refresh_github_stats(self) -> None:
        self._github_stats_var.set("GitHub-Statistik: wird geladen …")

        def work() -> None:
            from creality_nfc.update_check import fetch_latest_release, format_setup_downloads, is_newer

            try:
                info = fetch_latest_release()
                if not info:
                    text = "GitHub: keine Release-Infos erreichbar."
                else:
                    newer = is_newer(info.version, APP_VERSION)
                    hint = " — Update verfügbar!" if newer else ""
                    dl = format_setup_downloads(
                        info.setup_download_count,
                        label=info.download_label,
                    )
                    text = (
                        f"Installiert: {APP_VERSION}{hint}\n"
                        f"GitHub neuestes Release: {info.tag}\n"
                        f"{dl}"
                    )
            except Exception as exc:
                text = f"GitHub-Statistik fehlgeschlagen: {exc}"

            self.after(0, lambda: self._github_stats_var.set(text))

        threading.Thread(target=work, name="github-stats", daemon=True).start()

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
        self._on_save(s)
