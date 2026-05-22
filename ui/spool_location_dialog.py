"""Übersicht: Wo liegt welche Spule?"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from creality_nfc.printer_store import load_printers
from creality_nfc.spool_location import spools_at_printer, spools_in_storage
from ui.dialog_theme import prepare_toplevel
from ui.rounded_widgets import rounded_button
from ui.theme import BG

if TYPE_CHECKING:
    from creality_nfc.spool_inventory import SpoolInventory


def show_spool_location_dialog(parent: tk.Misc, inventory: SpoolInventory) -> None:
    dlg = tk.Toplevel(parent)
    dlg.title("Spulen-Standort")
    prepare_toplevel(
        dlg,
        parent,
        width=720,
        height=480,
        geometry_key="spool_location",
        min_width=560,
        min_height=320,
    )

    ttk.Label(
        dlg,
        text="Physische Zuordnung und zuletzt am Drucker gesehen (CFS).",
        style="Muted.TLabel",
        wraplength=660,
    ).pack(anchor="w", padx=12, pady=(10, 6))

    cols = ("label", "material", "rest", "location", "seen", "slot")
    tree = ttk.Treeview(dlg, columns=cols, show="headings", height=16)
    for c, t, w in (
        ("label", "Spule", 140),
        ("material", "Material", 100),
        ("rest", "Rest", 60),
        ("location", "Zugeordnet", 120),
        ("seen", "Zuletzt gesehen", 120),
        ("slot", "CFS-Slot", 70),
    ):
        tree.heading(c, text=t)
        tree.column(c, width=w)
    sy = ttk.Scrollbar(dlg, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sy.set)
    tree.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=4)
    sy.pack(side="right", fill="y", pady=4, padx=(0, 12))

    printers = [p.name for p in load_printers()]
    sections: list[tuple[str, list]] = []
    for pname in printers:
        items = spools_at_printer(inventory, pname)
        if items:
            sections.append((f"Drucker: {pname}", items))
    storage = spools_in_storage(inventory)
    if storage:
        sections.append(("Nur Lager / unzugeordnet", storage))
    other = [
        sp
        for sp in inventory.sorted_spools()
        if sp not in [x for _t, lst in sections for x in lst]
    ]
    if other:
        sections.append(("Sonstige", other))

    for title, spools in sections:
        tree.insert("", tk.END, values=(f"— {title} —", "", "", "", "", ""))
        for sp in spools:
            rest = f"{sp.remaining_g} g" if sp.remaining_g is not None else "—"
            tree.insert(
                "",
                tk.END,
                values=(
                    sp.label,
                    sp.material_name or sp.brand or "—",
                    rest,
                    sp.location_printer or "—",
                    sp.last_seen_printer or "—",
                    sp.last_seen_slot_label or sp.cfs_slot_label() or "—",
                ),
            )

    foot = tk.Frame(dlg, bg=BG)
    foot.pack(side="bottom", fill="x", padx=14, pady=10)
    rounded_button(foot, "Schließen", dlg.destroy, variant="accent", compact=True).pack(
        side="right"
    )
