"""Links zu bewährten RFID-Tag-Haltern (Printables / Creality Cloud)."""

from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import ttk

from app.bundled_assets import save_bundled_plastic_holder_stls
from creality_nfc.i18n import t as _t
from ui.components import scrollable_tab
from ui.dialog_theme import prepare_toplevel
from ui.hardware_links import amazon_hardware_links

URL_PLASTIC_TAG_HOLDER_THINGIVERSE = "https://www.thingiverse.com/thing:7356949"
URL_PLASTIC_SPOOL_HEX = "https://www.printables.com/model/1204576-creality-cfs-rfid-reusable-spool-hex"


def _tag_holder_links() -> tuple[tuple[str, str, str], ...]:
    return (
        (
            _t("thl.hex_title"),
            _t("thl.hex_desc"),
            URL_PLASTIC_SPOOL_HEX,
        ),
        (
            _t("thl.cardboard_title"),
            _t("thl.cardboard_only"),
            "https://www.printables.com/model/1159112-k2-cfs-rdif-tag-holder-for-creality-cardboard-spoo",
        ),
        (
            _t("thl.cloud_cardboard_title"),
            _t("thl.cloud_cardboard_desc"),
            "https://www.crealitycloud.com/model-detail/rfid-cfs-tag-holders-cardboard-spools",
        ),
        (
            _t("thl.amoy_title"),
            _t("thl.large_spools"),
            "https://www.printables.com/model/1220708-creality-cfs-rfid-spool-tab",
        ),
        (
            _t("thl.extrudr_title"),
            _t("thl.extrudr_desc"),
            "https://www.printables.com/model/1151473-creality-cfs-rfid-tag-holder-for-extrudr-spools",
        ),
        (
            _t("thl.universal_title"),
            _t("thl.small_case"),
            "https://www.printables.com/model/1280735-cfs-rfid-tag-for-spools",
        ),
    )


TAG_HOLDER_LINKS = _tag_holder_links()


class TagHolderLinksDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self.title(_t("thl.dialog_title"))
        self.minsize(500, 420)

        pad = {"padx": 12, "pady": 4}
        ttk.Label(
            self,
            text=_t("thl.intro"),
            wraplength=540,
            justify="left",
        ).pack(anchor="w", **pad)
        quick = ttk.Frame(self)
        quick.pack(fill="x", padx=12, pady=(0, 6))
        ttk.Label(quick, text=_t("thl.quick_access"), style="Muted.TLabel").pack(side="left", padx=(0, 8))
        ttk.Button(
            quick,
            text=_t("thl.save_stl"),
            command=self._save_plastic_holder,
            style="Accent.TButton",
        ).pack(side="left", padx=(0, 8))

        featured = ttk.LabelFrame(
            self,
            text=_t("thl.featured_label"),
            padding=10,
        )
        featured.pack(fill="x", padx=12, pady=(0, 8))
        ttk.Label(
            featured,
            text=_t("thl.plastic_desc"),
            wraplength=540,
            justify="left",
        ).pack(anchor="w")
        btn_row = ttk.Frame(featured)
        btn_row.pack(anchor="w", pady=(8, 0))
        ttk.Button(
            btn_row,
            text=_t("thl.save_all_stl"),
            command=self._save_plastic_holder,
            style="Accent.TButton",
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            btn_row,
            text=_t("thl.open_thingiverse"),
            command=lambda: webbrowser.open(URL_PLASTIC_TAG_HOLDER_THINGIVERSE),
            style="Secondary.TButton",
        ).pack(side="left")

        hw = ttk.LabelFrame(
            self,
            text=_t("thl.hw_label"),
            padding=10,
        )
        hw.pack(fill="x", padx=12, pady=(0, 8))
        ttk.Label(
            hw,
            text=_t("thl.hw_disclaimer"),
            wraplength=540,
            justify="left",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(0, 6))
        for title, desc, url in amazon_hardware_links():
            row_hw = ttk.Frame(hw)
            row_hw.pack(fill="x", pady=(0, 4))
            ttk.Label(row_hw, text=f"{title}: {desc}", wraplength=420, justify="left").pack(
                side="left", fill="x", expand=True
            )
            ttk.Button(
                row_hw,
                text="Amazon",
                command=lambda u=url: webbrowser.open(u),
                style="Secondary.TButton",
            ).pack(side="right")

        list_host = ttk.Frame(self)
        list_host.pack(fill="both", expand=True, padx=12, pady=(0, 4))
        _, scroll_inner = scrollable_tab(list_host)

        for title, desc, url in _tag_holder_links():
            row = ttk.LabelFrame(scroll_inner, text=f"  {title}  ", padding=8)
            row.pack(fill="x", pady=(0, 8))
            ttk.Label(row, text=desc, wraplength=500, justify="left").pack(anchor="w")
            ttk.Button(
                row,
                text=_t("thl.btn.open_browser"),
                command=lambda u=url: webbrowser.open(u),
                style="Secondary.TButton",
            ).pack(anchor="w", pady=(6, 0))

        footer = ttk.Frame(self)
        footer.pack(fill="x", side="bottom", padx=12, pady=(4, 12))
        ttk.Label(
            footer,
            text=_t("thl.footer_hint"),
            style="Muted.TLabel",
            wraplength=540,
        ).pack(anchor="w", pady=(0, 8))
        ttk.Button(footer, text=_t("thl.btn.close"), command=self.destroy).pack(anchor="e")
        prepare_toplevel(self, parent, width=600, height=640, geometry_key="tag_holder_links")

    def _save_plastic_holder(self) -> None:
        save_bundled_plastic_holder_stls(self)
