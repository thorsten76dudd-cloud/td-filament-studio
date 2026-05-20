"""Tab Modell-Bibliothek: STL/3MF-Sammlung mit Ordnern."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from typing import TYPE_CHECKING

from app.paths import DATA_DIR
from creality_nfc.windows_mesh_open import open_mesh_in_system_viewer, open_mesh_with_default_app
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
        self._drag_entry_id: str | None = None
        self._drag_start_xy: tuple[int, int] | None = None
        self._drag_active = False
        self._drop_highlight: str | None = None
        self._last_file_entry_id: str | None = None

        top = ttk.Frame(self)
        top.pack(fill="x", padx=8, pady=8)
        tip(
            ttk.Button(top, text="Datei importieren…", command=self._import_copy, style="Accent.TButton"),
            "STL, 3MF, PDF, Bilder, ZIP … in die Bibliothek kopieren.",
        ).pack(side="left", padx=(0, 6))
        tip(
            ttk.Button(top, text="Verknüpfung…", command=self._import_link, style="Secondary.TButton"),
            "Nur Pfad merken — Datei bleibt am ursprünglichen Ort.",
        ).pack(side="left", padx=(0, 6))
        tip(
            ttk.Button(top, text="Datei löschen", command=self._delete_file, style="Secondary.TButton"),
            "Ausgewählte Datei aus der Bibliothek entfernen.",
        ).pack(side="left", padx=(0, 6))
        tip(
            ttk.Button(top, text="Umbenennen…", command=self._rename_file, style="Secondary.TButton"),
            "Anzeigename der ausgewählten Datei ändern.",
        ).pack(side="left", padx=(0, 6))
        tip(
            ttk.Button(top, text="In Ordner verschieben…", command=self._move_file, style="Secondary.TButton"),
            "Ausgewählte Datei in einen anderen Ordner verschieben.",
        ).pack(side="left", padx=(0, 6))
        tip(
            ttk.Button(top, text="Speichern unter…", command=self._export_file, style="Accent.TButton"),
            "Ausgewählte Datei(en) exportieren (mehrere: Strg+Klick, dann Zielordner wählen).",
        ).pack(side="right", padx=(6, 0))
        tip(
            ttk.Button(top, text="Im Explorer öffnen", command=self._open_in_explorer, style="Secondary.TButton"),
            "Datei oder Bibliotheks-Ordner im Explorer anzeigen.",
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
        ttk.Label(folder_col, text="Ordner", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        self._folder_path_var = tk.StringVar(value="Bibliothek")
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
            ttk.Button(fbtns, text="Unterordner", command=self._new_folder, style="Secondary.TButton"),
            "Neuen Unterordner im gewählten Ordner anlegen.",
        ).pack(side="left", padx=(0, 4), pady=4)
        tip(
            ttk.Button(fbtns, text="Umbenennen", command=self._rename_folder, style="Secondary.TButton"),
            "Gewählten Ordner umbenennen (nicht Bibliothek).",
        ).pack(side="left", padx=(0, 4), pady=4)
        tip(
            ttk.Button(fbtns, text="Löschen", command=self._delete_folder, style="Secondary.TButton"),
            "Ordner inkl. Unterordner und Dateien löschen.",
        ).pack(side="left", padx=(0, 4), pady=4)
        tip(
            ttk.Button(fbtns, text="↑ Überordner", command=self._goto_parent_folder, style="Secondary.TButton"),
            "Zum übergeordneten Ordner springen.",
        ).pack(side="left", pady=4)
        folder_wrap = ttk.Frame(folder_col)
        folder_wrap.grid(row=3, column=0, sticky="nsew")
        folder_wrap.columnconfigure(0, weight=1)
        folder_wrap.rowconfigure(0, weight=1)
        self.folder_tree = ttk.Treeview(folder_wrap, show="tree", height=14)
        fsy = ttk.Scrollbar(folder_wrap, orient="vertical", command=self.folder_tree.yview)
        self.folder_tree.configure(yscrollcommand=fsy.set)
        self.folder_tree.grid(row=0, column=0, sticky="nsew")
        fsy.grid(row=0, column=1, sticky="ns")
        self.folder_tree.bind("<<TreeviewSelect>>", self._on_folder_select)
        self.folder_tree.tag_configure("drop_target", background=ACCENT_SOFT)

        files_col = ttk.Frame(left_split)
        left_split.add(files_col, weight=2)
        files_col.columnconfigure(0, weight=1)
        files_col.rowconfigure(4, weight=1)
        self._files_title = ttk.Label(files_col, text="Dateien", style="Muted.TLabel")
        self._files_title.grid(row=0, column=0, sticky="w")
        files_path_hdr = ttk.Frame(files_col, height=_hdr_h)
        files_path_hdr.grid(row=1, column=0, sticky="ew", pady=(2, 0))
        files_path_hdr.grid_propagate(False)
        self._files_path_lbl = ttk.Label(files_path_hdr, text="", style="Muted.TLabel", wraplength=280)
        self._files_path_lbl.pack(anchor="nw", fill="x")
        file_btns = ttk.Frame(files_col, height=_btn_h)
        search_row = ttk.Frame(files_col)
        search_row.grid(row=2, column=0, sticky="ew", pady=(4, 0))
        ttk.Label(search_row, text="Suche:").pack(side="left")
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._reload_files())
        ttk.Entry(search_row, textvariable=self._search_var).pack(side="left", fill="x", expand=True, padx=6)
        self._filter_done_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            search_row,
            text="Nur offen",
            variable=self._filter_done_var,
            command=self._reload_files,
        ).pack(side="left")
        file_btns = ttk.Frame(files_col, height=_btn_h)
        file_btns.grid(row=3, column=0, sticky="ew", pady=(4, 4))
        file_btns.grid_propagate(False)
        tip(
            ttk.Button(file_btns, text="Umbenennen", command=self._rename_file, style="Secondary.TButton"),
            "Ausgewählte Datei umbenennen (F2).",
        ).pack(side="left", padx=(0, 4), pady=4)
        tip(
            ttk.Button(file_btns, text="Erledigt ✓", command=self._toggle_done_selected, style="Secondary.TButton"),
            "Ausgewählte Datei(en) als gedruckt/erledigt markieren oder Markierung entfernen.",
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
        right.rowconfigure(1, weight=1)
        ttk.Label(right, text="Details", style="Muted.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 4))
        self._left_split = left_split

        meta = ttk.LabelFrame(right, text="  Ausgewählte Datei  ", padding=8)
        meta.grid(row=1, column=0, sticky="nsew")
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
                text="Erledigt (bereits gedruckt / fertig)",
                variable=self._done_var,
                command=self._on_done_checkbox,
            ),
            "Haken setzen = Teil ist erledigt. Bleibt nach Neustart gespeichert.",
        ).pack(anchor="w")
        ttk.Label(meta, text="Anzeigename", style="Muted.TLabel").grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(meta, textvariable=self._name_var).grid(row=2, column=0, sticky="ew", **pad)
        ttk.Label(meta, text="Quelle (URL)", style="Muted.TLabel").grid(row=3, column=0, sticky="w", **pad)
        ttk.Entry(meta, textvariable=self._url_var).grid(row=4, column=0, sticky="ew", **pad)
        ttk.Label(meta, text="Bemerkung", style="Muted.TLabel").grid(row=5, column=0, sticky="w", **pad)
        ttk.Entry(meta, textvariable=self._notes_var).grid(row=6, column=0, sticky="ew", **pad)
        ttk.Label(meta, text="Pfad", style="Muted.TLabel").grid(row=7, column=0, sticky="w", **pad)
        self._path_entry = ttk.Entry(meta, textvariable=self._path_var, state="readonly")
        self._path_entry.grid(row=8, column=0, sticky="ew", **pad)
        meta_btns = ttk.Frame(meta)
        meta_btns.grid(row=9, column=0, sticky="ew", pady=(8, 0))
        meta_btns.columnconfigure(1, weight=1)
        left_btns = ttk.Frame(meta_btns)
        left_btns.grid(row=0, column=0, sticky="w")
        tip(
            ttk.Button(left_btns, text="In Creality öffnen", command=self._open_in_creality, style="Secondary.TButton"),
            "STL/3MF in Creality Print (Windows-Standard-App für diese Dateitypen).",
        ).pack(side="left", padx=(0, 6))
        tip(
            ttk.Button(left_btns, text="3D-Viewer wählen…", command=self._open_in_3d_viewer, style="Secondary.TButton"),
            "Windows 3D Viewer / Paint 3D — falls nicht installiert: „Öffnen mit“-Dialog.",
        ).pack(side="left")
        tip(
            ttk.Button(meta_btns, text="Details speichern", command=self._save_meta, style="Accent.TButton"),
            "Name, URL und Bemerkung für die ausgewählte Datei speichern.",
        ).grid(row=0, column=2, sticky="e")

        ttk.Label(
            self,
            text="Strg+Klick = mehrere Dateien. Export: Speichern unter… | Verschieben: auf Ordner ziehen.",
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

    def _reload_folders(self) -> None:
        self.folder_tree.delete(*self.folder_tree.get_children())
        root = self.library.folder_by_id("root")
        root_name = root.name if root else "Bibliothek"
        self.folder_tree.insert("", "end", iid="root", text=root_name, open=True)
        self._insert_folder_children("root")

    def _insert_folder_children(self, parent_id: str) -> None:
        for folder in self.library.child_folders(parent_id):
            n_files = self.library.entry_count(folder.id, include_subfolders=True)
            n_sub = len(self.library.child_folders(folder.id))
            label = folder.name
            if n_files or n_sub:
                label = f"{folder.name}  ({n_files} Datei{'en' if n_files != 1 else ''})"
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
        self._files_title.config(text="Dateien")
        self._files_path_lbl.config(text=path)
        self._update_folder_path_label()
        query = self._search_var.get().strip().lower()
        only_open = self._filter_done_var.get()
        for e in self.library.entries_in_folder(self._current_folder_id):
            if only_open and e.done:
                continue
            if query:
                hay = f"{e.display_name} {e.notes} {e.source_url} {e.file_ext}".lower()
                if query not in hay:
                    continue
            storage = "Kopie" if e.storage == "copy" else "Link"
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
        self._path_var.set(str(path) if path else "— Datei nicht gefunden —")

    def _clear_details(self) -> None:
        self._name_var.set("")
        self._url_var.set("")
        self._notes_var.set("")
        self._path_var.set("")
        self._done_var.set(False)

    def _collect_importable_paths(self, paths: list[Path]) -> list[Path]:
        allowed = ALLOWED_EXT | ARCHIVE_EXT
        out: list[Path] = []
        for raw in paths:
            p = Path(raw)
            if p.is_file():
                if p.suffix.lower() in allowed:
                    out.append(p)
            elif p.is_dir():
                for child in sorted(p.rglob("*")):
                    if child.is_file() and child.suffix.lower() in allowed:
                        out.append(child)
        return out

    def _import_paths(self, paths: list[Path], folder_id: str | None = None) -> int:
        target = folder_id or self._current_folder_id
        items = self._collect_importable_paths(paths)
        if not items:
            return 0
        n = 0
        for path in items:
            try:
                if path.suffix.lower() == ".zip":
                    n += len(self.library.import_zip(path, target))
                else:
                    self.library.import_file(path, target)
                    n += 1
            except (OSError, ValueError) as exc:
                notify(self, f"{path.name}: {exc}", "error")
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
            self.folder_tree,
            self.files_tree,
        ]
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
            notify(self, f"{n} Datei(en) importiert.", "ok")
        else:
            notify(
                self,
                "Keine unterstützten Dateien (STL, 3MF, ZIP, PDF, Bilder …).",
                "warn",
            )

    def _import_copy(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Dateien importieren",
            filetypes=[
                ("Alles unterstützte", "*.stl *.3mf *.zip *.pdf *.png *.jpg *.jpeg *.gif *.txt *.md *.gcode"),
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
            notify(self, f"{n} Datei(en) importiert.", "ok")

    def _import_link(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Datei verknüpfen",
            filetypes=[
                ("Unterstützte Dateien", "*.stl *.3mf *.pdf *.png *.jpg *.jpeg *.gif *.txt *.md *.gcode"),
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
                notify(self, f"{Path(p).name}: {exc}", "error")
        if n:
            notify(self, f"{n} Verknüpfung(en) angelegt.", "ok")
            self._reload_files()

    def _ask_name(self, title: str, prompt: str, initial: str = "") -> str | None:
        result: list[str | None] = [None]
        dlg = tk.Toplevel(self)
        dlg.title(title)
        prepare_toplevel(dlg, self, width=460, height=200)

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
        name = self._ask_name("Unterordner", "Name des neuen Ordners:")
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
        notify(self, f"Unterordner „{folder.name}“ angelegt.", "ok")

    def _rename_folder(self) -> None:
        folder_id = self._folder_id_for_rename()
        if not folder_id:
            notify(self, "Bitte einen Ordner in der Liste links wählen.", "warn")
            return
        folder = self.library.folder_by_id(folder_id)
        if not folder:
            return
        title = "Hauptordner umbenennen" if folder_id == "root" else "Ordner umbenennen"
        name = self._ask_name(title, "Neuer Name:", folder.name)
        if not name:
            return
        self.library.rename_folder(folder_id, name)
        self._reload_folders()
        self._open_folder_in_tree(folder_id)
        if self.folder_tree.exists(folder_id):
            self.folder_tree.selection_set(folder_id)
        self._reload_files()
        notify(self, f"Umbenannt in „{name}“.", "ok")

    def _rename_file(self) -> None:
        entry = self._selected_entry()
        if not entry:
            notify(self, "Bitte eine Datei in der Liste wählen.", "warn")
            return
        name = self._ask_name("Datei umbenennen", "Neuer Anzeigename:", entry.display_name)
        if not name:
            return
        self.library.rename_entry(entry.id, name)
        self._name_var.set(name)
        self._reload_files()
        self._reload_folders()
        if self.files_tree.exists(entry.id):
            self.files_tree.selection_set(entry.id)
        notify(self, f"Umbenannt in „{name}“.", "ok")

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
            notify(self, "Bitte einen Unterordner wählen.", "warn")
            return
        folder_id = sel[0]
        folder = self.library.folder_by_id(folder_id)
        if not folder:
            return
        n = self.library.entry_count(folder_id, include_subfolders=True)
        sub = len(self.library.child_folders(folder_id))
        msg = f"Ordner „{folder.name}“ wirklich löschen?"
        if n or sub:
            msg += f"\n\nInkl. Unterordner: {n} Datei(en) werden entfernt."

        def do_del() -> None:
            removed = self.library.delete_folder_recursive(folder_id)
            self._current_folder_id = "root"
            self._reload_folders()
            self.folder_tree.selection_set("root")
            self._reload_files()
            self._clear_details()
            notify(self, f"Ordner gelöscht ({removed} Datei(en) entfernt).", "ok")

        confirm(self, msg, do_del)

    def _delete_file(self) -> None:
        entry = self._selected_entry()
        if not entry:
            notify(self, "Bitte eine Datei auswählen.", "warn")
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
            notify(self, f"„{name}“ entfernt.", "ok")

        confirm(self, f"„{name}“ aus der Bibliothek entfernen?", do_del)

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
            notify(self, "Bitte eine oder mehrere Dateien auswählen.", "warn")
            return
        mark_done = not all(e.done for e in entries)
        for entry in entries:
            self.library.set_entry_done(entry.id, mark_done)
        sel = [e.id for e in entries]
        self._reload_files()
        self.files_tree.selection_set([i for i in sel if self.files_tree.exists(i)])
        notify(
            self,
            f"{len(entries)} Datei(en) als {'erledigt' if mark_done else 'offen'} markiert.",
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

    def _on_file_drag_press(self, event) -> None:
        if self.files_tree.identify_region(event.x, event.y) != "cell":
            self._cancel_drag()
            return
        row = self.files_tree.identify_row(event.y)
        if not row:
            self._cancel_drag()
            return
        self._drag_entry_id = row
        self._last_file_entry_id = row
        self._drag_start_xy = (event.x_root, event.y_root)
        self._drag_active = False
        self.bind("<B1-Motion>", self._on_drag_motion_global, add="+")
        self.bind("<ButtonRelease-1>", self._on_drag_release, add="+")

    def _on_drag_motion_global(self, event) -> None:
        if not self._drag_entry_id or not self._drag_start_xy:
            return
        if not self._drag_active:
            dx = abs(event.x_root - self._drag_start_xy[0])
            dy = abs(event.y_root - self._drag_start_xy[1])
            if dx + dy < 8:
                return
            self._drag_active = True
        self._update_drop_highlight()

    def _on_drag_release(self, _event) -> None:
        entry_id = self._drag_entry_id
        was_drag = self._drag_active
        folder_id = self._drop_highlight or self._folder_at_pointer()
        self._end_drag()
        if not was_drag or not entry_id:
            return
        if folder_id:
            self._apply_move_to_folder(entry_id, folder_id)
        else:
            notify(self, "Zum Verschieben auf einen Ordner links loslassen.", "warn")

    def _cancel_drag(self) -> None:
        self._drag_entry_id = None
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

    def _apply_move_to_folder(self, entry_id: str, target_folder_id: str) -> None:
        entry = self.library.get_entry(entry_id)
        if not entry:
            return
        if entry.folder_id == target_folder_id:
            return
        self.library.move_entry(entry_id, target_folder_id)
        self._current_folder_id = target_folder_id
        self._reload_folders()
        self._open_folder_in_tree(target_folder_id)
        if self.folder_tree.exists(target_folder_id):
            self.folder_tree.selection_set(target_folder_id)
        self._reload_files()
        if self.files_tree.exists(entry_id):
            self.files_tree.selection_set(entry_id)
            self._on_file_select()
        notify(self, f"Verschoben nach: {self.library.folder_breadcrumb(target_folder_id)}", "ok")

    def _move_file(self) -> None:
        entry = self._selected_entry()
        if not entry:
            notify(self, "Bitte eine Datei auswählen.", "warn")
            return
        options = self.library.all_folders_for_picker()
        labels = [label for label, _fid in options]
        if not labels:
            return

        dlg = tk.Toplevel(self)
        dlg.title("In Ordner verschieben")
        prepare_toplevel(dlg, self, width=480, height=200)
        picked: list[str] = []

        def ok() -> None:
            picked.append(choice.get())
            dlg.destroy()

        add_dialog_footer(dlg, on_ok=ok, on_cancel=dlg.destroy, ok_text="Verschieben")
        body = ttk.Frame(dlg)
        body.pack(fill="both", expand=True, padx=14, pady=14)
        ttk.Label(body, text=f"Zielordner für „{entry.display_name}“:").pack(anchor="w", pady=(0, 8))
        choice = tk.StringVar(value=labels[0])
        combo = ttk.Combobox(body, textvariable=choice, values=labels, state="readonly", width=42)
        combo.pack(fill="x", pady=4)
        dlg.wait_window()
        if not picked:
            return
        label_to_id = {label: fid for label, fid in options}
        target_id = label_to_id.get(picked[0], "root")
        self._apply_move_to_folder(entry.id, target_id)

    def _save_meta(self) -> None:
        entry = self._selected_entry()
        if not entry:
            notify(self, "Bitte eine Datei auswählen.", "warn")
            return
        entry.display_name = self._name_var.get().strip() or entry.display_name
        entry.source_url = self._url_var.get().strip()
        entry.notes = self._notes_var.get().strip()
        self.library.update_entry(entry)
        self._reload_files()
        self.files_tree.selection_set(entry.id)
        notify(self, "Gespeichert.", "ok")

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
        entries = self._selected_entries()
        if not entries:
            notify(self, "Bitte eine oder mehrere Dateien auswählen.", "warn")
            return

        if len(entries) == 1:
            entry = entries[0]
            src = entry.resolved_path(self.library.root)
            if not src:
                notify(self, "Datei nicht gefunden (Pfad prüfen).", "warn")
                return
            default_name = self._export_dest_name(entry, src)
            ext = Path(default_name).suffix
            dest = filedialog.asksaveasfilename(
                parent=self,
                title="Datei speichern unter",
                initialfile=default_name,
                defaultextension=ext,
                filetypes=[
                    ("Alle Dateien", "*.*"),
                    (f"{ext.upper()} Dateien", f"*{ext}"),
                ],
            )
            if not dest:
                return
            try:
                shutil.copy2(src, Path(dest))
                notify(self, f"Gespeichert:\n{dest}", "ok")
            except OSError as exc:
                notify(self, str(exc), "error")
            return

        dest_dir = filedialog.askdirectory(
            parent=self,
            title=f"{len(entries)} Dateien exportieren — Zielordner wählen",
        )
        if not dest_dir:
            return
        folder = Path(dest_dir)
        ok = 0
        failed: list[str] = []
        for entry in entries:
            src = entry.resolved_path(self.library.root)
            if not src:
                failed.append(entry.display_name)
                continue
            dest = self._unique_dest_path(folder, self._export_dest_name(entry, src), entry.id)
            try:
                shutil.copy2(src, dest)
                ok += 1
            except OSError as exc:
                failed.append(f"{entry.display_name}: {exc}")
        if ok:
            msg = f"{ok} Datei(en) nach\n{dest_dir}"
            if failed:
                msg += f"\n\nFehler ({len(failed)}):\n" + "\n".join(failed[:5])
            notify(self, msg, "ok" if not failed else "warn")
        elif failed:
            notify(self, "Export fehlgeschlagen:\n" + "\n".join(failed[:8]), "error")

    def _selected_mesh_path(self) -> Path | None:
        entry = self._selected_entry()
        if not entry:
            notify(self, "Bitte zuerst eine Datei auswählen.", "warn")
            return None
        path = entry.resolved_path(self.library.root)
        if not path or not path.is_file():
            notify(self, "Datei nicht gefunden.", "warn")
            return None
        if path.suffix.lower() not in {".stl", ".3mf"}:
            notify(self, "Nur STL- und 3MF-Dateien können in einem 3D-Programm geöffnet werden.", "warn")
            return None
        return path

    def _open_in_creality(self) -> None:
        path = self._selected_mesh_path()
        if not path:
            return
        ok, err = open_mesh_with_default_app(path)
        if not ok:
            notify(self, f"Creality / Standard-App konnte nicht gestartet werden:\n{err}", "error")

    def _open_in_3d_viewer(self) -> None:
        path = self._selected_mesh_path()
        if not path:
            return
        ok, hint = open_mesh_in_system_viewer(path)
        if ok:
            if hint:
                notify(self, hint, "info")
        else:
            notify(self, hint or "3D-Viewer konnte nicht gestartet werden.", "error")

    def _open_in_explorer(self) -> None:
        entry = self._selected_entry()
        if entry:
            path = entry.resolved_path(self.library.root)
            if not path:
                notify(self, "Datei nicht gefunden (Pfad prüfen).", "warn")
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
