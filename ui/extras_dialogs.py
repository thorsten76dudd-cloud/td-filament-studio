"""Zusatz-Dialoge: Druck-Historie, CFS-Batch-Übersicht."""

from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import filedialog, ttk
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from creality_nfc.cfs_adopt import CfsMeta, CfsSlotInfo, parse_cfs_meta, parse_cfs_slots
from creality_nfc.cfs_layout import cfs_slot_label, parse_cfs_layout
from creality_nfc.cfs_spool_link import find_spool_for_slot
from creality_nfc.filament_alerts import find_low_filament_spools
from creality_nfc.print_history import (
    PrintHistoryStore,
    PrintJobRecord,
    normalize_history_note,
)
from creality_nfc.spool_usage import is_low_filament
from ui.dialog_theme import begin_table_dialog, pack_dialog_shell, prepare_toplevel, show_table_dialog
from ui.messaging import notify
from ui.rounded_widgets import rounded_button
from ui.theme import BG

if TYPE_CHECKING:
    from creality_nfc.spool_inventory import SpoolInventory


def _gcode_basename(path: str) -> str:
    return (path or "").replace("\\", "/").rsplit("/", 1)[-1] or path


def show_print_history_dialog(
    parent: tk.Misc,
    store: PrintHistoryStore,
    *,
    threshold_g: int = 200,
    on_retro_deduct: Callable[[PrintJobRecord], None] | None = None,
) -> None:
    _ = threshold_g  # reserviert für spätere Spalten-Hinweise
    store.load()
    dlg, body, footer = begin_table_dialog(
        parent,
        title=f"Druck-Historie ({len(store.list_entries())})",
        width=1020,
        height=540,
        min_width=860,
        min_height=420,
    )

    foot_inner = tk.Frame(footer, bg=BG)
    foot_inner.pack(fill="x")

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

    _empty_labels: list[ttk.Label] = []

    def _fill_tree() -> None:
        for item in tree.get_children():
            tree.delete(item)
        for lbl in _empty_labels:
            lbl.destroy()
        _empty_labels.clear()
        entries = store.list_entries()
        if not entries:
            empty = ttk.Label(
                body,
                text=(
                    "Noch keine Einträge.\n\n"
                    "Die Historie füllt sich, wenn ein Druck auf dem K2 endet und der "
                    "Tab Drucker verbunden ist — auch wenn du den Filament-Dialog "
                    "überspringst.\n\n"
                    "Einstellungen: „Nach Druckende: Verbrauch abfragen“ kann aus sein; "
                    "der Eintrag wird trotzdem gespeichert."
                ),
                style="Muted.TLabel",
                wraplength=760,
                justify="left",
            )
            empty.pack(anchor="w", padx=12, pady=(0, 6))
            _empty_labels.append(empty)
            return
        for e in entries:
            if e.deducted_g is not None and e.deducted_g > 0:
                ded = f"{e.deducted_g} g"
            elif e.estimated_total_g is not None and e.estimated_total_g > 0:
                ded = f"~{e.estimated_total_g} g"
            else:
                ded = "—"
            short = _gcode_basename(e.filename)
            note = normalize_history_note(e)
            iid = PrintHistoryStore.tree_iid(e)
            tree.insert(
                "",
                tk.END,
                iid=iid,
                values=(
                    e.ts.replace("T", " ")[:19],
                    short,
                    ded,
                    e.cfs_slot_label or "—",
                    e.spool_label or "—",
                    note,
                ),
            )

    def _retro_deduct() -> None:
        if not on_retro_deduct:
            return
        sel = tree.selection()
        if not sel:
            notify(dlg, "Bitte zuerst einen Druck in der Liste wählen.", "warn")
            return
        entry = store.get(sel[0])
        if entry is None:
            notify(dlg, "Eintrag nicht gefunden.", "warn")
            return
        on_retro_deduct(entry)
        store.load()
        _fill_tree()
        keep = PrintHistoryStore.tree_iid(entry)
        if tree.exists(keep):
            tree.selection_set(keep)
            tree.see(keep)
        elif tree.get_children():
            tree.selection_set(tree.get_children()[0])

    rounded_button(
        foot_inner, "CSV exportieren…", _export_csv, variant="secondary", compact=True
    ).pack(side="left")
    if on_retro_deduct:
        tip_retro = (
            "Verbrauch für den gewählten Druck nachträglich von der Spule abziehen "
            "(gleicher Dialog wie nach Druckende)."
        )
        rounded_button(
            foot_inner,
            "Verbrauch nachträglich…",
            _retro_deduct,
            variant="secondary",
            compact=True,
        ).pack(side="left", padx=(8, 0))
    rounded_button(foot_inner, "Schließen", dlg.destroy, variant="accent", compact=True).pack(
        side="right"
    )

    top = ttk.Frame(body, padding=10)
    top.pack(fill="x")
    hint = "Abgeschlossene Drucke (lokal gespeichert)"
    if on_retro_deduct:
        hint += " — Zeile wählen → „Verbrauch nachträglich…“"
    ttk.Label(top, text=hint, style="Muted.TLabel").pack(anchor="w")

    tree_wrap = ttk.Frame(body)
    tree_wrap.pack(fill="both", expand=True, padx=10, pady=(4, 8))
    tree_wrap.grid_rowconfigure(0, weight=1)
    tree_wrap.grid_columnconfigure(0, weight=1)

    cols = ("ts", "file", "deducted", "slot", "spool", "note")
    tree = ttk.Treeview(tree_wrap, columns=cols, show="headings", height=18)
    tree.heading("ts", text="Zeit")
    tree.heading("file", text="Datei")
    tree.heading("deducted", text="Abgezogen")
    tree.heading("slot", text="Slot")
    tree.heading("spool", text="Spule")
    tree.heading("note", text="Notiz")
    tree.column("ts", width=158, minwidth=140, stretch=False)
    tree.column("file", width=280, minwidth=180, stretch=True)
    tree.column("deducted", width=100, minwidth=96, stretch=False)
    tree.column("slot", width=64, minwidth=56, stretch=False)
    tree.column("spool", width=200, minwidth=140, stretch=True)
    tree.column("note", width=280, minwidth=160, stretch=True)
    sy = ttk.Scrollbar(tree_wrap, orient="vertical", command=tree.yview)
    sx = ttk.Scrollbar(tree_wrap, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
    tree.grid(row=0, column=0, sticky="nsew")
    sy.grid(row=0, column=1, sticky="ns")
    sx.grid(row=1, column=0, sticky="ew")

    _fill_tree()

    show_table_dialog(dlg)


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
    dlg.configure(bg=BG)
    prepare_toplevel(
        dlg,
        parent,
        width=920,
        height=440,
        geometry_key="cfs_all_slots",
        min_width=760,
        min_height=340,
        modal=False,
    )

    foot = tk.Frame(dlg, bg=BG)
    foot_inner = tk.Frame(foot, bg=BG)
    foot_inner.pack(fill="x", padx=14, pady=12)
    rounded_button(foot_inner, "Schließen", dlg.destroy, variant="accent", compact=True).pack(
        side="right"
    )

    body = pack_dialog_shell(dlg, footer=foot)

    ttk.Label(
        body,
        text="Live vom Drucker (WebSocket). RFID-Chips am PC: Tab RFID-Tag.",
        style="Muted.TLabel",
        wraplength=860,
    ).pack(anchor="w", padx=12, pady=(10, 6))

    tree_wrap = ttk.Frame(body)
    tree_wrap.pack(fill="both", expand=True, padx=12, pady=4)
    tree_wrap.grid_rowconfigure(0, weight=1)
    tree_wrap.grid_columnconfigure(0, weight=1)

    cols = ("cfs", "slot", "mat", "color", "rfid", "spool", "rest", "status")
    tree = ttk.Treeview(tree_wrap, columns=cols, show="headings", height=8)
    for c, t, w, stretch in (
        ("cfs", "CFS", 48, False),
        ("slot", "Slot", 52, False),
        ("mat", "Material", 88, False),
        ("color", "Farbe", 88, False),
        ("rfid", "RFID", 100, False),
        ("spool", "Meine Spule", 260, True),
        ("rest", "Rest", 80, False),
        ("status", "Status", 130, True),
    ):
        tree.heading(c, text=t)
        tree.column(c, width=w, minwidth=max(44, w // 2), stretch=stretch)
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
        ttk.Label(body, text=msg, foreground="#c9a227").pack(anchor="w", padx=12, pady=4)

    if not has_box and all(s.empty for s in slot_list):
        ttk.Label(
            body,
            text="Tipp: Tab Filament muss CFS-Daten zeigen — dann ↻ oder neu verbinden.",
            style="Muted.TLabel",
            wraplength=560,
        ).pack(anchor="w", padx=12, pady=4)

    finalize_dialog_size(dlg, width=920, height=440, min_width=760, min_height=340)


def _find_boxs_info_key(state: dict[str, Any]) -> bool:
    for key in ("boxsInfo", "boxsinfo", "BoxsInfo", "retBoxsInfo"):
        if key in state and state[key]:
            return True
    return False
