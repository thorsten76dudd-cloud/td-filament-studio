"""Dialog: Material-ID eines Profils ändern und optional auf den K2 schreiben."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, ttk

from creality_nfc.i18n import t as _t
from creality_nfc.materials import FilamentProfile
from ui.dialog_theme import prepare_toplevel, theme_dialog
from ui.rounded_widgets import rounded_button


def ask_change_filament_id(
    parent: tk.Misc,
    profile: FilamentProfile,
    *,
    default_push_to_printer: bool = True,
    on_apply: Callable[[str, bool], None],
) -> None:
    """Modal: neue ID eingeben; on_apply(new_id, push_to_printer) bei Bestätigen."""
    dlg = tk.Toplevel(parent)
    dlg.title(_t("id_change.title"))
    prepare_toplevel(dlg, parent, width=520, height=340, geometry_key="change_filament_id")
    theme_dialog(dlg)
    dlg.transient(parent.winfo_toplevel())
    dlg.grab_set()

    body = ttk.Frame(dlg, padding=12)
    body.pack(fill="both", expand=True)

    ttk.Label(
        body,
        text=_t("id_change.intro"),
        style="Muted.TLabel",
        wraplength=480,
    ).pack(anchor="w", pady=(0, 10))

    grid = ttk.Frame(body)
    grid.pack(fill="x", pady=(0, 8))
    for row, (label, value) in enumerate(
        (
            (_t("id_change.field.brand"), profile.brand),
            (_t("id_change.field.name"), profile.name),
            (_t("id_change.field.old_id"), profile.filament_id),
        )
    ):
        ttk.Label(grid, text=label, width=14, anchor="w").grid(row=row, column=0, sticky="w", pady=3)
        ttk.Label(grid, text=value, anchor="w").grid(row=row, column=1, sticky="w", pady=3)

    ttk.Label(grid, text=_t("id_change.field.new_id"), width=14, anchor="w").grid(
        row=3, column=0, sticky="w", pady=(8, 3)
    )
    new_var = tk.StringVar(value=profile.filament_id)
    entry = ttk.Entry(grid, textvariable=new_var, width=12)
    entry.grid(row=3, column=1, sticky="w", pady=(8, 3))
    entry.select_range(0, tk.END)
    entry.focus_set()

    push_var = tk.BooleanVar(value=default_push_to_printer)
    ttk.Checkbutton(
        body,
        text=_t("id_change.push_printer"),
        variable=push_var,
    ).pack(anchor="w", pady=(6, 4))

    ttk.Label(
        body,
        text=_t("id_change.warn"),
        style="Muted.TLabel",
        wraplength=480,
    ).pack(anchor="w", pady=(4, 0))

    btn_row = ttk.Frame(dlg, padding=(12, 0, 12, 12))
    btn_row.pack(fill="x")

    def cancel() -> None:
        dlg.destroy()

    def apply() -> None:
        new_id = new_var.get().strip()
        if not new_id:
            messagebox.showwarning(_t("id_change.title"), _t("id_change.err.empty"), parent=dlg)
            return
        dlg.destroy()
        on_apply(new_id, push_var.get())

    rounded_button(btn_row, _t("id_change.apply"), apply, variant="accent").pack(side="right", padx=(6, 0))
    rounded_button(btn_row, _t("id_change.cancel"), cancel, variant="secondary").pack(side="right)

    dlg.bind("<Return>", lambda _e: apply())
    dlg.bind("<Escape>", lambda _e: cancel())
