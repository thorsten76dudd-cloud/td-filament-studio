"""Übersicht: Wo liegt welche Spule?"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from creality_nfc.i18n import t as _t
from creality_nfc.printer_store import load_printers
from creality_nfc.spool_location import spools_at_printer, spools_in_storage
from ui.color_swatch import make_swatch_photo
from ui.dialog_theme import begin_table_dialog, show_table_dialog
from ui.rounded_widgets import rounded_button
from ui.theme import BG

if TYPE_CHECKING:
    from creality_nfc.spool_inventory import SpoolInventory


def _build_sections(inventory: SpoolInventory) -> list[tuple[str, list]]:
    sections: list[tuple[str, list]] = []
    seen: set[str] = set()
    for prof in load_printers():
        pname = prof.name.strip()
        if not pname:
            continue
        items = spools_at_printer(inventory, pname)
        if items:
            sections.append((_t("sld.section.printer", name=pname), items))
            seen.update(sp.id for sp in items)
    storage = spools_in_storage(inventory)
    if storage:
        sections.append((_t("sld.section.storage"), storage))
        seen.update(sp.id for sp in storage)
    rest = [sp for sp in inventory.sorted_spools() if sp.id not in seen]
    if rest:
        sections.append((_t("sld.section.all"), rest))
    return sections


def show_spool_location_dialog(parent: tk.Misc, inventory: SpoolInventory) -> None:
    sections = _build_sections(inventory)
    row_count = sum(len(spools) + 1 for _, spools in sections) if sections else 1

    dlg, body, footer = begin_table_dialog(
        parent,
        title=_t("sld.title", n=row_count),
        width=980,
        height=580,
        min_width=820,
        min_height=440,
    )

    foot_inner = tk.Frame(footer, bg=BG)
    foot_inner.pack(fill="x")
    rounded_button(foot_inner, _t("sld.btn.close"), dlg.destroy, variant="accent", compact=True).pack(
        side="right"
    )

    ttk.Label(
        body,
        text=_t("sld.intro"),
        style="Muted.TLabel",
        wraplength=760,
    ).pack(anchor="w", padx=12, pady=(10, 4))

    tree_wrap = ttk.Frame(body)
    tree_wrap.pack(fill="both", expand=True, padx=12, pady=(4, 6))
    tree_wrap.grid_rowconfigure(0, weight=1)
    tree_wrap.grid_columnconfigure(0, weight=1)

    swatch_cache: dict[str, tk.PhotoImage] = {}
    cols = ("label", "material", "rest", "location", "seen", "slot")
    tree = ttk.Treeview(tree_wrap, columns=cols, show="tree headings", height=18)
    tree.heading("#0", text=_t("sld.col.color"), anchor="center")
    tree.column("#0", width=44, minwidth=44, stretch=False, anchor="center")
    for c, t, w, mn, stretch in (
        ("label", _t("sld.col.spool"), 200, 120, True),
        ("material", _t("sld.col.material"), 120, 90, False),
        ("rest", _t("sld.col.rest"), 80, 64, False),
        ("location", _t("sld.col.location"), 180, 120, True),
        ("seen", _t("sld.col.seen"), 180, 130, True),
        ("slot", _t("sld.col.slot"), 88, 72, False),
    ):
        tree.heading(c, text=t)
        tree.column(c, width=w, minwidth=mn, stretch=stretch)
    sy = ttk.Scrollbar(tree_wrap, orient="vertical", command=tree.yview)
    sx = ttk.Scrollbar(tree_wrap, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
    tree.grid(row=0, column=0, sticky="nsew")
    sy.grid(row=0, column=1, sticky="ns")
    sx.grid(row=1, column=0, sticky="ew")

    if not sections:
        tree.insert(
            "",
            tk.END,
            text="",
            values=(
                _t("sld.empty"),
                "—",
                "—",
                "—",
                "—",
                "—",
            ),
        )
    else:
        for title, spools in sections:
            tree.insert("", tk.END, text="", values=(f"— {title} —", "", "", "", "", ""))
            for sp in spools:
                rest = f"{sp.remaining_g} g" if sp.remaining_g is not None else "—"
                loc = sp.location_display() or "—"
                seen = (sp.last_seen_printer or "").strip() or "—"
                slot = sp.last_seen_slot_label or sp.cfs_slot_label() or "—"
                swatch = make_swatch_photo(dlg, sp.color_hex, cache=swatch_cache)
                tree.insert(
                    "",
                    tk.END,
                    image=swatch,
                    text="",
                    values=(
                        sp.label,
                        sp.material_name or sp.brand or "—",
                        rest,
                        loc,
                        seen,
                        slot,
                    ),
                )

    dlg._spool_loc_swatch_cache = swatch_cache  # Referenz halten (PhotoImage)

    ttk.Label(
        body,
        text=_t("sld.footer"),
        style="Muted.TLabel",
        wraplength=760,
    ).pack(anchor="w", padx=12, pady=(0, 8))

    show_table_dialog(dlg)
