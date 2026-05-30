"""Dialog: Material-ID eines Profils ändern und optional auf den K2 schreiben."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, ttk

from creality_nfc.i18n import t as _t
from creality_nfc.materials import FilamentProfile
from ui.dialog_theme import dialog_root, prepare_toplevel, theme_dialog
from ui.rounded_widgets import rounded_button


def _profile_label(p: FilamentProfile) -> str:
    return f"{p.brand} — {p.name}  ·  ID {p.filament_id}"


def _raise_dialog(dlg: tk.Toplevel) -> None:
    dlg.update_idletasks()
    try:
        dlg.deiconify()
        dlg.lift()
        dlg.attributes("-topmost", True)
        dlg.after(120, lambda: dlg.attributes("-topmost", False))
        dlg.focus_force()
    except tk.TclError:
        pass


def ask_change_filament_id(
    parent: tk.Misc,
    profiles: list[FilamentProfile],
    *,
    initial: FilamentProfile | None = None,
    default_push_to_printer: bool = True,
    on_apply: Callable[[FilamentProfile, str, bool], None],
) -> None:
    """Profil in der Liste wählen, neue ID eingeben; on_apply(profile, new_id, push)."""
    if not profiles:
        messagebox.showwarning(
            _t("id_change.title"),
            _t("id_change.err.no_profiles"),
            parent=dialog_root(parent),
        )
        return

    root = dialog_root(parent)
    dlg = tk.Toplevel(root)
    dlg.title(_t("id_change.title"))
    prepare_toplevel(dlg, root, width=560, height=420, geometry_key="change_filament_id")
    theme_dialog(dlg)
    dlg.transient(root)

    by_label = {_profile_label(p): p for p in profiles}
    labels = sorted(by_label.keys(), key=str.lower)
    start = initial if initial else profiles[0]
    start_label = _profile_label(start) if _profile_label(start) in by_label else labels[0]

    body = ttk.Frame(dlg, padding=12)
    body.pack(fill="both", expand=True)

    ttk.Label(
        body,
        text=_t("id_change.intro_pick"),
        style="Muted.TLabel",
        wraplength=500,
    ).pack(anchor="w", pady=(0, 10))

    pick_row = ttk.Frame(body)
    pick_row.pack(fill="x", pady=(0, 8))
    ttk.Label(pick_row, text=_t("id_change.field.profile"), width=14, anchor="w").pack(side="left")
    pick_var = tk.StringVar(value=start_label)
    pick_combo = ttk.Combobox(
        pick_row,
        textvariable=pick_var,
        values=labels,
        state="readonly",
        width=48,
    )
    pick_combo.pack(side="left", fill="x", expand=True)

    detail = ttk.Label(body, text="", style="Muted.TLabel", wraplength=500)
    detail.pack(anchor="w", pady=(0, 8))

    grid = ttk.Frame(body)
    grid.pack(fill="x", pady=(0, 8))

    ttk.Label(grid, text=_t("id_change.field.new_id"), width=14, anchor="w").grid(
        row=0, column=0, sticky="w", pady=(4, 3)
    )
    new_var = tk.StringVar()
    entry = ttk.Entry(grid, textvariable=new_var, width=14, font=("Consolas", 12))
    entry.grid(row=0, column=1, sticky="w", pady=(4, 3))

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
        wraplength=500,
    ).pack(anchor="w", pady=(4, 0))

    def current_profile() -> FilamentProfile:
        return by_label[pick_var.get()]

    def refresh_fields(*_args: object) -> None:
        p = current_profile()
        new_var.set(p.filament_id)
        detail.config(text=_t("id_change.detail", brand=p.brand, name=p.name, typ=p.material_type))
        entry.select_range(0, tk.END)
        entry.focus_set()

    pick_combo.bind("<<ComboboxSelected>>", refresh_fields)
    refresh_fields()

    btn_row = ttk.Frame(dlg, padding=(12, 0, 12, 12))
    btn_row.pack(fill="x")

    def cancel() -> None:
        dlg.destroy()

    def apply() -> None:
        new_id = new_var.get().strip()
        if not new_id:
            messagebox.showwarning(_t("id_change.title"), _t("id_change.err.empty"), parent=dlg)
            return
        prof = current_profile()
        dlg.destroy()
        on_apply(prof, new_id, push_var.get())

    rounded_button(btn_row, _t("id_change.apply"), apply, variant="accent").pack(side="right", padx=(6, 0))
    rounded_button(btn_row, _t("id_change.cancel"), cancel, variant="secondary").pack(side="right")

    dlg.bind("<Return>", lambda _e: apply())
    dlg.bind("<Escape>", lambda _e: cancel())
    dlg.protocol("WM_DELETE_WINDOW", cancel)
    _raise_dialog(dlg)
    root.wait_window(dlg)
