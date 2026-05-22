"""Dialog: Druck-Check vor Start."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from creality_nfc.print_readiness import PrintReadinessReport, ReadinessLine
from ui.dialog_theme import prepare_toplevel, theme_dialog
from ui.rounded_widgets import rounded_button
from ui.theme import BG, OK, TEXT, WARN


_LEVEL_FG = {
    "ok": OK,
    "warn": WARN,
    "error": "#e85d5d",
    "info": TEXT,
}


def show_print_check_dialog(
    parent: tk.Misc,
    report: PrintReadinessReport,
) -> None:
    dlg = tk.Toplevel(parent)
    dlg.title("Druck-Check")
    prepare_toplevel(
        dlg,
        parent,
        width=640,
        height=480,
        geometry_key="print_check",
        min_width=520,
        min_height=360,
    )

    top = ttk.Frame(dlg, padding=10)
    top.pack(fill="x")
    short = report.filename.replace("\\", "/").rsplit("/", 1)[-1]
    ttk.Label(
        top,
        text=f"Prüfe markierte Datei: {short}",
        font=("Segoe UI", 11, "bold"),
    ).pack(anchor="w")
    ttk.Label(
        top,
        text="(Die Datei muss in der Liste grün markiert sein — nicht der letzte Druck.)",
        style="Muted.TLabel",
        wraplength=520,
    ).pack(anchor="w", pady=(2, 0))
    ttk.Label(top, text=report.summary(), style="Muted.TLabel").pack(anchor="w", pady=(4, 0))

    body = tk.Frame(dlg, bg=BG)
    body.pack(fill="both", expand=True, padx=10, pady=6)
    sy = ttk.Scrollbar(body, orient="vertical")
    canvas = tk.Canvas(body, highlightthickness=0, bg=BG, yscrollcommand=sy.set)
    inner = tk.Frame(canvas, bg=BG)
    inner_id = canvas.create_window((0, 0), window=inner, anchor="nw")
    sy.config(command=canvas.yview)
    sy.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    def _on_configure(_e: tk.Event | None = None) -> None:
        canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.itemconfigure(inner_id, width=canvas.winfo_width())

    inner.bind("<Configure>", _on_configure)
    canvas.bind("<Configure>", _on_configure)

    for ln in report.lines:
        _add_line(inner, ln)

    if not report.lines:
        ttk.Label(
            inner,
            text="Keine Prüfdaten — G-Code und CFS-Verbindung prüfen.",
            style="Muted.TLabel",
        ).pack(anchor="w", padx=8, pady=4)

    foot = tk.Frame(dlg, bg=BG)
    foot.pack(side="bottom", fill="x", padx=14, pady=12)
    rounded_button(foot, "Schließen", dlg.destroy, variant="accent", compact=True).pack(
        side="right"
    )


def _add_line(parent: tk.Misc, ln: ReadinessLine) -> None:
    fg = _LEVEL_FG.get(ln.level, TEXT)
    prefix = {"ok": "✓", "warn": "!", "error": "✗", "info": "·"}.get(ln.level, "·")
    row = tk.Frame(parent, bg=BG)
    row.pack(fill="x", padx=8, pady=3)
    tk.Label(
        row,
        text=f"{prefix} {ln.text}",
        bg=BG,
        fg=fg,
        anchor="w",
        justify="left",
        wraplength=540,
    ).pack(anchor="w")
