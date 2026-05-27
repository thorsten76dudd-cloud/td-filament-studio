"""Dialog: Verbrauch nach Druck — pro G-Code-Slot/Farbe."""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk

from creality_nfc.i18n import t as _t
from ui.dialog_theme import add_dialog_footer, center_toplevel, theme_dialog
from ui.theme import BG


@dataclass
class DeductRow:
    spool_id: str
    slot_label: str
    spool_label: str
    color_hex: str | None
    material: str | None
    default_grams: int
    source: str
    cfs_filament: str = ""


def ask_post_print_deductions(
    parent: tk.Misc,
    *,
    filename: str,
    rows: list[DeductRow],
) -> list[tuple[str, int]] | None:
    """
    Nutzer bestätigt Abzüge pro Spule.
    Rückgabe: [(spool_id, grams), …] oder None bei Abbruch.
    """
    if not rows:
        return []
    if len(rows) == 1:
        r = rows[0]
        from tkinter import simpledialog

        detail = _row_detail(r, compact=False)
        suffix = f": {filename}" if filename else ""
        grams = simpledialog.askinteger(
            _t("deduct.title"),
            _t("deduct.single_prompt", suffix=suffix, detail=detail),
            initialvalue=r.default_grams,
            minvalue=0,
            maxvalue=5000,
            parent=parent,
        )
        if grams is None or grams <= 0:
            return []
        return [(r.spool_id, grams)]

    win = tk.Toplevel(parent)
    win.title(_t("deduct.title"))
    theme_dialog(win)
    win.transient(parent)
    win.configure(bg=BG)

    header = ttk.Frame(win)
    short_name = filename.replace("\\", "/").rsplit("/", 1)[-1] if filename else ""
    suffix = f": {short_name}" if short_name else ""
    title = _t("deduct.dialog_header", suffix=suffix)
    ttk.Label(
        header,
        text=title,
        font=("Segoe UI", 11, "bold"),
        wraplength=580,
    ).pack(anchor="w")
    ttk.Label(
        header,
        text=_t("deduct.subhint"),
        wraplength=580,
    ).pack(anchor="w", pady=(4, 0))

    list_host = ttk.Frame(win)

    canvas = tk.Canvas(
        list_host,
        highlightthickness=0,
        borderwidth=0,
        bg=BG,
    )
    scroll = ttk.Scrollbar(list_host, orient="vertical", command=canvas.yview)
    body = ttk.Frame(canvas)
    body_id = canvas.create_window((0, 0), window=body, anchor="nw")

    def _on_body_configure(_event: tk.Event | None = None) -> None:
        canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.itemconfigure(body_id, width=canvas.winfo_width())

    def _on_canvas_configure(event: tk.Event) -> None:
        canvas.itemconfigure(body_id, width=event.width)

    body.bind("<Configure>", _on_body_configure)
    canvas.bind("<Configure>", _on_canvas_configure)
    canvas.configure(yscrollcommand=scroll.set)
    canvas.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")

    def _wheel(event: tk.Event) -> None:
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _bind_wheel(_event: tk.Event | None = None) -> None:
        canvas.bind_all("<MouseWheel>", _wheel)

    def _unbind_wheel(_event: tk.Event | None = None) -> None:
        try:
            canvas.unbind_all("<MouseWheel>")
        except tk.TclError:
            pass

    canvas.bind("<Enter>", _bind_wheel)
    canvas.bind("<Leave>", _unbind_wheel)

    entries: list[tuple[DeductRow, tk.BooleanVar, tk.StringVar]] = []
    for r in rows:
        row_f = ttk.Frame(body)
        row_f.pack(fill="x", pady=6, padx=2)
        enabled = tk.BooleanVar(value=True)
        grams_var = tk.StringVar(value=str(r.default_grams))
        ttk.Checkbutton(row_f, variable=enabled).grid(row=0, column=0, rowspan=2, sticky="nw", padx=(0, 8))
        ttk.Label(
            row_f,
            text=_row_detail(r, compact=True),
            wraplength=520,
            justify="left",
        ).grid(row=0, column=1, sticky="w")
        gram_f = ttk.Frame(row_f)
        gram_f.grid(row=0, column=2, rowspan=2, sticky="ne", padx=(12, 0))
        ttk.Label(gram_f, text=_t("deduct.grams")).pack(side="left", padx=(0, 4))
        ttk.Entry(gram_f, textvariable=grams_var, width=8).pack(side="left")
        row_f.columnconfigure(1, weight=1)
        entries.append((r, enabled, grams_var))

    result: list[tuple[str, int]] | None = None

    def _ok() -> None:
        nonlocal result
        out: list[tuple[str, int]] = []
        for r, en, gv in entries:
            if not en.get():
                continue
            try:
                g = int(gv.get().strip())
            except ValueError:
                g = 0
            if g > 0:
                out.append((r.spool_id, g))
        result = out
        _unbind_wheel()
        win.destroy()

    def _cancel() -> None:
        nonlocal result
        result = None
        _unbind_wheel()
        win.destroy()

    # Footer zuerst packen (bottom), sonst verdrängt expand=True die Buttons.
    add_dialog_footer(
        win,
        on_ok=_ok,
        on_cancel=_cancel,
        ok_text=_t("deduct.btn_apply"),
        cancel_text=_t("deduct.btn_cancel"),
    )
    header.pack(side="top", fill="x", padx=14, pady=(12, 6))
    list_host.pack(side="top", fill="both", expand=True, padx=14, pady=(0, 4))

    win.protocol("WM_DELETE_WINDOW", _cancel)

    row_block = 72
    want_h = 130 + len(rows) * row_block + 80
    max_h = max(360, int(win.winfo_screenheight() * 0.82))
    dlg_h = min(want_h, max_h)
    dlg_w = 640
    win.minsize(560, 300)

    from ui.window_geometry import get_window_geometry_manager

    mgr = get_window_geometry_manager()
    if mgr:
        mgr.attach_toplevel(
            win,
            "post_print_deduct",
            default_width=dlg_w,
            default_height=dlg_h,
            min_width=560,
            min_height=300,
        )
    else:
        win.update_idletasks()
        center_toplevel(win, width=dlg_w, height=dlg_h)
    try:
        win.grab_set()
        parent.wait_window(win)
    finally:
        try:
            win.grab_release()
        except tk.TclError:
            pass
    return result


def _row_detail(r: DeductRow, *, compact: bool) -> str:
    cfs = r.cfs_filament or "—"
    if compact:
        mat = f" · {r.material}" if r.material else ""
        return _t(
            "deduct.row_compact",
            slot=r.slot_label,
            label=r.spool_label,
            mat=mat,
            cfs=cfs,
            grams=r.default_grams,
        )
    parts = [_t("deduct.row_full", slot=r.slot_label, cfs=cfs, label=r.spool_label)]
    if r.material:
        parts.append(r.material)
    if r.source:
        parts.append(_t("deduct.source_grams", source=r.source, grams=r.default_grams))
    return " · ".join(parts)
