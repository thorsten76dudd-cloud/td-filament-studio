"""Zusatz-Dialoge: Druck-Historie, CFS-Batch-Übersicht."""

from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import filedialog, ttk
from typing import TYPE_CHECKING, Any

from creality_nfc.cfs_adopt import SLOT_LABELS, parse_cfs_slots
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
    prepare_toplevel(dlg, parent)
    theme_dialog(dlg)
    dlg.geometry("720x420")
    dlg.minsize(520, 300)

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

    for e in store.list_entries():
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
) -> None:
    dlg = tk.Toplevel(parent)
    dlg.title("CFS — alle Slots")
    prepare_toplevel(dlg, parent)
    theme_dialog(dlg)
    dlg.geometry("640x360")
    dlg.minsize(480, 280)

    ttk.Label(
        dlg,
        text="Live vom Drucker (WebSocket). RFID-Chips am PC: Tab RFID-Tag.",
        style="Muted.TLabel",
        wraplength=580,
    ).pack(anchor="w", padx=12, pady=(10, 6))

    cols = ("slot", "mat", "color", "rfid", "spool", "rest", "status")
    tree = ttk.Treeview(dlg, columns=cols, show="headings", height=6)
    for c, t, w in (
        ("slot", "Slot", 44),
        ("mat", "Material", 100),
        ("color", "Farbe", 70),
        ("rfid", "RFID (Drucker)", 100),
        ("spool", "Meine Spule", 120),
        ("rest", "Rest", 60),
        ("status", "Status", 140),
    ):
        tree.heading(c, text=t)
        tree.column(c, width=w)
    tree.pack(fill="both", expand=True, padx=12, pady=4)

    slots = parse_cfs_slots(state)
    by_idx = {s.index: s for s in slots}
    for i in range(4):
        info = by_idx.get(i)
        lab = SLOT_LABELS[i]
        if not info:
            tree.insert("", tk.END, values=(lab, "—", "—", "—", "—", "—", "leer / offline"))
            continue
        mat = info.material_type or "—"
        col = info.color_hex or "—"
        rfid = (info.rfid_id or "—")[:12]
        sp = find_spool_for_slot(inventory, i)
        sp_label = sp.label if sp else "—"
        rest = f"{sp.remaining_g} g" if sp and sp.remaining_g is not None else "—"
        status = "im Einsatz" if info.loaded else "bereit"
        if sp and is_low_filament(sp, threshold_g):
            status = f"niedrig (<{threshold_g}g)"
        tree.insert(
            "",
            tk.END,
            values=(lab, mat, col, rfid, sp_label, rest, status),
        )

    low = find_low_filament_spools(inventory, threshold_g)
    if low:
        msg = "Niedriger Rest: " + ", ".join(s.label for s, _ in low[:4])
        ttk.Label(dlg, text=msg, foreground="#c9a227").pack(anchor="w", padx=12, pady=4)

    ttk.Button(dlg, text="Schließen", command=dlg.destroy).pack(pady=10)
