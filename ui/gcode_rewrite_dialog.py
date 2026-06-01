"""Dialog: Creality-G-Code an lokale Spulen (RFID-IDs) anpassen."""

from __future__ import annotations

import tempfile
import threading
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from printer_connect import load_settings

from creality_nfc.cfs_layout import cfs_slot_label
from creality_nfc.gcode_rewrite import (
    GcodeRewritePlan,
    apply_rewrite_plan,
    build_spool_mappings,
    default_output_path,
    parse_gcode_for_rewrite,
)
from creality_nfc.i18n import t as _t
from creality_nfc.printer_ssh import default_password, normalize_host, upload_gcode_to_printer
from creality_nfc.spool_inventory import Spool, SpoolInventory
from ui.dialog_theme import dialog_root, prepare_toplevel, theme_dialog
from ui.messaging import notify
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
        on_uploaded: Callable[[str, Path], None] | None = None,
    ) -> None:
        self._inventory = inventory
        self._on_saved = on_saved
        self._on_uploaded = on_uploaded
        self._plan: GcodeRewritePlan | None = None
        self._last_saved: Path | None = None
        self._path_var = tk.StringVar(value=str(initial_path) if initial_path else "")
        self._upload_status = tk.StringVar(value="")

        root = dialog_root(parent)
        self._dlg = tk.Toplevel(root)
        self._dlg.title(_t("gcode_rw.title"))
        prepare_toplevel(
            self._dlg,
            root,
            width=960,
            height=640,
            geometry_key="gcode_rewrite",
            min_width=760,
            min_height=520,
        )
        theme_dialog(self._dlg)
        self._dlg.transient(root)
        self._dlg.columnconfigure(0, weight=1)
        self._dlg.rowconfigure(0, weight=1)
        self._dlg.rowconfigure(1, weight=0)
        self._dlg.rowconfigure(2, weight=0)
        self._dlg.rowconfigure(3, weight=0)

        body = ttk.Frame(self._dlg, padding=12)
        body.grid(row=0, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(3, weight=1)

        intro = ttk.Label(
            body,
            text=_t("gcode_rw.intro"),
            style="Muted.TLabel",
            wraplength=900,
        )
        intro.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        row = ttk.Frame(body)
        row.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        row.columnconfigure(1, weight=1)
        ttk.Label(row, text=_t("gcode_rw.field.file"), width=12, anchor="w").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Entry(row, textvariable=self._path_var).grid(
            row=0, column=1, sticky="ew", padx=4
        )
        btn_file = ttk.Frame(row)
        btn_file.grid(row=0, column=2, sticky="e")
        rounded_button(btn_file, text=_t("gcode_rw.btn.browse"), command=self._browse).pack(
            side="left"
        )
        rounded_button(
            btn_file, text=_t("gcode_rw.btn.analyze"), command=self._analyze
        ).pack(side="left", padx=(6, 0))

        self._summary = ttk.Label(body, text="", style="Muted.TLabel", wraplength=900)
        self._summary.grid(row=2, column=0, sticky="ew", pady=(0, 6))

        cols = (
            "ch",
            "gcolor",
            "gid",
            "gprof",
            "grams",
            "spool",
            "newid",
        )
        tree_wrap = ttk.Frame(body)
        tree_wrap.grid(row=3, column=0, sticky="nsew")
        tree_wrap.columnconfigure(0, weight=1)
        tree_wrap.rowconfigure(0, weight=1)

        self._tree = ttk.Treeview(tree_wrap, columns=cols, show="headings", height=8)
        headings = {
            "ch": _t("gcode_rw.col.channel"),
            "gcolor": _t("gcode_rw.col.gcode_color"),
            "gid": _t("gcode_rw.col.gcode_id"),
            "gprof": _t("gcode_rw.col.gcode_profile"),
            "grams": _t("gcode_rw.col.grams"),
            "spool": _t("gcode_rw.col.spool"),
            "newid": _t("gcode_rw.col.new_id"),
        }
        widths = {
            "ch": 52,
            "gcolor": 88,
            "gid": 72,
            "gprof": 200,
            "grams": 56,
            "spool": 280,
            "newid": 72,
        }
        for c in cols:
            self._tree.heading(c, text=headings[c])
            stretch = c in ("gprof", "spool")
            self._tree.column(
                c,
                width=widths[c],
                minwidth=widths[c] - 20 if not stretch else widths[c],
                stretch=stretch,
            )
        sy = ttk.Scrollbar(tree_wrap, orient="vertical", command=self._tree.yview)
        sx = ttk.Scrollbar(tree_wrap, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        sy.grid(row=0, column=1, sticky="ns")
        sx.grid(row=1, column=0, sticky="ew")

        self._upload_status_lbl = ttk.Label(
            self._dlg, textvariable=self._upload_status, style="Muted.TLabel", wraplength=900
        )
        self._upload_status_lbl.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 4))

        btn_row = ttk.Frame(self._dlg, padding=(12, 4, 12, 12))
        btn_row.grid(row=3, column=0, sticky="ew")
        rounded_button(
            btn_row, text=_t("gcode_rw.btn.save_upload"), command=self._save_and_upload, variant="accent"
        ).pack(side="right")
        rounded_button(btn_row, text=_t("gcode_rw.btn.save_as"), command=self._save_as).pack(
            side="right", padx=(0, 8)
        )
        rounded_button(btn_row, text=_t("gcode_rw.btn.upload"), command=self._upload).pack(
            side="right", padx=(0, 8)
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
                    m.gcode_profile or "—",
                    f"{m.weight_g:.1f}" if m.weight_g > 0.01 else "—",
                    _spool_summary(m.spool),
                    m.new_id or "—",
                ),
            )

    def _printer_credentials(self) -> tuple[str, str] | None:
        saved = load_settings()
        host = normalize_host(str(saved.get("host") or "").strip())
        if not host:
            messagebox.showwarning(
                _t("gcode_rw.title"),
                _t("gcode_rw.err.no_printer"),
                parent=self._dlg,
            )
            return None
        password = str(saved.get("password") or "").strip() or default_password()
        return host, password

    def _write_plan_to(self, dest: Path) -> Path:
        if not self._plan or not self._plan.mappings:
            raise ValueError(_t("gcode_rw.err.analyze_first"))
        return apply_rewrite_plan(self._plan, dest)

    def _resolved_upload_path(self) -> Path | None:
        if self._last_saved and self._last_saved.is_file():
            return self._last_saved
        raw = self._path_var.get().strip()
        if not raw:
            return None
        p = Path(raw)
        if not p.is_file():
            return None
        if self._plan and p.resolve() == self._plan.source_path.resolve():
            tmp = Path(tempfile.gettempdir()) / default_output_path(self._plan.source_path).name
            return self._write_plan_to(tmp)
        return p

    def _pick_save_path(self) -> Path | None:
        if not self._plan:
            return None
        dest = filedialog.asksaveasfilename(
            parent=self._dlg,
            title=_t("gcode_rw.save_title"),
            initialfile=default_output_path(self._plan.source_path).name,
            defaultextension=".gcode",
            filetypes=[("G-Code", "*.gcode")],
        )
        if not dest:
            return None
        return Path(dest)

    def _after_saved(self, out: Path, *, close: bool) -> None:
        self._last_saved = out
        self._path_var.set(str(out))
        if self._on_saved:
            self._on_saved(out)
        messagebox.showinfo(
            _t("gcode_rw.title"),
            _t("gcode_rw.done", path=str(out)),
            parent=self._dlg,
        )
        if close:
            self._dlg.destroy()

    def _save_as(self) -> None:
        if not self._plan or not self._plan.mappings:
            messagebox.showwarning(
                _t("gcode_rw.title"), _t("gcode_rw.err.analyze_first"), parent=self._dlg
            )
            return
        dest = self._pick_save_path()
        if not dest:
            return
        try:
            out = self._write_plan_to(dest)
        except (OSError, ValueError) as e:
            messagebox.showerror(_t("gcode_rw.title"), str(e), parent=self._dlg)
            return
        self._after_saved(out, close=False)

    def _save_and_upload(self) -> None:
        if not self._plan or not self._plan.mappings:
            messagebox.showwarning(
                _t("gcode_rw.title"), _t("gcode_rw.err.analyze_first"), parent=self._dlg
            )
            return
        creds = self._printer_credentials()
        if not creds:
            return
        dest = self._pick_save_path()
        if not dest:
            return
        try:
            out = self._write_plan_to(dest)
        except (OSError, ValueError) as e:
            messagebox.showerror(_t("gcode_rw.title"), str(e), parent=self._dlg)
            return
        self._last_saved = out
        self._path_var.set(str(out))
        if self._on_saved:
            self._on_saved(out)
        self._start_upload(out, creds, close_after=True)

    def _upload(self) -> None:
        creds = self._printer_credentials()
        if not creds:
            return
        try:
            path = self._resolved_upload_path()
        except (OSError, ValueError) as e:
            messagebox.showerror(_t("gcode_rw.title"), str(e), parent=self._dlg)
            return
        if path is None:
            messagebox.showwarning(
                _t("gcode_rw.title"),
                _t("gcode_rw.err.analyze_first"),
                parent=self._dlg,
            )
            return
        if self._plan and path.resolve() == self._plan.source_path.resolve():
            messagebox.showwarning(
                _t("gcode_rw.title"),
                _t("gcode_rw.err.upload_original"),
                parent=self._dlg,
            )
            return
        self._start_upload(path, creds, close_after=False)

    def _start_upload(
        self, local: Path, creds: tuple[str, str], *, close_after: bool
    ) -> None:
        host, password = creds
        self._upload_status.set(_t("gcode_rw.uploading", name=local.name))

        def work() -> None:
            try:
                remote = upload_gcode_to_printer(host, password, local)
                self._dlg.after(
                    0, lambda: self._after_upload(remote, local, close_after=close_after)
                )
            except Exception as exc:
                self._dlg.after(0, lambda: self._upload_failed(str(exc)))

        threading.Thread(target=work, daemon=True).start()

    def _upload_failed(self, msg: str) -> None:
        self._upload_status.set("")
        notify(self._dlg, msg, "error")

    def _after_upload(self, remote: str, local: Path, *, close_after: bool) -> None:
        self._upload_status.set(_t("gcode_rw.upload_done", name=local.name))
        notify(self._dlg, _t("gcode_rw.uploaded", remote=remote), "ok")
        if self._on_uploaded:
            self._on_uploaded(remote, local)
        if close_after:
            self._dlg.destroy()


def open_gcode_rewrite_dialog(
    parent: tk.Misc,
    inventory: SpoolInventory,
    *,
    initial_path: Path | None = None,
    on_uploaded: Callable[[str, Path], None] | None = None,
) -> None:
    GcodeRewriteDialog(
        parent, inventory, initial_path=initial_path, on_uploaded=on_uploaded
    )
