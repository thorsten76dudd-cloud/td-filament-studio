"""Einstellungen als eingebettetes Panel (kein Popup)."""

from __future__ import annotations

import threading
import tkinter as tk
import webbrowser
from collections.abc import Callable
from tkinter import ttk

from creality_nfc.app_settings import DEFAULT_SETTINGS_PATH, AppSettings
from creality_nfc.config import APP_VERSION, GITHUB_URL
from creality_nfc.i18n import t as _t
from creality_nfc.reader import CrealityNfcReader
from ui.components import scrollable_tab
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

        footer = ttk.Frame(self)
        footer.pack(side="bottom", fill="x", padx=12, pady=(4, 10))
        btn_row = ttk.Frame(footer)
        btn_row.pack(anchor="w")
        tip(
            ttk.Button(btn_row, text=_t("settings.save"), command=self._save, style="Accent.TButton"),
            _t("settings.save.tip"),
        ).pack(side="left", padx=(0, 8))
        if on_show_setup:
            tip(
                ttk.Button(btn_row, text=_t("settings.show_setup"), command=on_show_setup, style="Secondary.TButton"),
                _t("settings.show_setup.tip"),
            ).pack(side="left", padx=(0, 8))
        if on_factory_reset:
            tip(
                ttk.Button(
                    btn_row,
                    text=_t("settings.factory_reset"),
                    command=on_factory_reset,
                    style="Secondary.TButton",
                ),
                _t("settings.factory_reset.tip"),
            ).pack(side="left")

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        _canvas, inner = scrollable_tab(body)

        from creality_nfc.i18n import supported_languages, t

        lang_box = ttk.LabelFrame(inner, text=_t("settings.language"))
        lang_box.pack(fill="x", **frame_pad)
        self.language_var = tk.StringVar(value=settings.language or "de")
        lang_row = ttk.Frame(lang_box)
        lang_row.pack(fill="x", padx=8, pady=4)
        ttk.Label(lang_row, text=t("settings.language") + ":").pack(side="left")
        for code in supported_languages():
            ttk.Radiobutton(
                lang_row,
                text=t(f"language.{code}"),
                value=code,
                variable=self.language_var,
            ).pack(side="left", padx=(8, 0))
        ttk.Label(
            lang_box,
            text=t("settings.language.hint"),
            style="Muted.TLabel",
            wraplength=520,
        ).pack(anchor="w", padx=8, pady=(0, 6))

        auto = ttk.LabelFrame(inner, text=_t("settings.section.auto"))
        auto.pack(fill="x", **frame_pad)
        self.auto_read = tk.BooleanVar(value=settings.auto_read_tag)
        self.auto_write = tk.BooleanVar(value=settings.auto_write_tag)
        self.batch_write = tk.BooleanVar(value=settings.batch_write_mode)
        self.auto_sync_spool = tk.BooleanVar(value=settings.auto_sync_spool_on_tag)
        ttk.Checkbutton(auto, text=_t("settings.auto_read"), variable=self.auto_read).pack(anchor="w", padx=8)
        ttk.Checkbutton(auto, text=_t("settings.auto_write"), variable=self.auto_write).pack(anchor="w", padx=8)
        ttk.Checkbutton(auto, text=_t("settings.batch_write"), variable=self.batch_write).pack(anchor="w", padx=8)
        ttk.Checkbutton(
            auto,
            text=_t("settings.auto_sync_spool"),
            variable=self.auto_sync_spool,
        ).pack(anchor="w", padx=8)
        self.launch_with_creality = tk.BooleanVar(value=settings.launch_with_creality_print)
        ttk.Checkbutton(
            auto,
            text=_t("settings.launch_with_creality"),
            variable=self.launch_with_creality,
        ).pack(anchor="w", padx=8)
        ttk.Label(
            auto,
            text=_t("settings.launch_with_creality.hint"),
            style="Muted.TLabel",
            wraplength=520,
        ).pack(anchor="w", padx=8, pady=(0, 6))

        tray = ttk.LabelFrame(inner, text=_t("settings.section.tray_box"))
        tray.pack(fill="x", **frame_pad)
        self.tray_run_in_background = tk.BooleanVar(value=settings.tray_run_in_background)
        ttk.Checkbutton(
            tray,
            text=_t("settings.tray_close_to_bg"),
            variable=self.tray_run_in_background,
        ).pack(anchor="w", padx=8, pady=(4, 0))
        ttk.Label(
            tray,
            text=_t("settings.tray_close_to_bg.hint"),
            style="Muted.TLabel",
            wraplength=520,
        ).pack(anchor="w", padx=8, pady=(0, 6))

        serial = ttk.LabelFrame(inner, text=_t("settings.section.serial"))
        serial.pack(fill="x", **frame_pad)
        self.auto_serial = tk.BooleanVar(value=settings.auto_increment_serial)
        ttk.Checkbutton(serial, text=_t("settings.auto_serial"), variable=self.auto_serial).pack(anchor="w", padx=8)
        row = ttk.Frame(serial)
        row.pack(fill="x", padx=8, pady=4)
        ttk.Label(row, text=_t("settings.serial_fixed")).pack(side="left")
        self.fixed_serial = tk.StringVar(value=settings.fixed_serial)
        ttk.Entry(row, textvariable=self.fixed_serial, width=10).pack(side="left", padx=6)

        filament = ttk.LabelFrame(inner, text=_t("settings.section.spool_cfs"))
        filament.pack(fill="x", **frame_pad)
        self.low_filament_g = tk.IntVar(value=settings.low_filament_threshold_g)
        fl_row = ttk.Frame(filament)
        fl_row.pack(fill="x", padx=8, pady=4)
        ttk.Label(fl_row, text=_t("settings.low_filament_label")).pack(side="left")
        ttk.Spinbox(fl_row, from_=50, to=2000, textvariable=self.low_filament_g, width=6).pack(
            side="left", padx=6
        )
        self.prompt_deduct = tk.BooleanVar(value=settings.prompt_deduct_after_print)
        ttk.Checkbutton(
            filament,
            text=_t("settings.prompt_deduct"),
            variable=self.prompt_deduct,
        ).pack(anchor="w", padx=8)
        self.alert_print = tk.BooleanVar(value=getattr(settings, "alert_print_pause_error", True))
        self.alert_print_popup = tk.BooleanVar(value=getattr(settings, "alert_print_popup", True))
        self.alert_print_toast = tk.BooleanVar(value=getattr(settings, "alert_print_windows_toast", True))
        ttk.Checkbutton(
            filament,
            text=_t("settings.alert_pause_error"),
            variable=self.alert_print,
        ).pack(anchor="w", padx=8, pady=(6, 0))
        ttk.Checkbutton(
            filament,
            text=_t("settings.alert_popup"),
            variable=self.alert_print_popup,
        ).pack(anchor="w", padx=24)
        ttk.Checkbutton(
            filament,
            text=_t("settings.alert_toast"),
            variable=self.alert_print_toast,
        ).pack(anchor="w", padx=24, pady=(0, 4))
        self.alert_complete_toast = tk.BooleanVar(
            value=getattr(settings, "alert_print_complete_toast", True)
        )
        self.alert_low_toast = tk.BooleanVar(
            value=getattr(settings, "alert_low_filament_toast", True)
        )
        ttk.Checkbutton(
            filament,
            text=_t("settings.alert_complete_toast"),
            variable=self.alert_complete_toast,
        ).pack(anchor="w", padx=8)
        ttk.Checkbutton(
            filament,
            text=_t("settings.alert_low_toast"),
            variable=self.alert_low_toast,
        ).pack(anchor="w", padx=8, pady=(0, 4))
        ttk.Label(
            filament,
            text=_t("settings.alert_low.hint"),
            style="Muted.TLabel",
            wraplength=520,
        ).pack(anchor="w", padx=8, pady=(0, 4))
        self.protect_tag = tk.BooleanVar(value=getattr(settings, "protect_tag_overwrite", True))
        ttk.Checkbutton(
            filament,
            text=_t("settings.protect_tag"),
            variable=self.protect_tag,
        ).pack(anchor="w", padx=8, pady=(2, 0))
        self.default_deduct_g = tk.IntVar(value=settings.default_post_print_deduct_g)
        d_row = ttk.Frame(filament)
        d_row.pack(fill="x", padx=8, pady=(2, 4))
        ttk.Label(d_row, text=_t("settings.default_deduct")).pack(side="left")
        ttk.Spinbox(d_row, from_=0, to=500, textvariable=self.default_deduct_g, width=6).pack(
            side="left", padx=6
        )
        reader = ttk.LabelFrame(inner, text=_t("settings.section.reader"))
        reader.pack(fill="x", **frame_pad)
        names = [""] + CrealityNfcReader.list_readers_safe()
        self.reader_var = tk.StringVar(value=settings.preferred_reader)
        ttk.Combobox(reader, textvariable=self.reader_var, values=names).pack(fill="x", padx=8, pady=4)

        db_sync = ttk.LabelFrame(inner, text=_t("settings.section.material_db"))
        db_sync.pack(fill="x", **frame_pad)
        ttk.Label(
            db_sync,
            text=_t("settings.material_db.hint"),
            style="Muted.TLabel",
            wraplength=520,
        ).pack(anchor="w", padx=8, pady=(4, 8))

        merge = ttk.LabelFrame(inner, text=_t("settings.section.db_merge"))
        merge.pack(fill="x", **frame_pad)
        self.merge_var = tk.StringVar(value=settings.merge_prefer)
        ttk.Radiobutton(merge, text=_t("settings.merge.local"), value="local", variable=self.merge_var).pack(anchor="w", padx=8)
        ttk.Radiobutton(merge, text=_t("settings.merge.cloud"), value="cloud", variable=self.merge_var).pack(anchor="w", padx=8)
        ttk.Label(
            merge,
            text=_t("settings.merge.hint"),
            style="Muted.TLabel",
            wraplength=480,
        ).pack(anchor="w", padx=8, pady=(4, 0))

        updates = ttk.LabelFrame(inner, text=_t("settings.section.updates"))
        updates.pack(fill="x", **frame_pad)
        self.check_updates = tk.BooleanVar(value=settings.check_updates)
        ttk.Checkbutton(
            updates,
            text=_t("settings.updates.auto"),
            variable=self.check_updates,
        ).pack(anchor="w", padx=8)
        ttk.Label(
            updates,
            text=_t("settings.updates.hint"),
            style="Muted.TLabel",
            wraplength=520,
        ).pack(anchor="w", padx=8, pady=(0, 6))
        self._github_stats_var = tk.StringVar(value=_t("settings.github.loading"))
        ttk.Label(
            updates,
            textvariable=self._github_stats_var,
            wraplength=520,
        ).pack(anchor="w", padx=8)
        gh_row = ttk.Frame(updates)
        gh_row.pack(anchor="w", padx=8, pady=(4, 10))
        tip(
            ttk.Button(gh_row, text=_t("settings.github.refresh"), command=self._refresh_github_stats),
            _t("settings.github.refresh.tip"),
        ).pack(side="left", padx=(0, 8))
        tip(
            ttk.Button(
                gh_row,
                text=_t("settings.github.releases"),
                command=lambda: webbrowser.open(f"{GITHUB_URL}/releases"),
                style="Secondary.TButton",
            ),
            _t("settings.github.releases.tip"),
        ).pack(side="left")
        self.after(500, self._refresh_github_stats)

        self.show_setup_startup = tk.BooleanVar(value=settings.show_setup_on_startup)
        ttk.Checkbutton(
            inner,
            text=_t("settings.show_setup_startup"),
            variable=self.show_setup_startup,
        ).pack(anchor="w", padx=12, pady=(4, 12))

    def _refresh_github_stats(self) -> None:
        self._github_stats_var.set(_t("settings.github.loading"))

        def work() -> None:
            from creality_nfc.update_check import fetch_latest_release, format_setup_downloads, is_newer

            try:
                info = fetch_latest_release()
                if not info:
                    text = _t("settings.github.no_release")
                else:
                    newer = is_newer(info.version, APP_VERSION)
                    hint = _t("settings.github.update_hint") if newer else ""
                    dl = format_setup_downloads(
                        info.setup_download_count,
                        label=info.download_label,
                    )
                    text = _t("settings.github.stats_line", version=APP_VERSION, hint=hint, tag=info.tag, downloads=dl)
            except Exception as exc:
                text = _t("settings.github.failed", exc=exc)

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
        s.alert_print_pause_error = self.alert_print.get()
        s.alert_print_popup = self.alert_print_popup.get()
        s.alert_print_windows_toast = self.alert_print_toast.get()
        s.alert_print_complete_toast = self.alert_complete_toast.get()
        s.alert_low_filament_toast = self.alert_low_toast.get()
        s.default_post_print_deduct_g = int(self.default_deduct_g.get())
        s.protect_tag_overwrite = self.protect_tag.get()
        s.launch_with_creality_print = self.launch_with_creality.get()
        s.tray_run_in_background = self.tray_run_in_background.get()
        new_lang = (self.language_var.get() or "de").strip().lower()
        language_changed = new_lang != (s.language or "de")
        s.language = new_lang if new_lang in ("de", "en") else "de"
        self._on_save(s)
        if language_changed:
            try:
                from tkinter import messagebox

                from creality_nfc.i18n import t

                messagebox.showinfo(
                    title=t("settings.title"),
                    message=t("settings.language.hint"),
                    parent=self,
                )
            except Exception:
                pass
