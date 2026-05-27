"""Hilfe-Tab: Programm + JSON-Parameter."""

from __future__ import annotations

import tkinter as tk
from tkinter import scrolledtext, ttk

from creality_nfc.i18n import t as _t
from creality_nfc.kvparam_docs import KVPARAM_DOCS, describe_key
from creality_nfc.mcode_docs import MCODE_DOCS, describe_mcode, mcode_categories
from ui.dialog_theme import theme_dialog
from ui.help_content import PROGRAM_HELP
from ui.theme import apply_text_area_style


class HelpPanel(ttk.Frame):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        theme_dialog(self)

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        tab_prog = ttk.Frame(nb)
        tab_json = ttk.Frame(nb)
        tab_mcode = ttk.Frame(nb)
        nb.add(tab_prog, text=_t("help.tab.program"))
        nb.add(tab_json, text=_t("help.tab.json"))
        nb.add(tab_mcode, text=_t("help.tab.mcode"))

        prog = scrolledtext.ScrolledText(
            tab_prog,
            wrap="word",
            font=("Segoe UI", 10),
            height=20,
        )
        prog.pack(fill="both", expand=True, padx=8, pady=8)
        prog.insert("1.0", PROGRAM_HELP.strip())
        prog.config(state="disabled")
        apply_text_area_style(prog)

        top = ttk.Frame(tab_json)
        top.pack(fill="x", padx=8, pady=8)
        ttk.Label(top, text=_t("help.search_param")).pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._filter())
        ttk.Entry(top, textvariable=self.search_var).pack(side="left", fill="x", expand=True, padx=8)

        tree_frame = ttk.Frame(tab_json)
        tree_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        cols = ("key", "desc")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=22)
        self.tree.heading("key", text=_t("help.col.json_key"))
        self.tree.heading("desc", text=_t("help.col.desc"))
        self.tree.column("key", width=280)
        self.tree.column("desc", width=520)
        sy = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sy.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sy.pack(side="right", fill="y")
        self._fill_tree()

        m_top = ttk.Frame(tab_mcode)
        m_top.pack(fill="x", padx=8, pady=8)
        ttk.Label(m_top, text=_t("help.search_mcode")).pack(side="left")
        self.mcode_search_var = tk.StringVar()
        self.mcode_search_var.trace_add("write", lambda *_: self._fill_mcode_tree())
        ttk.Entry(m_top, textvariable=self.mcode_search_var).pack(side="left", fill="x", expand=True, padx=8)

        m_frame = ttk.Frame(tab_mcode)
        m_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        m_cols = ("code", "desc")
        self.mcode_tree = ttk.Treeview(m_frame, columns=m_cols, show="headings", height=22)
        self.mcode_tree.heading("code", text=_t("help.col.mcode"))
        self.mcode_tree.heading("desc", text=_t("help.col.desc"))
        self.mcode_tree.column("code", width=100)
        self.mcode_tree.column("desc", width=700)
        m_sy = ttk.Scrollbar(m_frame, orient="vertical", command=self.mcode_tree.yview)
        self.mcode_tree.configure(yscrollcommand=m_sy.set)
        self.mcode_tree.pack(side="left", fill="both", expand=True)
        m_sy.pack(side="right", fill="y")
        hint = ttk.Label(
            tab_mcode,
            text=_t("help.mcode_hint"),
            style="Muted.TLabel",
            wraplength=900,
        )
        hint.pack(anchor="w", padx=12, pady=(0, 8))
        self._fill_mcode_tree()

    def _fill_mcode_tree(self) -> None:
        for i in self.mcode_tree.get_children():
            self.mcode_tree.delete(i)
        q = self.mcode_search_var.get().strip().lower()
        if q:
            for code in sorted(MCODE_DOCS.keys()):
                desc = MCODE_DOCS[code]
                if q in code.lower() or q in desc.lower():
                    self.mcode_tree.insert("", "end", values=(code, desc))
            return
        seen: set[str] = set()
        for _title, codes in mcode_categories():
            for code in codes:
                if code in seen or code not in MCODE_DOCS:
                    continue
                seen.add(code)
                self.mcode_tree.insert("", "end", values=(code, MCODE_DOCS[code]))
        for code in sorted(MCODE_DOCS.keys()):
            if code not in seen:
                self.mcode_tree.insert("", "end", values=(code, MCODE_DOCS[code]))

    def _fill_tree(self, query: str = "") -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        q = query.lower()
        for key in sorted(KVPARAM_DOCS.keys()):
            desc = describe_key(key)
            if q and q not in key.lower() and q not in desc.lower():
                continue
            self.tree.insert("", "end", values=(key, desc))

    def _filter(self) -> None:
        self._fill_tree(self.search_var.get().strip())
