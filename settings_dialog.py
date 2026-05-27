"""App settings dialog."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from creality_nfc.app_settings import AppSettings
from creality_nfc.i18n import t as _t
from creality_nfc.reader import CrealityNfcReader
from ui.dialog_theme import prepare_toplevel


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, settings: AppSettings) -> None:
        super().__init__(parent)
        self.title(_t("sd.title"))
        self.result: AppSettings | None = None
        self._settings = settings

        frame_pad = {"padx": 10, "pady": 6}
        auto = ttk.LabelFrame(self, text=_t("sd.auto_label"))
        auto.pack(fill="x", **frame_pad)

        self.auto_read = tk.BooleanVar(value=settings.auto_read_tag)
        self.auto_write = tk.BooleanVar(value=settings.auto_write_tag)
        ttk.Checkbutton(auto, text=_t("sd.auto_read"), variable=self.auto_read).pack(
            anchor="w", padx=8, pady=2
        )
        ttk.Checkbutton(
            auto, text=_t("sd.auto_write"), variable=self.auto_write
        ).pack(anchor="w", padx=8, pady=2)
        self.batch_write = tk.BooleanVar(value=settings.batch_write_mode)
        ttk.Checkbutton(
            auto,
            text=_t("sd.batch_wait"),
            variable=self.batch_write,
        ).pack(anchor="w", padx=8, pady=2)

        serial = ttk.LabelFrame(self, text=_t("sd.serial_label"))
        serial.pack(fill="x", **frame_pad)
        self.auto_serial = tk.BooleanVar(value=settings.auto_increment_serial)
        ttk.Checkbutton(
            serial, text=_t("sd.auto_serial"), variable=self.auto_serial
        ).pack(anchor="w", padx=8, pady=2)
        row = ttk.Frame(serial)
        row.pack(fill="x", padx=8, pady=4)
        ttk.Label(row, text=_t("sd.fixed_label")).pack(side="left")
        self.fixed_serial = tk.StringVar(value=settings.fixed_serial)
        ttk.Entry(row, textvariable=self.fixed_serial, width=10).pack(side="left", padx=6)
        ttk.Label(row, text=_t("sd.next_serial", sn=settings.next_serial)).pack(side="left")

        reader = ttk.LabelFrame(self, text=_t("sd.reader_label"))
        reader.pack(fill="x", **frame_pad)
        names = [""] + CrealityNfcReader.list_readers_safe()
        self.reader_var = tk.StringVar(value=settings.preferred_reader)
        ttk.Label(reader, text=_t("sd.preferred_reader")).pack(anchor="w", padx=8)
        ttk.Combobox(reader, textvariable=self.reader_var, values=names).pack(
            fill="x", padx=8, pady=4
        )
        if len(names) <= 1:
            ttk.Label(
                reader,
                text=_t("sd.no_reader"),
                foreground="#b45309",
                wraplength=380,
            ).pack(anchor="w", padx=8, pady=4)

        merge = ttk.LabelFrame(self, text=_t("sd.db_merge_title"))
        merge.pack(fill="x", **frame_pad)
        self.merge_var = tk.StringVar(value=settings.merge_prefer)
        ttk.Radiobutton(
            merge, text=_t("sd.merge_local_keep"), value="local", variable=self.merge_var
        ).pack(anchor="w", padx=8)
        ttk.Radiobutton(
            merge, text=_t("sd.merge_cloud_overwrite"), value="cloud", variable=self.merge_var
        ).pack(anchor="w", padx=8)

        self.check_updates = tk.BooleanVar(value=settings.check_updates)
        ttk.Checkbutton(self, text=_t("sd.check_updates_on_start"), variable=self.check_updates).pack(
            anchor="w", padx=12, pady=4
        )

        btns = ttk.Frame(self)
        btns.pack(fill="x", pady=10, padx=10)
        ttk.Button(btns, text=_t("btn.cancel"), command=self.destroy).pack(side="right")
        ttk.Button(btns, text=_t("btn.save"), command=self._save).pack(side="right", padx=8)

        prepare_toplevel(self, parent, width=440, height=460, geometry_key="settings")

    def _save(self) -> None:
        s = self._settings
        s.auto_read_tag = self.auto_read.get()
        s.auto_write_tag = self.auto_write.get()
        s.auto_increment_serial = self.auto_serial.get()
        s.fixed_serial = self.fixed_serial.get().strip() or "000001"
        s.preferred_reader = self.reader_var.get().strip()
        s.merge_prefer = self.merge_var.get()
        s.check_updates = self.check_updates.get()
        s.batch_write_mode = self.batch_write.get()
        self.result = s
        self.destroy()
