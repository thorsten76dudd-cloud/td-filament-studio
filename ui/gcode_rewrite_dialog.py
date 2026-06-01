"""Dialog: Creality-G-Code an lokale Spulen (RFID-IDs) anpassen."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from creality_nfc.cfs_layout import cfs_slot_label
from creality_nfc.gcode_rewrite import (
    GcodeRewritePlan,
    apply_rewrite_plan,
    build_spool_mappings,
    default_output_path,
    parse_gcode_for_rewrite,
)
from creality_nfc.i18n import t as _t
from creality_nfc.spool_inventory import Spool, SpoolInventory
from ui.dialog_theme import dialog_root, prepare_toplevel, theme_dialog
from ui.rounded_widgets import rounded_button


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


def _spool_summary(spool: Spool | None) -> str:
    if spool is None:
        return "—"
    slot = ""
    if spool.cfs_slot is not None:
        slot = cfs_slot_label(spool.cfs_box_id or 1, spool.cfs_slot) + " · "
    return f"{slot}{spool.filament_id} · {spool.material_name or spool.label}"


class GcodeRewriteDialog:
    def __init__(
        self,
        parent: tk.Misc,
        inventory: SpoolInventory,
        *,
        initial_path: Path | None = None,
        on_saved: Callable[[Path], None] | None = None,
    ) -> None:
        self._inventory = inventory
        self._on_saved = on_saved
        self._plan: GcodeRewritePlan | None = None
        self._path_var = tk.StringVar(value=str(initial_path) if initial_path else "")

        root = dialog_root(parent)
        self._dlg = tk.Toplevel(root)
        self._dlg.title(_t("gcode_rw.title"))
        prepare_toplevel(self._dlg, root, width=820, height=520, geometry_key="gcode_rewrite")
        theme_dialog(self._dlg)
        self._dlg.transient(root)

        body = ttk.Frame(self._dlg, padding=12)
        body.pack(fill="both", expand=True)

        ttk.Label(
            body,
            text=_t("gcode_rw.intro"),
            style="Muted.TLabel",
            wraplength=780,
        ).pack(anchor="w", pady=(0, 10))

        row = ttk.Frame(body)
        row.pack(fill="x", pady=(0, 8))
        ttk.Label(row, text=_t("gcode_rw.field.file"), width=12, anchor="w").pack(side="left")
        ttk.Entry(row, textvariable=self._path_var).pack(side="left", fill="x", expand=True, padx=4)
        rounded_button(row, text=_t("gcode_rw.btn.browse"), command=self._browse).pack(side="left")
        rounded_button(row, text=_t("gcode_rw.btn.analyze"), command=self._analyze).pack(
            side="left", padx=(6, 0)
        )

        self._summary = ttk.Label(body, text="", style="Muted.TLabel", wraplength=780)
        self._summary.pack(anchor="w", pady=(0, 6))

        cols = (
            "ch",
            "gcolor",
            "gid",
            "gprof",
            "grams",
            "spool",
            "newid",
        )
        tree_frame = ttk.Frame(body)
        tree_frame.pack(fill="both", expand=True)
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=10)
        headings = {
            "ch": _t("gcode_rw.col.channel"),
            "gcolor": _t("gcode_rw.col.gcode_color"),
            "gid": _t("gcode_rw.col.gcode_id"),
            "gprof": _t("gcode_rw.col.gcode_profile"),
            "grams": _t("gcode_rw.col.grams"),
            "spool": _t("gcode_rw.col.spool"),
            "newid": _t("gcode_rw.col.new_id"),
        }
        for c in cols:
            self._tree.heading(c, text=headings[c])
            self._tree.column(c, width=100 if c != "gprof" else 180, stretch=True)
        self._tree.column("spool", width=200)
        scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=scroll.set)
        self._tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        btn_row = ttk.Frame(body)
        btn_row.pack(fill="x", pady=(10, 0))
        rounded_button(btn_row, text=_t("gcode_rw.btn.save_as"), command=self._save_as).pack(
            side="right"
        )
        rounded_button(btn_row, text=_t("gcode_rw.cancel"), command=self._dlg.destroy).pack(
            side="right", padx=(0, 8)
        )

        if initial_path and initial_path.is_file():
            self._dlg.after(100, self._analyze)

        _raise_dialog(self._dlg)

    def _browse(self) -> None:
        path = filedialog.askopenfilename(
            parent=self._dlg,
            title=_t("gcode_rw.pick_file"),
            filetypes=[("G-Code", "*.gcode"), (_t("gcode_rw.all_files"), "*.*")],
        )
        if path:
            self._path_var.set(path)

    def _analyze(self) -> None:
        raw = self._path_var.get().strip()
        if not raw:
            messagebox.showwarning(
                _t("gcode_rw.title"), _t("gcode_rw.err.no_file"), parent=self._dlg
            )
            return
        try:
            plan = parse_gcode_for_rewrite(Path(raw))
            spools = list(self._inventory.spools)
            if not spools:
                messagebox.showwarning(
                    _t("gcode_rw.title"),
                    _t("gcode_rw.err.no_spools"),
                    parent=self._dlg,
                )
                return
            plan = build_spool_mappings(plan, spools, only_active=False)
            self._plan = plan
        except OSError as e:
            messagebox.showerror(
                _t("gcode_rw.title"), str(e), parent=self._dlg
            )
            return

        for item in self._tree.get_children():
            self._tree.delete(item)

        tool = plan.initial_tool
        parts = [Path(raw).name]
        if tool is not None:
            parts.append(_t("gcode_rw.summary.tool", tool=tool))
        warn_n = sum(len(m.warnings) for m in plan.mappings) + len(plan.warnings)
        if warn_n:
            parts.append(_t("gcode_rw.summary.warnings", n=warn_n))
        self._summary.configure(text=" · ".join(parts))

        for m in plan.mappings:
            ch = plan.channels[m.channel] if m.channel < len(plan.channels) else None
            color = (ch.color_hex if ch else m.gcode_color) or "—"
            self._tree.insert(
                "",
                "end",
                values=(
                    f"T{m.channel}",
                    color,
                    m.gcode_id or "—",
                    (m.gcode_profile or "—")[:40],
                    f"{m.weight_g:.1f}" if m.weight_g > 0.01 else "—",
                    _spool_summary(m.spool),
                    m.new_id or "—",
                ),
            )

    def _save_as(self) -> None:
        if not self._plan or not self._plan.mappings:
            messagebox.showwarning(
                _t("gcode_rw.title"), _t("gcode_rw.err.analyze_first"), parent=self._dlg
            )
            return
        src = self._plan.source_path
        dest = filedialog.asksaveasfilename(
            parent=self._dlg,
            title=_t("gcode_rw.save_title"),
            initialfile=default_output_path(src).name,
            defaultextension=".gcode",
            filetypes=[("G-Code", "*.gcode")],
        )
        if not dest:
            return
        try:
            out = apply_rewrite_plan(self._plan, Path(dest))
        except (OSError, ValueError) as e:
            messagebox.showerror(_t("gcode_rw.title"), str(e), parent=self._dlg)
            return
        messagebox.showinfo(
            _t("gcode_rw.title"),
            _t("gcode_rw.done", path=str(out)),
            parent=self._dlg,
        )
        if self._on_saved:
            self._on_saved(out)
        self._dlg.destroy()


def open_gcode_rewrite_dialog(
    parent: tk.Misc,
    inventory: SpoolInventory,
    *,
    initial_path: Path | None = None,
) -> None:
    GcodeRewriteDialog(parent, inventory, initial_path=initial_path)
