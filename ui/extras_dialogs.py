"""Zusatz-Dialoge: Druck-Historie, CFS-Batch-Übersicht."""

from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import filedialog, ttk
from typing import TYPE_CHECKING, Any

from creality_nfc.cfs_adopt import CfsMeta, CfsSlotInfo, parse_cfs_meta, parse_cfs_slots
from creality_nfc.cfs_layout import cfs_slot_label, parse_cfs_layout
from creality_nfc.cfs_spool_link import find_spool_for_slot
from creality_nfc.filament_alerts import find_low_filament_spools
from creality_nfc.print_history import PrintHistoryStore
from creality_nfc.spool_usage import is_low_filament
from ui.dialog_theme import prepare_toplevel, theme_dialog
from ui.messaging import notify

if TYPE_CHECKING:
    from creality_nfc.spool_inventory import SpoolInventory


def show_print_history_dialog(
    parent: tk.Misc,
    store: PrintHistoryStore,
    *,
    threshold_g: int = 200,
) -> None:
    dlg = tk.Toplevel(parent)
    dlg.title("Druck-Historie")
    prepare_toplevel(
        dlg,
        parent,
        width=720,
        height=420,
        geometry_key="print_history",
        min_width=520,
        min_height=300,
    )

    top = ttk.Frame(dlg, padding=8)
    top.pack(fill="x")
    ttk.Label(top, text="Abgeschlossene Drucke (lokal gespeichert)", style="Muted.TLabel").pack(
        side="left"
    )

    def _export_csv() -> None:
        path = filedialog.asksaveasfilename(
            parent=dlg,
            title="Historie als CSV",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="druck_historie.csv",
        )
        if not path:
            return
        try:
            store.export_csv(path)
            notify(dlg, f"Exportiert:\n{path}", "ok")
        except OSError as exc:
            notify(dlg, str(exc), "error")

    ttk.Button(top, text="CSV exportieren…", command=_export_csv).pack(side="right")

    cols = ("ts", "file", "deducted", "slot", "spool", "note")
    tree = ttk.Treeview(dlg, columns=cols, show="headings", height=14)
    tree.heading("ts", text="Zeit")
    tree.heading("file", text="Datei")
    tree.heading("deducted", text="Abgezogen")
    tree.heading("slot", text="Slot")
    tree.heading("spool", text="Spule")
    tree.heading("note", text="Notiz")
    tree.column("ts", width=140)
    tree.column("file", width=180)
    tree.column("deducted", width=70)
    tree.column("slot", width=50)
    tree.column("spool", width=120)
    tree.column("note", width=140)
    sy = ttk.Scrollbar(dlg, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sy.set)
    tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
    sy.pack(side="right", fill="y", pady=8, padx=(0, 8))

    entries = store.list_entries()
    if not entries:
        ttk.Label(
            dlg,
            text=(
                "Noch keine Einträge.\n\n"
                "Die Historie füllt sich, wenn ein Druck auf dem K2 endet und der "
                "Tab Drucker verbunden ist — auch wenn du den Filament-Dialog "
                "überspringst.\n\n"
                "Einstellungen: „Nach Druckende: Verbrauch abfragen“ kann aus sein; "
                "der Eintrag wird trotzdem gespeichert."
            ),
            style="Muted.TLabel",
            wraplength=520,
            justify="left",
        ).pack(anchor="w", padx=12, pady=(0, 6))

    for e in entries:
        ded = f"{e.deducted_g} g" if e.deducted_g is not None else "—"
        tree.insert(
            "",
            tk.END,
            values=(
                e.ts.replace("T", " ")[:19],
                e.filename,
                ded,
                e.cfs_slot_label or "—",
                e.spool_label or "—",
                e.note,
            ),
        )

    ttk.Button(dlg, text="Schließen", command=dlg.destroy).pack(pady=8)


def show_cfs_batch_dialog(
    parent: tk.Misc,
    state: dict[str, Any],
    inventory: SpoolInventory,
    *,
    threshold_g: int = 200,
    slots: list[CfsSlotInfo] | None = None,
    meta: CfsMeta | None = None,
) -> None:
    dlg = tk.Toplevel(parent)
    dlg.title("CFS — alle Slots")
    prepare_toplevel(
        dlg,
        parent,
        width=920,
        height=380,
        geometry_key="cfs_all_slots",
        min_width=760,
        min_height=300,
    )

    ttk.Label(
        dlg,
        text="Live vom Drucker (WebSocket). RFID-Chips am PC: Tab RFID-Tag.",
        style="Muted.TLabel",
        wraplength=860,
    ).pack(anchor="w", padx=12, pady=(10, 6))

    tree_wrap = ttk.Frame(dlg)
    tree_wrap.pack(fill="both", expand=True, padx=12, pady=4)
    tree_wrap.grid_rowconfigure(0, weight=1)
    tree_wrap.grid_columnconfigure(0, weight=1)

    cols = ("cfs", "slot", "mat", "color", "rfid", "spool", "rest", "status")
    tree = ttk.Treeview(tree_wrap, columns=cols, show="headings", height=8)
    for c, t, w, stretch in (
        ("cfs", "CFS", 40, False),
        ("slot", "Slot", 44, False),
        ("mat", "Material", 72, False),
        ("color", "Farbe", 76, False),
        ("rfid", "RFID", 88, False),
        ("spool", "Meine Spule", 240, True),
        ("rest", "Rest", 72, False),
        ("status", "Status", 110, False),
    ):
        tree.heading(c, text=t)
        tree.column(c, width=w, minwidth=w // 2, stretch=stretch)
    sy = ttk.Scrollbar(tree_wrap, orient="vertical", command=tree.yview)
    sx = ttk.Scrollbar(tree_wrap, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
    tree.grid(row=0, column=0, sticky="nsew")
    sy.grid(row=0, column=1, sticky="ns")
    sx.grid(row=1, column=0, sticky="ew")

    cfs_meta = meta if meta is not None else parse_cfs_meta(state)
    layout = parse_cfs_layout(state)
    slot_list = slots if slots is not None else layout.all_slots()
    if slots and len(slots) <= 4:
        slot_list = layout.all_slots() if layout.box_count() > 1 else list(slots)
    has_box = bool(_find_boxs_info_key(state))
    rows = slot_list if layout.box_count() > 0 else []
    if not rows:
        for i in range(4):
            rows.append(
                CfsSlotInfo(
                    index=i,
                    label=cfs_slot_label(1, i),
                    vendor="",
                    name="",
                    material_type="",
                    color_raw="",
                    color_hex="FFFFFF",
                    percent=None,
                    rfid_id="",
                    empty=True,
                    box_id=1,
                )
            )
    for info in rows:
        bid = getattr(info, "box_id", 1) or 1
        lab = cfs_slot_label(bid, info.index)
        if info.empty:
            hint = "keine CFS-Daten" if not has_box else "leer"
            tree.insert(
                "",
                tk.END,
                values=(str(bid), lab, "—", "—", "—", "—", "—", hint),
            )
            continue
        mat = info.material_type or info.name or "—"
        col = f"#{info.color_hex}" if info.color_hex else "—"
        rfid = (info.rfid_id or "—")[:16]
        sp = find_spool_for_slot(inventory, info)
        if sp is None:
            sp = inventory.find_by_cfs_slot(info.index)
        sp_label = sp.label if sp else "—"
        rest = f"{sp.remaining_g} g" if sp and sp.remaining_g is not None else "—"
        in_use = (
            cfs_meta.loaded_index == info.index
            or cfs_meta.feeding_index == info.index
        ) and layout.box_count() <= 1
        status = "im Einsatz" if in_use else "bereit"
        if sp and is_low_filament(sp, threshold_g):
            status = f"niedrig (<{threshold_g}g)"
        tree.insert(
            "",
            tk.END,
            values=(str(bid), lab, mat, col, rfid, sp_label, rest, status),
        )

    low = find_low_filament_spools(inventory, threshold_g)
    if low:
        msg = "Niedriger Rest: " + ", ".join(s.label for s, _ in low[:4])
        ttk.Label(dlg, text=msg, foreground="#c9a227").pack(anchor="w", padx=12, pady=4)

    if not has_box and all(s.empty for s in slot_list):
        ttk.Label(
            dlg,
            text="Tipp: Tab Filament muss CFS-Daten zeigen — dann ↻ oder neu verbinden.",
            style="Muted.TLabel",
            wraplength=560,
        ).pack(anchor="w", padx=12, pady=4)

    ttk.Button(dlg, text="Schließen", command=dlg.destroy).pack(pady=10)


def _find_boxs_info_key(state: dict[str, Any]) -> bool:
    for key in ("boxsInfo", "boxsinfo", "BoxsInfo", "retBoxsInfo"):
        if key in state and state[key]:
            return True
    return False
