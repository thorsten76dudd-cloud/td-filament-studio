"""CFS-Live-Ansicht (Creality-Print-Stil)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Literal

from creality_nfc.cfs_adopt import CfsSlotInfo, SLOT_LABELS, parse_cfs_meta
from creality_nfc.cfs_feed import active_slot_label
from creality_nfc.cfs_layout import parse_cfs_layout
from creality_nfc.cfs_slot_index import flat_slot_index
from creality_nfc.cfs_spool_link import find_spool_for_slot
from creality_nfc.color_util import creality_color_to_hex
from ui.theme import BG_SUBTLE, BORDER, CARD, MUTED, WARN
from ui.rounded_widgets import rounded_button
from ui.tooltip import tip

try:
    from ui.printer_tab_theme import P_BORDER, P_CARD, P_CARD_ALT, P_MUTED, P_WARN
except ImportError:
    P_CARD = CARD
    P_CARD_ALT = BG_SUBTLE
    P_BORDER = BORDER
    P_MUTED = MUTED
    P_WARN = WARN

LayoutMode = Literal["grid", "creality"]


class CfsDashboard(ttk.Frame):
    """Spulenhalter + CFS 1A–1D mit Live-Farben und Feuchtigkeit."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        appearance: str = "light",
        layout: LayoutMode = "grid",
        on_adopt: Callable[[int], None],
        on_refresh: Callable[[], None],
        on_feed: Callable[[], None] | None = None,
        on_retract: Callable[[], None] | None = None,
        on_bind_spool: Callable[[int], None] | None = None,
        on_batch_scan: Callable[[], None] | None = None,
        on_preview_toggle: Callable[[], None] | None = None,
        inventory=None,
    ) -> None:
        self._printer = appearance == "printer"
        self._creality = layout == "creality"
        if self._printer:
            self._sf = "Printer.Card.TFrame"
            self._sh = "Printer.CardHeading.TLabel"
            self._sm = "Printer.CardMuted.TLabel"
            self._sb = "Printer.Secondary.TButton"
            self._sa = "Printer.Accent.TButton"
            self._lf = "Printer.TLabelframe"
            self._card_bg = P_CARD
            self._border = P_BORDER
            self._warn = P_WARN
            self._swatch_px = 56 if self._creality else 44
        else:
            self._sf = "Card.TFrame"
            self._sh = "CardHeading.TLabel"
            self._sm = "CardMuted.TLabel"
            self._sb = "Secondary.TButton"
            self._sa = "Accent.TButton"
            self._lf = "TLabelframe"
            self._card_bg = CARD
            self._border = BORDER
            self._warn = WARN
            self._swatch_px = 44

        super().__init__(parent, style=self._sf)
        self._on_adopt = on_adopt
        self._on_refresh = on_refresh
        self._on_feed = on_feed
        self._on_retract = on_retract
        self._on_bind_spool = on_bind_spool
        self._inventory = inventory
        self._selected: int | None = None
        self._printer_active: int | None = None
        self._printer_feeding: int | None = None
        self._slots: list[CfsSlotInfo] = []
        self._layout_sig: tuple[tuple[int, int], ...] = ()
        self._slot_frames: list[tk.Frame] = []
        self._slot_swatches: list[tk.Label] = []
        self._slot_labels: list[ttk.Label] = []
        self._slot_types: list[ttk.Label] = []
        self._slot_inv: list[ttk.Label] = []
        self._slots_area: ttk.Frame | None = None
        self._box_filter: int | None = None
        self._box_bar: ttk.Frame | None = None
        self._box_btn_refs: dict[int | str, ttk.Button] = {}
        self._matrix_overview = False

        top = ttk.Frame(self, style=self._sf)
        top.pack(fill="x", padx=8, pady=(8, 4))
        title = "Filamenteinstellungen" if self._creality else "Filament"
        ttk.Label(top, text=title, style=self._sh).pack(side="left")
        self._cfs_summary_var = tk.StringVar(value="1 CFS am Drucker (1A–1D)")
        ttk.Label(top, textvariable=self._cfs_summary_var, style=self._sm).pack(
            side="left", padx=(12, 0)
        )
        self._on_preview_toggle = on_preview_toggle
        self._preview_btn = None
        if on_preview_toggle:
            self._preview_btn = tip(
                rounded_button(
                    top,
                    "4× CFS Demo",
                    on_preview_toggle,
                    variant="secondary",
                    compact=True,
                ),
                "Vier CFS-Einheiten nur zur Ansicht (ohne Drucker). Erneut klicken = aus.",
            )
            self._preview_btn.pack(side="right", padx=(0, 6))
        if on_batch_scan:
            tip(
                rounded_button(
                    top,
                    "Alle Slots",
                    on_batch_scan,
                    variant="secondary",
                    compact=True,
                ),
                "Übersicht aller CFS-Slots (1A–4D) mit verknüpften Spulen.",
            ).pack(side="right", padx=(0, 6))
        tip(
            ttk.Button(top, text="↻", width=3, command=on_refresh, style=self._sb),
            "CFS-Daten neu laden.",
        ).pack(side="right")

        if self._creality:
            self._build_creality_slots(on_adopt, on_bind_spool)
        else:
            self._build_grid_slots(on_adopt, on_bind_spool)

        foot = ttk.Frame(self, style=self._sf)
        foot.pack(fill="x", padx=8, pady=(4, 4))
        self._active_var = tk.StringVar(value="Aktiv: —")
        ttk.Label(foot, textvariable=self._active_var, style=self._sh).pack(
            anchor="w", fill="x", pady=(0, 2)
        )
        foot2 = ttk.Frame(self, style=self._sf)
        foot2.pack(fill="x", padx=8, pady=(0, 4))
        self._humidity_var = tk.StringVar(value="Feuchtigkeit: —")
        ttk.Label(foot2, textvariable=self._humidity_var, style=self._sm).pack(side="right")
        self._status_var = tk.StringVar(
            value="Slot wählen, dann Zufuhr oder Zurückziehen"
            if self._creality
            else "Slot wählen · → RFID übernimmt Material in den Editor"
        )
        ttk.Label(foot2, textvariable=self._status_var, style=self._sm, wraplength=480).pack(
            side="left", fill="x", expand=True
        )
        if not self._creality:
            ttk.Label(
                foot,
                text="Oranger Rahmen = Filament im Einsatz",
                style=self._sm,
                wraplength=520,
            ).pack(anchor="w", fill="x", pady=(0, 4))

        btn_bg = self._card_bg if self._printer else CARD
        btns = tk.Frame(self, bg=btn_bg)
        btns.pack(fill="x", padx=8, pady=(4, 10))
        cfs_font = ("Segoe UI", 10, "bold")
        self._feed_btn = tip(
            rounded_button(btns, "Zufuhr", self._feed, variant="accent", font=cfs_font),
            "Filament in den Drucker laden.",
        )
        self._feed_btn.pack(side="left", padx=(0, 8))
        self._retract_btn = tip(
            rounded_button(btns, "Zurückziehen", self._retract, variant="secondary", font=cfs_font),
            "Filament zurückziehen.",
        )
        self._retract_btn.pack(side="left")
        self._feed_btn.config(state="disabled")
        self._retract_btn.config(state="disabled")

        if self._creality:
            hint_style = "Printer.Hint.TLabel" if self._printer else self._sm
            hint = ttk.Label(
                self,
                text="Wählen Sie einen Slot und klicken Sie auf „Zufuhr“ / „Zurückziehen“",
                style=hint_style,
            )
            hint.pack(anchor="w", padx=12, pady=(0, 6))

    def _build_grid_slots(
        self,
        on_adopt: Callable[[int], None],
        on_bind: Callable[[int], None] | None,
    ) -> None:
        grid = ttk.Frame(self, style=self._sf)
        grid.pack(fill="both", expand=True, padx=8, pady=4)
        grid.columnconfigure(0, weight=0)
        grid.columnconfigure(1, weight=1)

        ext_box = ttk.LabelFrame(grid, text="  Spulenhalter  ", padding=6)
        ext_box.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=4)
        self._ext_swatch = tk.Label(
            ext_box,
            width=4,
            height=2,
            relief="solid",
            borderwidth=1,
            bg=self._border,
            text="?",
            fg=P_MUTED if self._printer else MUTED,
            font=("Segoe UI", 14),
        )
        self._ext_swatch.pack(pady=(4, 6))
        self._ext_type = ttk.Label(ext_box, text="—", style=self._sm)
        self._ext_type.pack()

        cfs_box = ttk.LabelFrame(grid, text="  CFS  ", padding=8)
        cfs_box.grid(row=0, column=1, sticky="nsew", pady=4)
        self._slots_area = ttk.Frame(cfs_box, style=self._sf)
        self._slots_area.pack(fill="both", expand=True)
        self._on_adopt_cb = on_adopt
        self._on_bind_cb = on_bind
        self._rebuild_slot_grid([])

    def _build_creality_slots(
        self,
        on_adopt: Callable[[int], None],
        on_bind: Callable[[int], None] | None,
    ) -> None:
        row = ttk.Frame(self, style=self._sf)
        row.pack(fill="both", expand=True, padx=8, pady=6)

        ext_box = ttk.LabelFrame(row, text="  Spulenhalter  ", padding=8, style=self._lf)
        ext_box.pack(side="left", fill="y", padx=(0, 10))
        self._ext_swatch = tk.Label(
            ext_box,
            width=5,
            height=4,
            relief="flat",
            borderwidth=0,
            bg=self._border,
            text="?",
            fg=P_MUTED,
            font=("Segoe UI", 16),
        )
        self._ext_swatch.pack(pady=8, padx=8)
        self._ext_type = ttk.Label(ext_box, text="—", style=self._sm)
        self._ext_type.pack(pady=(0, 8))

        cfs_col = ttk.Frame(row, style=self._sf)
        cfs_col.pack(side="left", fill="both", expand=True)
        self._box_bar = ttk.Frame(cfs_col, style=self._sf)
        self._box_bar.pack_forget()

        self._scroll_wrap = ttk.Frame(cfs_col, style=self._sf)
        self._scroll_wrap.pack(fill="both", expand=True)
        canvas_bg = self._card_bg
        self._slots_canvas = tk.Canvas(
            self._scroll_wrap, highlightthickness=0, bg=canvas_bg, height=300
        )
        self._slots_scroll = ttk.Scrollbar(
            self._scroll_wrap, orient="vertical", command=self._slots_canvas.yview
        )
        self._slots_area = ttk.Frame(self._slots_canvas, style=self._sf)
        self._slots_window_id = self._slots_canvas.create_window(
            (0, 0), window=self._slots_area, anchor="nw"
        )
        self._slots_hscroll = ttk.Scrollbar(
            self._scroll_wrap, orient="horizontal", command=self._slots_canvas.xview
        )
        self._slots_canvas.configure(
            yscrollcommand=self._slots_scroll.set,
            xscrollcommand=self._slots_hscroll.set,
        )
        self._slots_canvas.pack(side="left", fill="both", expand=True)
        self._slots_scroll.pack_forget()
        self._slots_hscroll.pack_forget()

        def _on_slots_configure(_event: tk.Event | None = None) -> None:
            self._slots_canvas.configure(scrollregion=self._slots_canvas.bbox("all"))
            if self._matrix_overview:
                req = max(self._slots_area.winfo_reqwidth(), 1)
                self._slots_canvas.itemconfigure(self._slots_window_id, width=req)
                return
            cw = max(int(self._scroll_wrap.winfo_width() or 0), 1)
            self._slots_canvas.itemconfigure(self._slots_window_id, width=cw)

        self._slots_area.bind("<Configure>", _on_slots_configure)
        self._scroll_wrap.bind("<Configure>", lambda _e: _on_slots_configure())

        self._on_adopt_cb = on_adopt
        self._on_bind_cb = on_bind
        self._rebuild_slot_grid([])

    def set_inventory(self, inventory) -> None:
        self._inventory = inventory

    def set_mode_hint(self, text: str) -> None:
        if hasattr(self, "_cfs_summary_var"):
            self._cfs_summary_var.set(text)

    def set_preview_active(self, active: bool) -> None:
        if self._preview_btn is not None:
            self._preview_btn.config(text="Demo beenden" if active else "4× CFS Demo")

    def _sync_scroll_visibility(self, box_count: int, *, matrix_overview: bool = False) -> None:
        if not hasattr(self, "_slots_scroll"):
            return
        self._matrix_overview = matrix_overview
        self._slots_hscroll.pack_forget()
        if box_count <= 1:
            self._slots_scroll.pack_forget()
            self._slots_canvas.configure(height=210)
        elif matrix_overview:
            if not self._slots_scroll.winfo_ismapped():
                self._slots_scroll.pack(side="right", fill="y")
            self._slots_canvas.configure(height=268)
            self._slots_area.update_idletasks()
            req_w = self._slots_area.winfo_reqwidth()
            view_w = self._scroll_wrap.winfo_width() or 0
            if req_w > view_w + 8 and view_w > 1:
                if not self._slots_hscroll.winfo_ismapped():
                    self._slots_hscroll.pack(side="bottom", fill="x")
            else:
                self._slots_hscroll.pack_forget()
        else:
            if not self._slots_scroll.winfo_ismapped():
                self._slots_scroll.pack(side="right", fill="y")
            self._slots_canvas.configure(height=320)

    def _set_box_filter(self, box_id: int | None) -> None:
        self._box_filter = box_id
        self._layout_sig = ()
        self._rebuild_slot_grid(self._slots)
        self._sync_box_bar_buttons()

    def _sync_box_bar(self, box_ids: list[int]) -> None:
        if self._box_bar is None:
            return
        for w in self._box_bar.winfo_children():
            w.destroy()
        self._box_btn_refs.clear()
        if len(box_ids) <= 1:
            self._box_bar.pack_forget()
            self._box_filter = None
            return
        self._box_bar.pack(fill="x", pady=(0, 6), before=self._scroll_wrap)
        ttk.Label(self._box_bar, text="CFS:", style=self._sm).pack(side="left", padx=(0, 6))

        def add_btn(label: str, bid: int | None) -> None:
            b = ttk.Button(
                self._box_bar,
                text=label,
                width=4,
                command=lambda x=bid: self._set_box_filter(x),
                style=self._sb,
            )
            b.pack(side="left", padx=(0, 4))
            self._box_btn_refs[label] = b

        add_btn("Alle", None)
        for bid in box_ids:
            add_btn(str(bid), bid)
        self._sync_box_bar_buttons()

    def _sync_box_bar_buttons(self) -> None:
        for key, btn in self._box_btn_refs.items():
            if key == "Alle":
                active = self._box_filter is None
            else:
                try:
                    active = self._box_filter == int(key)
                except ValueError:
                    active = False
            btn.state(["pressed"] if active else ["!pressed"])

    def _layout_signature(self, slots: list[CfsSlotInfo]) -> tuple[tuple[int, int], ...]:
        return tuple(
            (getattr(s, "box_id", 1) or 1, s.index) for s in slots
        )

    def _rebuild_slot_grid(self, slots: list[CfsSlotInfo]) -> None:
        """Slot-Zellen neu aufbauen (1–4 CFS × 4 Slots)."""
        if self._slots_area is None:
            return
        sig = (self._layout_signature(slots), self._box_filter)
        if sig == self._layout_sig and len(self._slot_frames) == len(slots) and slots:
            return
        self._layout_sig = sig
        for child in self._slots_area.winfo_children():
            child.destroy()
        self._slot_frames = []
        self._slot_swatches = []
        self._slot_labels = []
        self._slot_types = []
        self._slot_inv = []
        if not slots:
            slots = [
                CfsSlotInfo(
                    index=i,
                    label=SLOT_LABELS[i],
                    vendor="",
                    name="",
                    material_type="",
                    color_raw="",
                    color_hex="FFFFFF",
                    percent=None,
                    rfid_id="",
                    empty=True,
                    box_id=1,
                )
                for i in range(4)
            ]
        from collections import defaultdict

        by_box: dict[int, list[tuple[int, CfsSlotInfo]]] = defaultdict(list)
        for flat_i, slot in enumerate(slots):
            by_box[getattr(slot, "box_id", 1) or 1].append((flat_i, slot))
        box_ids = sorted(by_box.keys())
        self._sync_box_bar(box_ids)
        show_ids = box_ids
        if self._box_filter is not None:
            show_ids = [b for b in box_ids if b == self._box_filter]
        multi = len(box_ids) > 1
        host = self._slots_area
        compact = multi
        if multi and self._box_filter is None:
            self._box_bar.pack_forget()
            host.columnconfigure(0, weight=0)
            for c in range(1, 5):
                host.columnconfigure(c, weight=1, uniform="cfs_slot")
            row_num = 0
            ttk.Label(host, text="", style=self._sm).grid(row=row_num, column=0)
            for col_i, letter in enumerate(("A", "B", "C", "D"), start=1):
                ttk.Label(host, text=letter, style=self._sm).grid(
                    row=row_num, column=col_i, sticky="n", pady=(0, 2)
                )
            row_num += 1
            for box_id in show_ids:
                ttk.Label(host, text=f"CFS {box_id}", style=self._sm).grid(
                    row=row_num, column=0, sticky="e", padx=(4, 6), pady=2
                )
                box_row = ttk.Frame(host, style=self._sf)
                box_row.grid(row=row_num, column=1, columnspan=4, sticky="ew", padx=2, pady=1)
                for c in range(4):
                    box_row.columnconfigure(c, weight=1)
                items = sorted(by_box[box_id], key=lambda x: x[1].index)
                cells = self._make_slot_cells(
                    box_row,
                    self._on_adopt_cb,
                    self._on_bind_cb,
                    grid_cols=4,
                    parent_is_row=True,
                    slot_indices=[fi for fi, _ in items],
                    slot_labels=[s.label for _, s in items],
                    compact=True,
                    ultra_compact=True,
                )
                self._slot_frames.extend(cells[0])
                self._slot_swatches.extend(cells[1])
                self._slot_labels.extend(cells[2])
                self._slot_types.extend(cells[3])
                self._slot_inv.extend(cells[4])
                row_num += 1
        else:
            row_num = 0
            host.columnconfigure(0, weight=1)
            for box_id in show_ids:
                if multi:
                    hdr = ttk.Label(host, text=f"CFS {box_id}", style=self._sh)
                    hdr.grid(row=row_num, column=0, columnspan=4, sticky="w", padx=8, pady=(4, 0))
                    row_num += 1
                box_row = ttk.Frame(host, style=self._sf)
                box_row.grid(row=row_num, column=0, columnspan=4, sticky="ew", padx=4, pady=2)
                host.rowconfigure(row_num, weight=0)
                row_num += 1
                for c in range(4):
                    box_row.columnconfigure(c, weight=1)
                items = sorted(by_box[box_id], key=lambda x: x[1].index)
                cells = self._make_slot_cells(
                    box_row,
                    self._on_adopt_cb,
                    self._on_bind_cb,
                    grid_cols=4,
                    parent_is_row=True,
                    slot_indices=[fi for fi, _ in items],
                    slot_labels=[s.label for _, s in items],
                    compact=compact,
                )
                self._slot_frames.extend(cells[0])
                self._slot_swatches.extend(cells[1])
                self._slot_labels.extend(cells[2])
                self._slot_types.extend(cells[3])
                self._slot_inv.extend(cells[4])
        matrix = multi and self._box_filter is None
        self._sync_scroll_visibility(len(box_ids), matrix_overview=matrix)
        if hasattr(self, "_slots_canvas"):
            self._slots_area.update_idletasks()
            self._slots_canvas.configure(scrollregion=self._slots_canvas.bbox("all"))
            if matrix:
                self.after_idle(
                    lambda: self._sync_scroll_visibility(len(box_ids), matrix_overview=True)
                )

    def _make_slot_cells(
        self,
        parent: tk.Misc,
        on_adopt: Callable[[int], None],
        on_bind: Callable[[int], None] | None,
        *,
        grid_cols: int,
        parent_is_row: bool = False,
        slot_indices: list[int] | None = None,
        slot_labels: list[str] | None = None,
        compact: bool = False,
        ultra_compact: bool = False,
    ) -> tuple[list[tk.Frame], list[tk.Label], list[ttk.Label], list[ttk.Label], list[ttk.Label]]:
        frames: list[tk.Frame] = []
        swatches: list[tk.Label] = []
        labels: list[ttk.Label] = []
        types: list[ttk.Label] = []
        invs: list[ttk.Label] = []
        if ultra_compact:
            px = 18
            cell_pad = 1
        elif compact:
            px = 22
            cell_pad = 2
        else:
            px = max(40, self._swatch_px)
            cell_pad = 8
        grid_pad = 2 if ultra_compact else (4 if compact else 6)
        indices = slot_indices if slot_indices is not None else list(range(4))
        captions = slot_labels if slot_labels is not None else [
            SLOT_LABELS[i] if i < 4 else f"S{i + 1}" for i in indices
        ]

        for col, flat_i in enumerate(indices):
            cap = captions[col] if col < len(captions) else SLOT_LABELS[flat_i % 4]
            r, c = divmod(col, grid_cols)
            cell = tk.Frame(
                parent,
                bg=self._card_bg,
                padx=cell_pad,
                pady=cell_pad,
                highlightthickness=2,
                highlightbackground=self._card_bg,
            )
            if parent_is_row:
                cell.grid(row=0, column=col, padx=grid_pad, pady=grid_pad, sticky="nsew")
            else:
                cell.grid(row=r, column=c, padx=grid_pad, pady=grid_pad, sticky="nsew")
            cell.bind("<Button-1>", lambda _e, idx=flat_i: self._select(idx))

            sw = tk.Label(
                cell,
                width=max(4, px // 12),
                height=max(2, px // 28),
                relief="flat",
                borderwidth=0,
                bg=self._border,
                cursor="hand2",
            )
            sw.pack(pady=(2, 2) if ultra_compact else (4, 6))
            sw.bind("<Button-1>", lambda _e, idx=flat_i: self._select(idx))

            lb_style = self._sm if ultra_compact else self._sh
            lb = ttk.Label(cell, text=cap, style=lb_style, cursor="hand2")
            lb.pack()
            lb.bind("<Button-1>", lambda _e, idx=flat_i: self._select(idx))

            ty = ttk.Label(cell, text="—", style=self._sm, cursor="hand2")
            ty.pack(pady=(0, 0) if ultra_compact else ((1, 1) if compact else (2, 2)))
            ty.bind("<Button-1>", lambda _e, idx=flat_i: self._select(idx))

            inv_wrap = 48 if ultra_compact else (56 if compact else 72)
            inv = ttk.Label(
                cell, text="", style=self._sm, cursor="hand2", wraplength=inv_wrap
            )
            if not ultra_compact:
                inv.pack(pady=(0, 1 if compact else 2))
                inv.bind("<Button-1>", lambda _e, idx=flat_i: self._select(idx))

            if not ultra_compact:
                btn_row = ttk.Frame(cell, style=self._sf)
                btn_row.pack(pady=(0, 1 if compact else 2))
                adopt_lbl = "RF" if compact else ("RFID" if self._creality else "→ RFID")
                adopt = tip(
                    rounded_button(
                        btn_row,
                        adopt_lbl,
                        lambda idx=flat_i: on_adopt(idx),
                        variant="secondary",
                        compact=True,
                    ),
                    "Material in RFID-Tab übernehmen.",
                )
                adopt.pack(side="left", padx=(0, 2 if compact else 4))
                adopt.config(state="disabled")
                setattr(cell, "_adopt_btn", adopt)
                if on_bind:
                    bind_btn = tip(
                        rounded_button(
                            btn_row,
                            "Spule" if not compact else "Sp",
                            lambda idx=flat_i: on_bind(idx),
                            variant="secondary",
                            compact=True,
                        ),
                        "Mit „Meine Spulen“ verknüpfen.",
                    )
                    bind_btn.pack(side="left")
                    bind_btn.config(state="disabled")
                    setattr(cell, "_bind_btn", bind_btn)
            frames.append(cell)
            swatches.append(sw)
            labels.append(lb)
            types.append(ty)
            invs.append(inv)

        return frames, swatches, labels, types, invs

    def _select(self, index: int) -> None:
        self._selected = index
        self._paint_selection()
        slot = self._slots[index] if 0 <= index < len(self._slots) else None
        if slot and not slot.empty:
            self._status_var.set(f"{slot.label}: {slot.display}")
            self._feed_btn.config(state="normal")
            self._retract_btn.config(state="normal")
        else:
            lab = SLOT_LABELS[index] if index < 4 else f"Slot {index + 1}"
            if 0 <= index < len(self._slots):
                lab = self._slots[index].label
            self._status_var.set(f"{lab}: leer — Spule einlegen")
            self._feed_btn.config(state="disabled")
            self._retract_btn.config(state="disabled")

    def _in_use_index(self) -> int | None:
        if self._printer_feeding is not None:
            if 0 <= self._printer_feeding < len(self._slots) and not self._slots[
                self._printer_feeding
            ].empty:
                return self._printer_feeding
        if self._printer_active is not None:
            if 0 <= self._printer_active < len(self._slots) and not self._slots[
                self._printer_active
            ].empty:
                return self._printer_active
        return None

    def _paint_selection(self) -> None:
        in_use = self._in_use_index()
        sel = self._selected
        for i, frame in enumerate(self._slot_frames):
            slot_empty = i < len(self._slots) and self._slots[i].empty
            if slot_empty:
                frame.configure(highlightbackground=self._card_bg, highlightthickness=2)
            elif i == in_use:
                frame.configure(highlightbackground=self._warn, highlightthickness=3)
            elif i == sel:
                frame.configure(highlightbackground=P_BORDER if self._printer else BORDER, highlightthickness=3)
            else:
                frame.configure(highlightbackground=self._card_bg, highlightthickness=2)

    def _feed(self) -> None:
        if self._on_feed:
            self._on_feed()

    def _retract(self) -> None:
        if self._on_retract:
            self._on_retract()

    def update_from_state(
        self,
        state: dict,
        *,
        slots: list[CfsSlotInfo] | None = None,
    ) -> None:
        if slots is not None:
            self._slots = list(slots)
        else:
            self._slots = parse_cfs_layout(state).all_slots()
        self._rebuild_slot_grid(self._slots)
        meta = parse_cfs_meta(state)
        active_flat = None
        if meta.loaded_index is not None:
            active_flat = flat_slot_index(
                self._slots,
                meta.loaded_box_id or 1,
                meta.loaded_index,
            )
        if active_flat is None and meta.feeding_index is not None:
            active_flat = flat_slot_index(
                self._slots,
                meta.feeding_box_id or 1,
                meta.feeding_index,
            )
        self._printer_active = active_flat
        feeding_flat = None
        if meta.feeding_index is not None:
            feeding_flat = flat_slot_index(
                self._slots,
                meta.feeding_box_id or 1,
                meta.feeding_index,
            )
        self._printer_feeding = feeding_flat

        in_use = feeding_flat if feeding_flat is not None else active_flat
        if (
            in_use is not None
            and 0 <= in_use < len(self._slots)
            and not self._slots[in_use].empty
        ):
            self._active_var.set(f"Im Einsatz: {active_slot_label(self._slots, in_use)}")
        else:
            self._active_var.set("Im Einsatz: —")

        ext = meta.external
        border = P_BORDER if self._printer else BORDER
        if ext and not ext.empty:
            hx = creality_color_to_hex(ext.color_raw) or P_CARD_ALT
            self._ext_swatch.config(bg=hx, text="")
            self._ext_type.config(text=ext.material_type or ext.name or "—")
        else:
            self._ext_swatch.config(bg=border, text="?")
            self._ext_type.config(text="—")

        for i in range(min(len(self._slots), len(self._slot_frames))):
            slot = self._slots[i]
            sw = self._slot_swatches[i]
            ty = self._slot_types[i]
            inv_lbl = self._slot_inv[i]
            lbl = self._slot_labels[i]
            lbl.config(text=slot.label)
            btn = getattr(self._slot_frames[i], "_adopt_btn", None)
            bind_btn = getattr(self._slot_frames[i], "_bind_btn", None)
            if slot.empty:
                sw.config(bg=border)
                ty.config(text="—")
                inv_lbl.config(text="")
                if btn:
                    btn.config(state="disabled")
                if bind_btn:
                    bind_btn.config(state="disabled")
            else:
                hx = creality_color_to_hex(slot.color_raw) or P_CARD_ALT
                sw.config(bg=hx)
                label = slot.material_type or slot.name or "—"
                ty.config(text=label.upper()[:16])
                if btn:
                    btn.config(state="normal")
                if bind_btn:
                    bind_btn.config(state="normal")
                inv_text = ""
                if self._inventory is not None:
                    sp = find_spool_for_slot(self._inventory, slot)
                    if sp:
                        rest = f" · {sp.remaining_g}g" if sp.remaining_g is not None else ""
                        inv_text = f"📦 {sp.label[:18]}{rest}"
                    else:
                        inv_text = "— nicht zugewiesen"
                inv_lbl.config(text=inv_text)

        if meta.humidity is not None:
            self._humidity_var.set(f"Feuchtigkeit: {meta.humidity} %")
        else:
            self._humidity_var.set("Feuchtigkeit: —")

        self._paint_selection()
        if self._selected is not None and 0 <= self._selected < len(self._slots):
            slot = self._slots[self._selected]
            if not slot.empty:
                self._status_var.set(f"Gewählt {slot.label}: {slot.display}")
            else:
                self._status_var.set(f"{slot.label}: leer")
