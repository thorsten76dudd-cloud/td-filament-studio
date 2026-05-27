"""Tab Modell-Bibliothek: STL/3MF-Sammlung mit Ordnern."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING

from app.paths import DATA_DIR
from creality_nfc.config import APP_NAME
from creality_nfc.i18n import t as _t
from creality_nfc.data_backup import (
    backup_model_library,
    default_model_library_backup_name,
    restore_model_library,
)
from creality_nfc.windows_mesh_open import open_mesh_choose_viewer, open_mesh_with_default_app
from creality_nfc.model_library import (
    ARCHIVE_EXT,
    ALLOWED_EXT,
    ModelEntry,
    ModelLibrary,
)
from ui.dnd_files import parse_dnd_file_list
from ui.tk_root import HAS_OS_DND
from ui.dialog_theme import add_dialog_footer, prepare_toplevel, theme_dialog
from ui.messaging import confirm, notify
from ui.stl_preview_widget import StlPreviewWidget
from ui.theme import ACCENT_SOFT, MUTED, OK
from ui.tooltip import tip

if TYPE_CHECKING:
    from app.main_window import TDFilamentStudioApp

LIBRARY_ROOT = DATA_DIR / "model_library"


class ModelLibraryPanel(ttk.Frame):
    def __init__(self, app: TDFilamentStudioApp) -> None:
        super().__init__(app.tab_models)
        theme_dialog(self)
        self.app = app
        self.library = ModelLibrary(LIBRARY_ROOT)
        self._current_folder_id = "root"
        self._drag_entry_ids: list[str] = []
        self._drag_folder_ids: list[str] = []
        self._drag_start_xy: tuple[int, int] | None = None
        self._drag_active = False
        self._drop_highlight: str | None = None
        self._last_file_entry_id: str | None = None

        top = ttk.Frame(self)
        top.pack(fill="x", padx=8, pady=8)
        tip(
            ttk.Button(top, text=_t("mlp.btn.import_file"), command=self._import_copy, style="Accent.TButton"),
            _t("mlp.drop_hint"),
        ).pack(side="left", padx=(0, 6))
        tip(
            ttk.Button(top, text=_t("mlp.btn.import_folder"), command=self._import_folder_copy, style="Secondary.TButton"),
            _t("mlp.tip.import_folder"),
        ).pack(side="left", padx=(0, 6))
        tip(
            ttk.Button(top, text=_t("mlp.btn.link"), command=self._import_link, style="Secondary.TButton"),
            _t("mlp.btn.link_tip"),
        ).pack(side="left", padx=(0, 6))
        tip(
            ttk.Button(top, text=_t("mlp.btn.delete_file"), command=self._delete_file, style="Secondary.TButton"),
            _t("mlp.btn.delete_file_tip"),
        ).pack(side="left", padx=(0, 6))
        tip(
            ttk.Button(top, text=_t("mlp.btn.rename"), command=self._rename_file, style="Secondary.TButton"),
            _t("mlp.btn.rename_file_tip"),
        ).pack(side="left", padx=(0, 6))
        tip(
            ttk.Button(top, text=_t("mlp.btn.move"), command=self._move_to_folder_dialog, style="Secondary.TButton"),
            _t("mlp.btn.move_tip"),
        ).pack(side="left", padx=(0, 6))
        tip(
            ttk.Button(top, text=_t("mlp.btn.backup"), command=self._backup_library, style="Secondary.TButton"),
            _t("mlp.tip.backup"),
        ).pack(side="right", padx=(6, 0))
        tip(
            ttk.Button(top, text=_t("mlp.btn.restore"), command=self._restore_library, style="Secondary.TButton"),
            _t("mlp.btn.restore_tip"),
        ).pack(side="right", padx=(6, 0))
        tip(
            ttk.Button(top, text=_t("mlp.btn.save_as"), command=self._export_file, style="Accent.TButton"),
            _t("mlp.btn.export_tip"),
        ).pack(side="right", padx=(6, 0))
        tip(
            ttk.Button(top, text=_t("mlp.btn.open_explorer"), command=self._open_in_explorer, style="Secondary.TButton"),
            _t("mlp.tip.open_explorer"),
        ).pack(side="right", padx=(6, 0))

        self._body_pane = ttk.Panedwindow(self, orient="horizontal")
        self._body_pane.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        left_col = ttk.Frame(self._body_pane)
        self._body_pane.add(left_col, weight=1)

        left_split = ttk.Panedwindow(left_col, orient="horizontal")
        left_split.pack(fill="both", expand=True)

        _hdr_h = 76
        _btn_h = 40

        folder_col = ttk.Frame(left_split)
        left_split.add(folder_col, weight=1)
        folder_col.columnconfigure(0, weight=1)
        folder_col.rowconfigure(3, weight=1)
        ttk.Label(folder_col, text=_t("mlp.label.folder"), style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        self._folder_path_var = tk.StringVar(value=_t("mlp.library.root"))
        path_hdr = ttk.Frame(folder_col, height=_hdr_h)
        path_hdr.grid(row=1, column=0, sticky="ew", pady=(2, 0))
        path_hdr.grid_propagate(False)
        ttk.Label(
            path_hdr,
            textvariable=self._folder_path_var,
            style="Muted.TLabel",
            wraplength=200,
        ).pack(anchor="nw", fill="x")
        fbtns = ttk.Frame(folder_col, height=_btn_h)
        fbtns.grid(row=2, column=0, sticky="ew", pady=(4, 4))
        fbtns.grid_propagate(False)
        tip(
            ttk.Button(fbtns, text=_t("mlp.btn.subfolder"), command=self._new_folder, style="Secondary.TButton"),
            _t("mlp.btn.new_subfolder_tip"),
        ).pack(side="left", padx=(0, 4), pady=4)
        tip(
            ttk.Button(fbtns, text=_t("mlp.btn.rename_short"), command=self._rename_folder, style="Secondary.TButton"),
            _t("mlp.btn.rename_folder_tip"),
        ).pack(side="left", padx=(0, 4), pady=4)
        tip(
            ttk.Button(fbtns, text=_t("mlp.btn.delete_folder"), command=self._delete_folder, style="Secondary.TButton"),
            _t("mlp.btn.delete_folder_tip"),
        ).pack(side="left", padx=(0, 4), pady=4)
        tip(
            ttk.Button(fbtns, text=_t("mlp.btn.parent_folder"), command=self._goto_parent_folder, style="Secondary.TButton"),
            _t("mlp.btn.parent_folder_tip"),
        ).pack(side="left", pady=4)
        folder_wrap = ttk.Frame(folder_col)
        folder_wrap.grid(row=3, column=0, sticky="nsew")
        folder_wrap.columnconfigure(0, weight=1)
        folder_wrap.rowconfigure(0, weight=1)
        self.folder_tree = ttk.Treeview(folder_wrap, show="tree", height=14, selectmode="extended")
        fsy = ttk.Scrollbar(folder_wrap, orient="vertical", command=self.folder_tree.yview)
        self.folder_tree.configure(yscrollcommand=fsy.set)
        self.folder_tree.grid(row=0, column=0, sticky="nsew")
        fsy.grid(row=0, column=1, sticky="ns")
        self.folder_tree.bind("<<TreeviewSelect>>", self._on_folder_select)
        self.folder_tree.bind("<ButtonPress-1>", self._on_folder_drag_press, add="+")
        self.folder_tree.tag_configure("drop_target", background=ACCENT_SOFT)

        files_col = ttk.Frame(left_split)
        left_split.add(files_col, weight=2)
        files_col.columnconfigure(0, weight=1)
        files_col.rowconfigure(4, weight=1)
        self._files_title = ttk.Label(files_col, text=_t("mlp.label.files"), style="Muted.TLabel")
        self._files_title.grid(row=0, column=0, sticky="w")
        files_path_hdr = ttk.Frame(files_col, height=_hdr_h)
        files_path_hdr.grid(row=1, column=0, sticky="ew", pady=(2, 0))
        files_path_hdr.grid_propagate(False)
        self._files_path_lbl = ttk.Label(files_path_hdr, text="", style="Muted.TLabel", wraplength=280)
        self._files_path_lbl.pack(anchor="nw", fill="x")
        file_btns = ttk.Frame(files_col, height=_btn_h)
        search_row = ttk.Frame(files_col)
        search_row.grid(row=2, column=0, sticky="ew", pady=(4, 0))
        ttk.Label(search_row, text=_t("mlp.label.search")).pack(side="left")
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._reload_files())
        ttk.Entry(search_row, textvariable=self._search_var).pack(side="left", fill="x", expand=True, padx=6)
        self._filter_done_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            search_row,
            text=_t("mlp.chk.open_only"),
            variable=self._filter_done_var,
            command=self._reload_files,
        ).pack(side="left")
        file_btns = ttk.Frame(files_col, height=_btn_h)
        file_btns.grid(row=3, column=0, sticky="ew", pady=(4, 4))
        file_btns.grid_propagate(False)
        tip(
            ttk.Button(file_btns, text=_t("mlp.btn.rename_short"), command=self._rename_file, style="Secondary.TButton"),
            _t("mlp.btn.rename_file_f2_tip"),
        ).pack(side="left", padx=(0, 4), pady=4)
        tip(
            ttk.Button(file_btns, text=_t("mlp.btn.done"), command=self._toggle_done_selected, style="Secondary.TButton"),
            _t("mlp.btn.mark_done_tip"),
        ).pack(side="left", padx=(0, 4), pady=4)
        files_wrap = ttk.Frame(files_col)
        files_wrap.grid(row=4, column=0, sticky="nsew")
        files_wrap.columnconfigure(0, weight=1)
        files_wrap.rowconfigure(0, weight=1)
        cols = ("done", "name", "type", "storage")
        self.files_tree = ttk.Treeview(
            files_wrap,
            columns=cols,
            show="headings",
            height=14,
            selectmode="extended",
        )
        for c, title, w, anchor in (
            ("done", "✓", 28, "center"),
            ("name", "Name", 128, "w"),
            ("type", "Typ", 44, "w"),
            ("storage", "Ablage", 64, "w"),
        ):
            self.files_tree.heading(c, text=title)
            self.files_tree.column(c, width=w, minwidth=24, anchor=anchor)
        self.files_tree.tag_configure("file_done", foreground=OK)
        self.files_tree.tag_configure("file_open", foreground=MUTED)
        fsy2 = ttk.Scrollbar(files_wrap, orient="vertical", command=self.files_tree.yview)
        self.files_tree.configure(yscrollcommand=fsy2.set)
        self.files_tree.grid(row=0, column=0, sticky="nsew")
        fsy2.grid(row=0, column=1, sticky="ns")
        self.files_tree.bind("<<TreeviewSelect>>", self._on_file_select)
        self.files_tree.bind("<Button-1>", self._on_files_tree_click, add="+")
        self.files_tree.bind("<Double-1>", self._on_files_tree_double_click)
        self.files_tree.bind("<Delete>", lambda _e: self._delete_file())
        self.files_tree.bind("<ButtonPress-1>", self._on_file_drag_press, add="+")
        self.bind("<F2>", self._on_f2_rename)

        right = ttk.Frame(self._body_pane)
        self._body_pane.add(right, weight=1)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)
        self._left_split = left_split

        right_split = ttk.Panedwindow(right, orient="vertical")
        self._right_split = right_split
        right_split.grid(row=0, column=0, sticky="nsew")
        preview_wrap = ttk.LabelFrame(right_split, text=_t("mlp.section.preview"), padding=6)
        right_split.add(preview_wrap, weight=3)
        preview_wrap.columnconfigure(0, weight=1)
        preview_wrap.rowconfigure(0, weight=1)
        self._stl_preview = StlPreviewWidget(preview_wrap)
        self._stl_preview.grid(row=0, column=0, sticky="nsew")
        preview_wrap.rowconfigure(0, weight=1)
        preview_wrap.columnconfigure(0, weight=1)
        self._stl_preview.set_external_handler(self._open_stl_external)
        preview_wrap.bind("<Configure>", lambda _e: self._stl_preview.fit_to_panel(), add="+")
        self._right_split.bind("<ButtonRelease-1>", lambda _e: self._stl_preview.fit_to_panel(), add="+")

        meta = ttk.LabelFrame(right_split, text=_t("mlp.section.selected_file"), padding=8)
        right_split.add(meta, weight=2)
        meta.columnconfigure(0, weight=1)
        pad = {"padx": 0, "pady": 3}
        self._name_var = tk.StringVar()
        self._url_var = tk.StringVar()
        self._notes_var = tk.StringVar()
        self._path_var = tk.StringVar()
        self._done_var = tk.BooleanVar()
        done_row = ttk.Frame(meta)
        done_row.grid(row=0, column=0, sticky="w", **pad)
        tip(
            ttk.Checkbutton(
                done_row,
                text=_t("mlp.chk.printed"),
                variable=self._done_var,
                command=self._on_done_checkbox,
            ),
            _t("mlp.tip.done_checkbox"),
        ).pack(anchor="w")
        ttk.Label(meta, text=_t("mlp.label.display_name"), style="Muted.TLabel").grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(meta, textvariable=self._name_var).grid(row=2, column=0, sticky="ew", **pad)
        ttk.Label(meta, text=_t("mlp.label.source_url"), style="Muted.TLabel").grid(row=3, column=0, sticky="w", **pad)
        ttk.Entry(meta, textvariable=self._url_var).grid(row=4, column=0, sticky="ew", **pad)
        ttk.Label(meta, text=_t("mlp.label.note"), style="Muted.TLabel").grid(row=5, column=0, sticky="w", **pad)
        ttk.Entry(meta, textvariable=self._notes_var).grid(row=6, column=0, sticky="ew", **pad)
        ttk.Label(meta, text=_t("mlp.label.path"), style="Muted.TLabel").grid(row=7, column=0, sticky="w", **pad)
        self._path_entry = ttk.Entry(meta, textvariable=self._path_var, state="readonly")
        self._path_entry.grid(row=8, column=0, sticky="ew", **pad)
        meta_btns = ttk.Frame(meta)
        meta_btns.grid(row=9, column=0, sticky="ew", pady=(8, 0))
        meta_btns.columnconfigure(1, weight=1)
        left_btns = ttk.Frame(meta_btns)
        left_btns.grid(row=0, column=0, sticky="w")
        tip(
            ttk.Button(left_btns, text=_t("mlp.btn.open"), command=self._open_selected_file, style="Secondary.TButton"),
            _t("mlp.tip.open_file_types"),
        ).pack(side="left", padx=(0, 6))
        tip(
            ttk.Button(left_btns, text=_t("mlp.btn.open_creality"), command=self._open_in_creality, style="Secondary.TButton"),
            _t("mlp.btn.open_creality_tip"),
        ).pack(side="left", padx=(0, 6))
        tip(
            ttk.Button(left_btns, text=_t("mlp.btn.open_3d"), command=self._open_in_3d_viewer, style="Secondary.TButton"),
            _t("mlp.btn.open_3dviewer_tip"),
        ).pack(side="left")
        tip(
            ttk.Button(meta_btns, text=_t("mlp.btn.save_details"), command=self._save_meta, style="Accent.TButton"),
            _t("mlp.btn.save_meta_tip"),
        ).grid(row=0, column=2, sticky="e")

        ttk.Label(
            self,
            text=_t("mlp.hint.save_under"),
            style="Muted.TLabel",
            wraplength=920,
        ).pack(anchor="w", padx=12, pady=(0, 8))

        self._reload_folders()
        self.folder_tree.selection_set("root")
        self._reload_files()
        self.after_idle(self._init_pane_sizes)
        self._setup_pc_drop()

    def _init_pane_sizes(self) -> None:
        self.update_idletasks()
        total = self._body_pane.winfo_width()
        if total < 700:
            return
        left_w = min(520, max(420, int(total * 0.55)))
        try:
            self._body_pane.sashpos(0, left_w)
        except tk.TclError:
            pass
        try:
            self._left_split.sashpos(0, 180)
        except tk.TclError:
            pass
        try:
            self._right_split.sashpos(0, 220)
        except tk.TclError:
            pass

    def _reload_folders(self) -> None:
        self.folder_tree.delete(*self.folder_tree.get_children())
        root = self.library.folder_by_id("root")
        root_name = root.name if root else _t("mlp.library.root")
        self.folder_tree.insert("", "end", iid="root", text=root_name, open=True)
        self._insert_folder_children("root")

    def _insert_folder_children(self, parent_id: str) -> None:
        for folder in self.library.child_folders(parent_id):
            n_files = self.library.entry_count(folder.id, include_subfolders=True)
            n_sub = len(self.library.child_folders(folder.id))
            label = folder.name
            if n_files or n_sub:
                label = _t("mlp.folder.file_count", name=folder.name, n=n_files)
            self.folder_tree.insert(parent_id, "end", iid=folder.id, text=label, open=False)
            self._insert_folder_children(folder.id)

    def _update_folder_path_label(self) -> None:
        self._folder_path_var.set(self.library.folder_breadcrumb(self._current_folder_id))

    def _open_folder_in_tree(self, folder_id: str) -> None:
        for iid in self.library.ancestor_ids(folder_id):
            if self.folder_tree.exists(iid):
                self.folder_tree.item(iid, open=True)

    def _reload_files(self) -> None:
        try:
            yview = self.files_tree.yview()
        except tk.TclError:
            yview = (0.0, 1.0)
        sel = list(self.files_tree.selection())
        focus = self.files_tree.focus()
        self.files_tree.delete(*self.files_tree.get_children())
        path = self.library.folder_breadcrumb(self._current_folder_id)
        self._files_title.config(text=_t("mlp.label.files"))
        self._files_path_lbl.config(text=path)
        self._update_folder_path_label()
        for e in self.library.entries_in_folder(self._current_folder_id):
            if not self._entry_matches_file_filter(e):
                continue
            storage = _t("mlp.storage.copy") if e.storage == "copy" else _t("mlp.storage.link")
            mark = "✓" if e.done else ""
            tags = ("file_done",) if e.done else ("file_open",)
            self.files_tree.insert(
                "",
                "end",
                iid=e.id,
                values=(mark, e.display_name, e.file_ext.lstrip(".").upper(), storage),
                tags=tags,
            )
        restore = [i for i in sel if self.files_tree.exists(i)]
        if restore:
            self.files_tree.selection_set(restore)
            focus_id = focus if focus in restore else restore[0]
            self.files_tree.focus(focus_id)
        try:
            self.files_tree.yview_moveto(yview[0])
        except tk.TclError:
            pass

    def _on_folder_select(self, _event=None) -> None:
        sel = self.folder_tree.selection()
        if sel:
            self._current_folder_id = sel[0]
            self._last_file_entry_id = None
            self._reload_files()

    def _selected_entry_ids(self) -> list[str]:
        sel = list(self.files_tree.selection())
        if sel:
            return sel
        if self._last_file_entry_id:
            return [self._last_file_entry_id]
        return []

    def _selected_entries(self) -> list[ModelEntry]:
        entries: list[ModelEntry] = []
        for entry_id in self._selected_entry_ids():
            entry = self.library.get_entry(entry_id)
            if entry:
                entries.append(entry)
        return entries

    def _entry_matches_file_filter(self, entry: ModelEntry) -> bool:
        if self._filter_done_var.get() and entry.done:
            return False
        query = self._search_var.get().strip().lower()
        if not query:
            return True
        hay = f"{entry.display_name} {entry.notes} {entry.source_url} {entry.file_ext}".lower()
        return query in hay

    def _entries_for_export(self) -> tuple[list[tuple[ModelEntry, Path]], str]:
        """
        Export-Plan: (Datei, relativer Unterordner im Ziel).
        Leerer Path = direkt ins Zielverzeichnis.
        """
        file_sel = self._selected_entries()
        if file_sel:
            return [(e, Path()) for e in file_sel], _t("mlp.export.n_files", n=len(file_sel))

        folder_ids = self._selected_movable_folder_ids()
        if folder_ids:
            items = []
            names: list[str] = []
            for fid in folder_ids:
                folder = self.library.folder_by_id(fid)
                if not folder:
                    continue
                names.append(folder.name)
                base = Path(folder.name)
                for entry in self.library.entries_in_folder_recursive(fid):
                    if not self._entry_matches_file_filter(entry):
                        continue
                    inner = self.library.entry_relative_subpath(fid, entry)
                    items.append((entry, base / inner if inner.parts else base))
            label = ", ".join(names[:3])
            if len(names) > 3:
                label += f" … (+{len(names) - 3})"
            return items, _t("mlp.export.folder_label", label=label)

        items = []
        for entry in self.library.entries_in_folder_recursive(self._current_folder_id):
            if not self._entry_matches_file_filter(entry):
                continue
            rel = self.library.entry_relative_subpath(self._current_folder_id, entry)
            items.append((entry, rel))
        return items, self.library.folder_breadcrumb(self._current_folder_id)

    def _selected_entry(self) -> ModelEntry | None:
        entries = self._selected_entries()
        return entries[0] if entries else None

    def _on_file_select(self, _event=None) -> None:
        sel = self.files_tree.selection()
        if sel:
            self._last_file_entry_id = sel[0]
        entry = self._selected_entry()
        if not entry:
            self._last_file_entry_id = None
            self._clear_details()
            return
        self._done_var.set(entry.done)
        self._name_var.set(entry.display_name)
        self._url_var.set(entry.source_url)
        self._notes_var.set(entry.notes)
        path = entry.resolved_path(self.library.root)
        self._path_var.set(str(path) if path else _t("mlp.path.not_found"))
        self._update_stl_preview(entry, path)

    def _update_stl_preview(self, entry: ModelEntry, path: Path | None) -> None:
        if not path or not path.is_file():
            self._stl_preview.clear(_t("mlp.preview.file_not_found"))
            return
        ext = (entry.file_ext or path.suffix).lower()
        if ext == ".stl":
            if not self._stl_preview.load_stl(path):
                pass
            return
        if ext == ".3mf":
            self._stl_preview.clear(_t("mlp.preview.3mf_external"))
            return
        self._stl_preview.clear(_t("mlp.preview.stl_only"))

    def _open_stl_external(self, path: Path) -> None:
        self._open_in_3d_viewer_for_path(path)

    def _clear_details(self) -> None:
        self._name_var.set("")
        self._url_var.set("")
        self._notes_var.set("")
        self._path_var.set("")
        self._done_var.set(False)
        self._stl_preview.clear()

    def _resolve_drop_path(self, raw: Path) -> Path:
        try:
            return raw.resolve()
        except OSError:
            return raw

    def _import_one_file(self, path: Path, target_folder_id: str) -> int:
        ext = path.suffix.lower()
        if ext == ".zip":
            return len(self.library.import_zip(path, target_folder_id))
        self.library.import_file(path, target_folder_id)
        return 1

    def _import_paths(self, paths: list[Path], folder_id: str | None = None) -> int:
        target = folder_id or self._current_folder_id
        n = 0
        for raw in paths:
            p = self._resolve_drop_path(raw)
            if not p.exists():
                notify(self, _t("mlp.notify.not_found_raw", raw=raw), "warn")
                continue
            try:
                if p.is_dir():
                    n += self.library.import_directory(p, target)
                elif p.is_file():
                    allowed = ALLOWED_EXT | ARCHIVE_EXT
                    if p.suffix.lower() not in allowed:
                        continue
                    n += self._import_one_file(p, target)
            except (OSError, ValueError) as exc:
                notify(self, _t("mlp.notify.path_error", name=p.name, exc=exc), "error")
        if n:
            self._reload_folders()
            self._reload_files()
        return n

    def _setup_pc_drop(self) -> None:
        if not HAS_OS_DND:
            return
        try:
            from tkinterdnd2 import DND_FILES
        except ImportError:
            return
        widgets: list[tk.Misc] = [
            self,
            self.app.tab_models,
            self._body_pane,
            self._left_split,
            self.folder_tree,
            self.files_tree,
        ]
        try:
            top = self.winfo_toplevel()
            if top not in widgets:
                widgets.append(top)
        except tk.TclError:
            pass
        for widget in widgets:
            try:
                widget.drop_target_register(DND_FILES)
                widget.dnd_bind("<<Drop>>", self._on_pc_drop)
            except tk.TclError:
                pass

    def _on_pc_drop(self, event) -> None:
        paths = parse_dnd_file_list(getattr(event, "data", ""))
        if not paths:
            return
        folder_id = self._folder_at_pointer() or self._current_folder_id
        n = self._import_paths(paths, folder_id)
        if n:
            notify(self, _t("mlp.notify.imported", n=n), "ok")
        else:
            notify(
                self,
                _t("mlp.notify.unsupported"),
                "warn",
            )

    def _import_folder_copy(self) -> None:
        path = filedialog.askdirectory(parent=self, title=_t("mlp.title.import_folder"))
        if not path:
            return
        n = self._import_paths([Path(path)])
        if n:
            notify(self, _t("mlp.notify.imported", n=n), "ok")
        else:
            notify(
                self,
                _t("mlp.notify.no_supported_in_folder"),
                "warn",
            )

    def _import_copy(self) -> None:
        paths = filedialog.askopenfilenames(
            title=_t("mlp.title.import_files"),
            filetypes=[
                (_t("mlp.dialog.all_supported"), "*.stl *.3mf *.zip *.pdf *.png *.jpg *.jpeg *.gif *.txt *.md *.gcode"),
                ("ZIP-Projekt", "*.zip"),
                ("3D-Modelle", "*.stl *.3mf"),
                ("PDF", "*.pdf"),
                ("Bilder", "*.png *.jpg *.jpeg *.gif *.webp *.bmp"),
                ("Dokumente", "*.txt *.md *.csv *.json"),
                ("Alle", "*.*"),
            ],
        )
        if not paths:
            return
        n = self._import_paths([Path(p) for p in paths])
        if n:
            notify(self, _t("mlp.notify.imported", n=n), "ok")

    def _import_link(self) -> None:
        paths = filedialog.askopenfilenames(
            title=_t("mlp.dialog.link_file_title"),
            filetypes=[
                (_t("mlp.dialog.supported_files"), "*.stl *.3mf *.pdf *.png *.jpg *.jpeg *.gif *.txt *.md *.gcode"),
                ("3D-Modelle", "*.stl *.3mf"),
                ("PDF", "*.pdf"),
                ("Alle", "*.*"),
            ],
        )
        if not paths:
            return
        n = 0
        for p in paths:
            try:
                self.library.link_file(Path(p), self._current_folder_id)
                n += 1
            except (OSError, ValueError) as exc:
                notify(self, _t("mlp.notify.path_error", name=Path(p).name, exc=exc), "error")
        if n:
            notify(self, _t("mlp.notify.links_created", n=n), "ok")
            self._reload_files()

    def _ask_name(self, title: str, prompt: str, initial: str = "") -> str | None:
        result: list[str | None] = [None]
        dlg = tk.Toplevel(self)
        dlg.title(title)
        prepare_toplevel(dlg, self, width=460, height=200, geometry_key="model_new_folder")

        def ok(_event=None) -> None:
            val = var.get().strip()
            if val:
                result[0] = val
            dlg.destroy()

        add_dialog_footer(dlg, on_ok=ok, on_cancel=dlg.destroy)
        body = ttk.Frame(dlg)
        body.pack(fill="both", expand=True, padx=14, pady=14)
        ttk.Label(body, text=prompt, wraplength=400).pack(anchor="w", pady=(0, 8))
        var = tk.StringVar(value=initial)
        entry = ttk.Entry(body, textvariable=var, width=48)
        entry.pack(fill="x", pady=4)
        dlg.bind("<Return>", ok)
        dlg.bind("<Escape>", lambda _e: dlg.destroy())
        dlg.after_idle(lambda: (entry.focus_set(), entry.icursor(tk.END), entry.select_range(0, tk.END)))
        dlg.wait_window()
        return result[0]

    def _on_f2_rename(self, event=None) -> None:
        try:
            tab = self.app.notebook.nametowidget(self.app.notebook.select())
        except tk.TclError:
            return
        if tab is not self.app.tab_models:
            return
        try:
            focus = self.focus_get()
        except tk.TclError:
            focus = None
        if focus == self.files_tree or self.files_tree.selection():
            self._rename_file()
            return
        self._rename_folder()

    def _folder_id_for_rename(self) -> str | None:
        sel = self.folder_tree.selection()
        if sel:
            return sel[0]
        return self._current_folder_id

    def _new_folder(self) -> None:
        name = self._ask_name(_t("mlp.prompt.subfolder"), _t("mlp.prompt.subfolder_name"))
        if not name:
            return
        parent_id = self._current_folder_id
        folder = self.library.add_folder(name.strip(), parent_id)
        self._reload_folders()
        self._open_folder_in_tree(parent_id)
        if self.folder_tree.exists(folder.id):
            self.folder_tree.selection_set(folder.id)
            self.folder_tree.see(folder.id)
            self._current_folder_id = folder.id
            self._reload_files()
        notify(self, _t("mlp.notify.folder_created", name=folder.name), "ok")

    def _rename_folder(self) -> None:
        folder_id = self._folder_id_for_rename()
        if not folder_id:
            notify(self, _t("mlp.notify.pick_folder_left"), "warn")
            return
        folder = self.library.folder_by_id(folder_id)
        if not folder:
            return
        title = _t("mlp.title.rename_root") if folder_id == "root" else _t("mlp.title.rename_folder")
        name = self._ask_name(title, "Neuer Name:", folder.name)
        if not name:
            return
        self.library.rename_folder(folder_id, name)
        self._reload_folders()
        self._open_folder_in_tree(folder_id)
        if self.folder_tree.exists(folder_id):
            self.folder_tree.selection_set(folder_id)
        self._reload_files()
        notify(self, _t("mlp.notify.renamed", name=name), "ok")

    def _rename_file(self) -> None:
        entry = self._selected_entry()
        if not entry:
            notify(self, _t("mlp.notify.pick_file"), "warn")
            return
        name = self._ask_name(_t("mlp.prompt.rename_file"), _t("mlp.prompt.new_display_name"), entry.display_name)
        if not name:
            return
        self.library.rename_entry(entry.id, name)
        self._name_var.set(name)
        self._reload_files()
        self._reload_folders()
        if self.files_tree.exists(entry.id):
            self.files_tree.selection_set(entry.id)
        notify(self, _t("mlp.notify.renamed", name=name), "ok")

    def _goto_parent_folder(self) -> None:
        if self._current_folder_id == "root":
            return
        folder = self.library.folder_by_id(self._current_folder_id)
        if not folder:
            return
        parent_id = folder.parent_id or "root"
        if self.folder_tree.exists(parent_id):
            self.folder_tree.selection_set(parent_id)
            self.folder_tree.see(parent_id)
            self._current_folder_id = parent_id
            self._reload_files()

    def _delete_folder(self) -> None:
        sel = self.folder_tree.selection()
        if not sel or sel[0] == "root":
            notify(self, _t("mlp.notify.pick_subfolder"), "warn")
            return
        folder_id = sel[0]
        folder = self.library.folder_by_id(folder_id)
        if not folder:
            return
        n = self.library.entry_count(folder_id, include_subfolders=True)
        sub = len(self.library.child_folders(folder_id))
        msg = _t("mlp.confirm.delete_folder", name=folder.name)
        if n or sub:
            msg += "\n\n" + _t("mlp.confirm.delete_folder_extra", n=n)

        def do_del() -> None:
            removed = self.library.delete_folder_recursive(folder_id)
            self._current_folder_id = "root"
            self._reload_folders()
            self.folder_tree.selection_set("root")
            self._reload_files()
            self._clear_details()
            notify(self, _t("mlp.notify.folder_deleted", removed=removed), "ok")

        confirm(self, msg, do_del)

    def _delete_file(self) -> None:
        entry = self._selected_entry()
        if not entry:
            notify(self, _t("mlp.notify.pick_file_short"), "warn")
            return

        entry_id = entry.id
        name = entry.display_name

        def do_del() -> None:
            self.library.delete_entry(entry_id)
            if self._last_file_entry_id == entry_id:
                self._last_file_entry_id = None
            self._clear_details()
            self._reload_files()
            self._reload_folders()
            notify(self, _t("mlp.notify.removed", name=name), "ok")

        confirm(self, _t("mlp.confirm.remove", name=name), do_del)

    def _on_files_tree_click(self, event) -> None:
        if self.files_tree.identify_region(event.x, event.y) != "cell":
            return
        if self.files_tree.identify_column(event.x) != "#1":
            return
        row = self.files_tree.identify_row(event.y)
        if row:
            self._toggle_done_entry(row)

    def _on_files_tree_double_click(self, event) -> None:
        if self.files_tree.identify_region(event.x, event.y) == "cell":
            if self.files_tree.identify_column(event.x) == "#1":
                return
        row = self.files_tree.identify_row(event.y)
        if row and self.files_tree.exists(row):
            self.files_tree.selection_set(row)
            self.files_tree.focus(row)
            self._on_file_select()
        entry = self._selected_entry()
        if entry:
            path = entry.resolved_path(self.library.root)
            ext = (entry.file_ext or (path.suffix if path else "")).lower()
            if ext == ".stl":
                return
        if self._open_selected_file(silent=True):
            return
        self._open_in_explorer()

    def _toggle_done_entry(self, entry_id: str) -> None:
        entry = self.library.get_entry(entry_id)
        if not entry:
            return
        self.library.set_entry_done(entry_id, not entry.done)
        sel = list(self.files_tree.selection())
        self._reload_files()
        restore = [i for i in sel if self.files_tree.exists(i)] or [entry_id]
        self.files_tree.selection_set(restore)
        if self.files_tree.exists(entry_id):
            self._on_file_select()

    def _toggle_done_selected(self) -> None:
        entries = self._selected_entries()
        if not entries:
            notify(self, _t("mlp.notify.pick_files"), "warn")
            return
        mark_done = not all(e.done for e in entries)
        for entry in entries:
            self.library.set_entry_done(entry.id, mark_done)
        sel = [e.id for e in entries]
        self._reload_files()
        self.files_tree.selection_set([i for i in sel if self.files_tree.exists(i)])
        notify(
            self,
            _t("mlp.notify.marked_done", n=len(entries), state=_t("mlp.state.done") if mark_done else _t("mlp.state.open")),
            "ok",
        )

    def _on_done_checkbox(self) -> None:
        entry = self._selected_entry()
        if not entry:
            return
        self.library.set_entry_done(entry.id, self._done_var.get())
        entry_id = entry.id
        self._reload_files()
        if self.files_tree.exists(entry_id):
            self.files_tree.selection_set(entry_id)
            self._on_file_select()

    def _selected_movable_folder_ids(self) -> list[str]:
        return [fid for fid in self.folder_tree.selection() if fid and fid != "root"]

    def _on_folder_drag_press(self, event) -> None:
        row = self.folder_tree.identify_row(event.y)
        if not row or row == "root":
            self._cancel_drag()
            return
        sel = self._selected_movable_folder_ids()
        if row in sel:
            folder_ids = sel
        else:
            folder_ids = [row]
        self._drag_folder_ids = folder_ids
        self._drag_entry_ids = []
        self._drag_start_xy = (event.x_root, event.y_root)
        self._drag_active = False
        self.bind("<B1-Motion>", self._on_drag_motion_global, add="+")
        self.bind("<ButtonRelease-1>", self._on_drag_release, add="+")

    def _on_file_drag_press(self, event) -> None:
        if self.files_tree.identify_region(event.x, event.y) != "cell":
            self._cancel_drag()
            return
        row = self.files_tree.identify_row(event.y)
        if not row:
            self._cancel_drag()
            return
        sel = list(self.files_tree.selection())
        if row in sel:
            entry_ids = sel
        else:
            entry_ids = [row]
        self._drag_entry_ids = entry_ids
        self._drag_folder_ids = []
        self._last_file_entry_id = row
        self._drag_start_xy = (event.x_root, event.y_root)
        self._drag_active = False
        self.bind("<B1-Motion>", self._on_drag_motion_global, add="+")
        self.bind("<ButtonRelease-1>", self._on_drag_release, add="+")

    def _on_drag_motion_global(self, event) -> None:
        if (not self._drag_entry_ids and not self._drag_folder_ids) or not self._drag_start_xy:
            return
        if not self._drag_active:
            dx = abs(event.x_root - self._drag_start_xy[0])
            dy = abs(event.y_root - self._drag_start_xy[1])
            if dx + dy < 8:
                return
            self._drag_active = True
        self._update_drop_highlight()

    def _on_drag_release(self, _event) -> None:
        entry_ids = list(self._drag_entry_ids)
        folder_ids = list(self._drag_folder_ids)
        was_drag = self._drag_active
        target_id = self._drop_highlight or self._folder_at_pointer()
        self._end_drag()
        if not was_drag:
            return
        if not target_id:
            notify(self, _t("mlp.notify.drop_on_folder"), "warn")
            return
        if folder_ids:
            self._apply_move_folders(folder_ids, target_id)
        elif entry_ids:
            self._apply_move_entries(entry_ids, target_id)

    def _cancel_drag(self) -> None:
        self._drag_entry_ids = []
        self._drag_folder_ids = []
        self._drag_start_xy = None
        self._drag_active = False

    def _end_drag(self) -> None:
        try:
            self.unbind("<ButtonRelease-1>")
            self.unbind("<B1-Motion>")
        except tk.TclError:
            pass
        self._clear_drop_highlight()
        self._cancel_drag()

    def _folder_at_pointer(self) -> str | None:
        try:
            px = self.folder_tree.winfo_pointerx() - self.folder_tree.winfo_rootx()
            py = self.folder_tree.winfo_pointery() - self.folder_tree.winfo_rooty()
        except tk.TclError:
            return None
        if px < 0 or py < 0 or px > self.folder_tree.winfo_width() or py > self.folder_tree.winfo_height():
            return None
        row = self.folder_tree.identify_row(py)
        if row:
            return row
        return self.folder_tree.identify("item", px, py) or None

    def _update_drop_highlight(self) -> None:
        folder_id = self._folder_at_pointer()
        if folder_id == self._drop_highlight:
            return
        self._clear_drop_highlight()
        if folder_id and self.folder_tree.exists(folder_id):
            self.folder_tree.item(folder_id, tags=("drop_target",))
            self._drop_highlight = folder_id

    def _clear_drop_highlight(self) -> None:
        if self._drop_highlight and self.folder_tree.exists(self._drop_highlight):
            self.folder_tree.item(self._drop_highlight, tags=())
        self._drop_highlight = None

    def _finish_move_ui(self, target_folder_id: str, *, focus_entry_ids: list[str] | None = None) -> None:
        self._current_folder_id = target_folder_id
        self._reload_folders()
        self._open_folder_in_tree(target_folder_id)
        if self.folder_tree.exists(target_folder_id):
            self.folder_tree.selection_set(target_folder_id)
        self._reload_files()
        if focus_entry_ids:
            restore = [i for i in focus_entry_ids if self.files_tree.exists(i)]
            if restore:
                self.files_tree.selection_set(restore)
                self.files_tree.focus(restore[0])
                self._on_file_select()

    def _apply_move_entries(self, entry_ids: list[str], target_folder_id: str) -> None:
        moved = 0
        for entry_id in entry_ids:
            entry = self.library.get_entry(entry_id)
            if not entry or entry.folder_id == target_folder_id:
                continue
            if self.library.move_entry(entry_id, target_folder_id):
                moved += 1
        if not moved:
            return
        crumb = self.library.folder_breadcrumb(target_folder_id)
        self._finish_move_ui(target_folder_id, focus_entry_ids=entry_ids)
        notify(
            self,
            _t("mlp.notify.moved_files", n=moved, dest=crumb),
            "ok",
        )

    def _apply_move_folders(self, folder_ids: list[str], target_folder_id: str) -> None:
        moved = 0
        skipped: list[str] = []
        for folder_id in folder_ids:
            if folder_id == target_folder_id:
                continue
            reason = self.library.folder_move_blocked(folder_id, target_folder_id)
            if reason:
                folder = self.library.folder_by_id(folder_id)
                name = folder.name if folder else folder_id
                skipped.append(f"{name}: {reason}")
                continue
            if self.library.move_folder(folder_id, target_folder_id):
                moved += 1
        if moved:
            crumb = self.library.folder_breadcrumb(target_folder_id)
            self._finish_move_ui(target_folder_id)
            msg = _t("mlp.notify.moved_folders", n=moved, dest=crumb)
            if skipped:
                msg += _t("mlp.notify.skipped_header") + "\n".join(skipped[:6])
            notify(self, msg, "ok" if not skipped else "warn")
        elif skipped:
            notify(self, _t("mlp.notify.not_moved", items="\n".join(skipped[:8])), "warn")
        else:
            notify(self, _t("mlp.notify.no_folders_moved"), "warn")

    def _pick_target_folder(self, prompt: str) -> str | None:
        options = self.library.all_folders_for_picker()
        labels = [label for label, _fid in options]
        if not labels:
            return None

        dlg = tk.Toplevel(self)
        dlg.title(_t("mlp.title.move_to_folder"))
        prepare_toplevel(dlg, self, width=480, height=200, geometry_key="model_move_folder")
        picked: list[str] = []

        def ok() -> None:
            picked.append(choice.get())
            dlg.destroy()

        add_dialog_footer(dlg, on_ok=ok, on_cancel=dlg.destroy, ok_text=_t("mlp.btn.move_ok"))
        body = ttk.Frame(dlg)
        body.pack(fill="both", expand=True, padx=14, pady=14)
        ttk.Label(body, text=prompt).pack(anchor="w", pady=(0, 8))
        choice = tk.StringVar(value=labels[0])
        combo = ttk.Combobox(body, textvariable=choice, values=labels, state="readonly", width=42)
        combo.pack(fill="x", pady=4)
        dlg.wait_window()
        if not picked:
            return None
        label_to_id = {label: fid for label, fid in options}
        return label_to_id.get(picked[0], "root")

    def _move_to_folder_dialog(self) -> None:
        entries = self._selected_entries()
        folder_ids = self._selected_movable_folder_ids()
        if entries:
            names = ", ".join(e.display_name for e in entries[:3])
            if len(entries) > 3:
                names += f" … (+{len(entries) - 3})"
            prompt = _t("mlp.move.target_files", n=len(entries), names=names)
            target_id = self._pick_target_folder(prompt)
            if target_id:
                self._apply_move_entries([e.id for e in entries], target_id)
            return
        if folder_ids:
            names = []
            for fid in folder_ids[:4]:
                folder = self.library.folder_by_id(fid)
                if folder:
                    names.append(folder.name)
            label = ", ".join(names)
            if len(folder_ids) > 4:
                label += f" … (+{len(folder_ids) - 4})"
            prompt = _t("mlp.move.target_folders", n=len(folder_ids), label=label)
            target_id = self._pick_target_folder(prompt)
            if target_id:
                self._apply_move_folders(folder_ids, target_id)
            return
        notify(
            self,
            _t("mlp.move.pick_source"),
            "warn",
        )

    def _save_meta(self) -> None:
        entry = self._selected_entry()
        if not entry:
            notify(self, _t("mlp.notify.pick_file_short"), "warn")
            return
        entry.display_name = self._name_var.get().strip() or entry.display_name
        entry.source_url = self._url_var.get().strip()
        entry.notes = self._notes_var.get().strip()
        self.library.update_entry(entry)
        self._reload_files()
        self.files_tree.selection_set(entry.id)
        notify(self, _t("mlp.notify.saved"), "ok")

    def _backup_library(self) -> None:
        self.library.save()
        dest = filedialog.asksaveasfilename(
            parent=self,
            title=_t("mlp.title.backup"),
            defaultextension=".zip",
            initialfile=default_model_library_backup_name(),
            filetypes=[(_t("mlp.filetype.zip_backup"), "*.zip")],
        )
        if not dest:
            return
        try:
            n = backup_model_library(self.library.root, Path(dest))
            notify(
                self,
                _t("mlp.notify.backup_ok", n=n, dest=dest),
                "ok",
            )
        except OSError as exc:
            notify(self, _t("mlp.notify.backup_failed", exc=exc), "error")

    def _restore_library(self) -> None:
        def do_restore() -> None:
            src = filedialog.askopenfilename(
                parent=self,
                title=_t("mlp.title.restore"),
                filetypes=[(_t("mlp.filetype.zip_backup"), "*.zip"), (_t("mlp.filetype.all"), "*.*")],
            )
            if not src:
                return
            try:
                self.library.save()
                n = restore_model_library(Path(src), self.library.root)
                self.library.load()
                self._current_folder_id = "root"
                self._reload_folders()
                self.folder_tree.selection_set("root")
                self._reload_files()
                self._clear_details()
                notify(
                    self,
                    _t("mlp.notify.restore_ok", n=n, src=src),
                    "ok",
                )
            except (OSError, zipfile.BadZipFile, ValueError) as exc:
                notify(self, _t("mlp.notify.restore_failed", exc=exc), "error")

        confirm(
            self,
            _t("mlp.confirm.restore"),
            do_restore,
        )

    def _export_dest_name(self, entry: ModelEntry, src: Path) -> str:
        ext = (entry.file_ext or src.suffix or ".stl").lower()
        if not ext.startswith("."):
            ext = f".{ext}"
        name = entry.display_name.strip() or src.stem
        if not name.lower().endswith(ext):
            name = f"{name}{ext}"
        return name

    def _unique_dest_path(self, folder: Path, filename: str, entry_id: str) -> Path:
        dest = folder / filename
        if not dest.exists():
            return dest
        stem = dest.stem
        suffix = dest.suffix
        alt = folder / f"{stem}_{entry_id[:6]}{suffix}"
        n = 2
        while alt.exists():
            alt = folder / f"{stem}_{entry_id[:6]}_{n}{suffix}"
            n += 1
        return alt

    def _export_file(self) -> None:
        items, label = self._entries_for_export()
        if not items:
            notify(
                self,
                _t("mlp.notify.export_empty"),
                "warn",
            )
            return

        if len(items) == 1 and not items[0][1].parts:
            entry = items[0][0]
            src = entry.resolved_path(self.library.root)
            if not src:
                notify(self, _t("mlp.notify.file_not_found"), "warn")
                return
            default_name = self._export_dest_name(entry, src)
            ext = Path(default_name).suffix
            dest = filedialog.asksaveasfilename(
                parent=self,
                title=_t("mlp.title.save_file_as"),
                initialfile=default_name,
                defaultextension=ext,
                filetypes=[
                    (_t("mlp.filetype.all"), "*.*"),
                    (_t("mlp.filetype.ext", ext=ext.upper()), f"*{ext}"),
                ],
            )
            if not dest:
                return
            try:
                shutil.copy2(src, Path(dest))
                notify(self, _t("mlp.notify.saved_to", dest=dest), "ok")
            except OSError as exc:
                notify(self, str(exc), "error")
            return

        title = _t("mlp.title.export_batch", label=label, n=len(items))
        dest_dir = filedialog.askdirectory(parent=self, title=title)
        if not dest_dir:
            return
        base = Path(dest_dir)
        ok = 0
        failed: list[str] = []
        for entry, rel in items:
            src = entry.resolved_path(self.library.root)
            if not src:
                failed.append(entry.display_name)
                continue
            target_dir = base / rel if rel.parts else base
            target_dir.mkdir(parents=True, exist_ok=True)
            dest = self._unique_dest_path(target_dir, self._export_dest_name(entry, src), entry.id)
            try:
                shutil.copy2(src, dest)
                ok += 1
            except OSError as exc:
                failed.append(f"{entry.display_name}: {exc}")
        if ok:
            msg = _t("mlp.notify.export_ok", n=ok, dest=dest_dir)
            if failed:
                msg += "\n\n" + _t("mlp.notify.export_errors_header", n=len(failed)) + "\n".join(failed[:5])
            notify(self, msg, "ok" if not failed else "warn")
        elif failed:
            notify(self, _t("mlp.notify.export_failed", failed="\n".join(failed[:8])), "error")

    def _entry_for_single_file_action(self, *, silent: bool = False) -> ModelEntry | None:
        """Genau eine Datei für Öffnen / Viewer — Klick in der Dateiliste nötig."""
        selected = self._selected_entries()
        if len(selected) > 1:
            if silent:
                return None
            messagebox.showwarning(
                APP_NAME,
                _t("mlp.notify.only_one_file"),
                parent=self.winfo_toplevel(),
            )
            return None
        if len(selected) == 1:
            return selected[0]
        focus = self.files_tree.focus()
        if focus and self.files_tree.exists(focus):
            entry = self.library.get_entry(focus)
            if entry:
                return entry
        if silent:
            return None
        messagebox.showwarning(
            APP_NAME,
            _t("mlp.msg.pick_one_file") + "\n\n"
            + _t("mlp.msg.pick_one_file_folder_only"),
            parent=self.winfo_toplevel(),
        )
        return None

    @staticmethod
    def _open_path_with_system(path: Path) -> tuple[bool, str]:
        path = path.resolve()
        try:
            if sys.platform == "win32":
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.run(["open", str(path)], check=False)
            else:
                subprocess.run(["xdg-open", str(path)], check=False)
            return True, ""
        except OSError as exc:
            return False, str(exc)

    def _open_selected_file(self, *, silent: bool = False) -> bool:
        """PDF/TXT/Bilder mit Standard-App; STL/3MF im 3D-Viewer. True = geöffnet."""
        entry = self._entry_for_single_file_action(silent=silent)
        if not entry:
            return False
        path = entry.resolved_path(self.library.root)
        if not path or not path.is_file():
            if not silent:
                notify(self, _t("mlp.notify.file_not_found"), "warn")
            return False
        ext = path.suffix.lower()
        if ext in {".stl", ".3mf"}:
            from creality_nfc.windows_mesh_open import open_microsoft_store_3d_viewer

            ok, hint, mode = open_mesh_choose_viewer(path)
            if ok:
                if not silent:
                    notify(self, hint, "ok")
                return True
            if not silent:
                parent = self.winfo_toplevel()
                if mode == "store" and messagebox.askyesno(
                    APP_NAME,
                    _t("mlp.viewer.install_q", hint=hint),
                    parent=parent,
                ):
                    if open_microsoft_store_3d_viewer():
                        notify(self, _t("mlp.viewer.store_opened"), "info")
                    return True
                messagebox.showerror(APP_NAME, hint, parent=parent)
            return False
        if ext in ALLOWED_EXT:
            ok, err = self._open_path_with_system(path)
            if ok:
                return True
            if not silent:
                notify(self, _t("mlp.notify.cannot_open", err=err), "error")
            return False
        if not silent:
            notify(self, _t("mlp.notify.ext_unsupported", ext=ext), "warn")
        return False

    def _selected_mesh_path(self) -> Path | None:
        entry = self._entry_for_single_file_action()
        if not entry:
            return None
        path = entry.resolved_path(self.library.root)
        if not path or not path.is_file():
            messagebox.showwarning(
                APP_NAME,
                _t("mlp.notify.file_not_found") + "\n\n"
                + _t("mlp.notify.entry_prefix", name=entry.display_name) + "\n"
                + _t("mlp.notify.check_path_or_reimport"),
                parent=self.winfo_toplevel(),
            )
            return None
        if path.suffix.lower() not in {".stl", ".3mf"}:
            messagebox.showwarning(
                APP_NAME,
                _t("mlp.notify.only_stl_3mf"),
                parent=self.winfo_toplevel(),
            )
            return None
        return path

    def _open_in_creality(self) -> None:
        path = self._selected_mesh_path()
        if not path:
            return
        ok, err = open_mesh_with_default_app(path)
        if not ok:
            notify(self, _t("mlp.notify.creality_open_failed", err=err), "error")

    def _open_in_3d_viewer_for_path(self, path: Path) -> None:
        from creality_nfc.windows_mesh_open import open_microsoft_store_3d_viewer

        ok, hint, mode = open_mesh_choose_viewer(path)
        parent = self.winfo_toplevel()
        if ok:
            notify(self, hint, "ok")
            return
        if mode == "store" and messagebox.askyesno(
            APP_NAME,
            _t("mlp.viewer.install_q", hint=hint),
            parent=parent,
        ):
            if open_microsoft_store_3d_viewer():
                notify(self, _t("mlp.notify.store_opened"), "info")
            else:
                notify(self, _t("mlp.notify.store_cant_open"), "warn")
            return
        messagebox.showerror(
            APP_NAME,
            _t("mlp.viewer.alt_creality", hint=hint),
            parent=parent,
        )
        notify(self, hint, "error")

    def _open_in_3d_viewer(self) -> None:
        path = self._selected_mesh_path()
        if not path:
            return
        self._open_in_3d_viewer_for_path(path)

    def _open_in_explorer(self) -> None:
        entry = self._selected_entry()
        if entry:
            path = entry.resolved_path(self.library.root)
            if not path:
                notify(self, _t("mlp.notify.file_not_found"), "warn")
                return
            self._show_in_explorer(path)
            return
        folder_dir = self.library.library_dir_for_folder(self._current_folder_id)
        self._show_in_explorer(folder_dir)

    @staticmethod
    def _show_in_explorer(path: Path) -> None:
        path = path.resolve()
        if sys.platform == "win32":
            os.startfile(path if path.is_dir() else path.parent)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
