"""Dialog: Filament-Profil aus der Material-Datenbank waehlen."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from creality_nfc.i18n import t as _t
from creality_nfc.materials import FilamentProfile
from ui.dialog_theme import prepare_toplevel, theme_dialog
from ui.tooltip import tip


def ask_filament_profile(
    parent: tk.Misc,
    profiles: list[FilamentProfile],
    *,
    title: str = "Profil aus Material-DB",
) -> FilamentProfile | None:
    """Modaler Dialog — gibt gewähltes Profil oder None zurück."""
    if not profiles:
        return None

    result: list[FilamentProfile | None] = [None]
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    prepare_toplevel(dlg, parent, width=620, height=480, geometry_key="profile_pick")
    theme_dialog(dlg)
    dlg.transient(parent.winfo_toplevel())
    dlg.grab_set()

    ttk.Label(
        dlg,
        text=_t("profile_pick.intro"),
        style="Muted.TLabel",
        wraplength=560,
    ).pack(anchor="w", padx=12, pady=(12, 6))

    search_var = tk.StringVar()
    search_row = ttk.Frame(dlg)
    search_row.pack(fill="x", padx=12, pady=(0, 6))
    ttk.Label(search_row, text=_t("profile_pick.search")).pack(side="left", padx=(0, 6))
    search_entry = ttk.Entry(search_row, textvariable=search_var)
    search_entry.pack(side="left", fill="x", expand=True)

    tree_wrap = ttk.Frame(dlg)
    tree_wrap.pack(fill="both", expand=True, padx=12, pady=4)
    sy = ttk.Scrollbar(tree_wrap, orient="vertical")
    tree = ttk.Treeview(
        tree_wrap,
        columns=("id", "brand", "name", "type"),
        show="headings",
        height=14,
        yscrollcommand=sy.set,
    )
    sy.config(command=tree.yview)
    for col, title_txt, w in (
        ("id", "ID", 72),
        ("brand", "Marke", 120),
        ("name", "Material", 240),
        ("type", "Typ", 80),
    ):
        tree.heading(col, text=title_txt)
        tree.column(col, width=w, minwidth=40)
    tree.grid(row=0, column=0, sticky="nsew")
    sy.grid(row=0, column=1, sticky="ns")
    tree_wrap.rowconfigure(0, weight=1)
    tree_wrap.columnconfigure(0, weight=1)

    rows: list[tuple[str, FilamentProfile]] = []

    def refill() -> None:
        tree.delete(*tree.get_children())
        rows.clear()
        q = search_var.get().strip().lower()
        for p in profiles:
            hay = f"{p.filament_id} {p.brand} {p.name} {p.material_type}".lower()
            if q and q not in hay:
                continue
            iid = f"{p.filament_id}|{p.brand}|{p.name}"
            rows.append((iid, p))
            tree.insert(
                "",
                "end",
                iid=iid,
                values=(p.filament_id, p.brand, p.name, p.material_type),
            )

    def pick_selected() -> None:
        sel = tree.selection()
        if not sel:
            return
        iid = sel[0]
        for rid, prof in rows:
            if rid == iid:
                result[0] = prof
                dlg.destroy()
                return

    search_var.trace_add("write", lambda *_: refill())
    tree.bind("<Double-1>", lambda _e: pick_selected())
    refill()
    kids = tree.get_children()
    if kids:
        tree.selection_set(kids[0])
        tree.focus(kids[0])

    btn_row = ttk.Frame(dlg)
    btn_row.pack(fill="x", padx=12, pady=12)
    tip(
        ttk.Button(btn_row, text=_t("profile_pick.cancel"), command=dlg.destroy, style="Secondary.TButton"),
        _t("profile_pick.cancel.tip"),
    ).pack(side="left")
    tip(
        ttk.Button(btn_row, text=_t("profile_pick.adopt"), command=pick_selected, style="Accent.TButton"),
        _t("profile_pick.adopt.tip"),
    ).pack(side="right")

    dlg.protocol("WM_DELETE_WINDOW", dlg.destroy)
    search_entry.focus_set()
    parent.wait_window(dlg)
    return result[0]
