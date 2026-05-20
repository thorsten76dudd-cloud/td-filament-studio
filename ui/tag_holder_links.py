"""Links zu bewährten RFID-Tag-Haltern (Printables / Creality Cloud)."""

from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import ttk

from app.bundled_assets import save_bundled_plastic_holder_stls
from ui.components import scrollable_tab
from ui.dialog_theme import prepare_toplevel

# (Titel, Kurzbeschreibung, URL)
URL_PLASTIC_SPOOL_HEX = "https://www.printables.com/model/1204576-creality-cfs-rfid-reusable-spool-hex"

TAG_HOLDER_LINKS: tuple[tuple[str, str, str], ...] = (
    (
        "Creality wiederverwendbare Spule (Hex + RFID)",
        "Komplette Hex-Spule zum Drucken mit eingebautem 25-mm-Tag-Fach (Remix, JBFuller).",
        URL_PLASTIC_SPOOL_HEX,
    ),
    (
        "Creality Kartonspulen (K2 / CFS)",
        "Nur für Kartonspulen — nicht für Kunststoffrollen.",
        "https://www.printables.com/model/1159112-k2-cfs-rdif-tag-holder-for-creality-cardboard-spoo",
    ),
    (
        "Creality Cloud — Kartonspulen",
        "3MF auf Creality Cloud (offizielle Community-Modelle).",
        "https://www.crealitycloud.com/model-detail/rfid-cfs-tag-holders-cardboard-spools",
    ),
    (
        "AMOYBABY / Flashforge-Spulen",
        "Für größere Spulen (~190 mm), Snap-in für 25-mm-Tags.",
        "https://www.printables.com/model/1220708-creality-cfs-rfid-spool-tab",
    ),
    (
        "Extrudr-Spulen",
        "Steckt in die Seitenbohrung der Extrudr-1-kg-Spule.",
        "https://www.printables.com/model/1151473-creality-cfs-rfid-tag-holder-for-extrudr-spools",
    ),
    (
        "Universal (einfach, 2× pro Spule)",
        "Kleine Hülle zum Aufkleben — pro Spule zwei Stück drucken.",
        "https://www.printables.com/model/1280735-cfs-rfid-tag-for-spools",
    ),
)


class TagHolderLinksDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self.title("RFID-Tag Halter — Download-Links")
        self.minsize(500, 420)

        pad = {"padx": 12, "pady": 4}
        ttk.Label(
            self,
            text="3D-Modelle für 25-mm-MIFARE-Classic-1K-Tags (Creality CFS).\n"
            "Für offizielle Creality-Kunststoffrollen: zuerst die mitgelieferten STL unten — Karton-Modelle passen dort nicht.",
            wraplength=540,
            justify="left",
        ).pack(anchor="w", **pad)
        quick = ttk.Frame(self)
        quick.pack(fill="x", padx=12, pady=(0, 6))
        ttk.Label(quick, text="Schnellzugriff:", style="Muted.TLabel").pack(side="left", padx=(0, 8))
        ttk.Button(
            quick,
            text="Tag-Halter STL speichern…",
            command=self._save_plastic_holder,
            style="Accent.TButton",
        ).pack(side="left", padx=(0, 8))

        featured = ttk.LabelFrame(
            self,
            text="  TD Filament Studio — Tag-Halter (Kunststoffspule)  ",
            padding=10,
        )
        featured.pack(fill="x", padx=12, pady=(0, 8))
        ttk.Label(
            featured,
            text=(
                "Mitgelieferte STL für 25-mm-MIFARE-Tags an offiziellen Creality-Kunststoffspulen.\n"
                "5 Teile: Deckel, Komponente 1–4. Pro Spule 2× komplett drucken (links + rechts am Flansch)."
            ),
            wraplength=540,
            justify="left",
        ).pack(anchor="w")
        btn_row = ttk.Frame(featured)
        btn_row.pack(anchor="w", pady=(8, 0))
        ttk.Button(
            btn_row,
            text="Alle STL in Ordner speichern…",
            command=self._save_plastic_holder,
            style="Accent.TButton",
        ).pack(side="left")

        list_host = ttk.Frame(self)
        list_host.pack(fill="both", expand=True, padx=12, pady=(0, 4))
        _, scroll_inner = scrollable_tab(list_host)

        for title, desc, url in TAG_HOLDER_LINKS:
            row = ttk.LabelFrame(scroll_inner, text=f"  {title}  ", padding=8)
            row.pack(fill="x", pady=(0, 8))
            ttk.Label(row, text=desc, wraplength=500, justify="left").pack(anchor="w")
            ttk.Button(
                row,
                text="Im Browser öffnen",
                command=lambda u=url: webbrowser.open(u),
                style="Secondary.TButton",
            ).pack(anchor="w", pady=(6, 0))

        footer = ttk.Frame(self)
        footer.pack(fill="x", side="bottom", padx=12, pady=(4, 12))
        ttk.Label(
            footer,
            text="Hinweis: Pro Spule 2× drucken (links + rechts am Flansch, ~25 mm vom Rand).",
            style="Muted.TLabel",
            wraplength=540,
        ).pack(anchor="w", pady=(0, 8))
        ttk.Button(footer, text="Schließen", command=self.destroy).pack(anchor="e")
        prepare_toplevel(self, parent, width=580, height=560)

    def _save_plastic_holder(self) -> None:
        save_bundled_plastic_holder_stls(self)
