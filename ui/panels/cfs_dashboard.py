"""CFS-Live-Ansicht (Creality-Print-Stil)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Literal

from creality_nfc.cfs_adopt import CfsSlotInfo, SLOT_LABELS, parse_cfs_meta, parse_cfs_slots
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

        top = ttk.Frame(self, style=self._sf)
        top.pack(fill="x", padx=8, pady=(8, 4))
        title = "Filamenteinstellungen" if self._creality else "Filament"
        ttk.Label(top, text=title, style=self._sh).pack(side="left")
        if on_batch_scan:
            tip(
                rounded_button(
                    top,
                    "Alle Slots",
                    on_batch_scan,
                    variant="secondary",
                    compact=True,
                ),
                "Übersicht 1A–1D mit verknüpften Spulen.",
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
        self._slot_frames, self._slot_swatches, self._slot_labels, self._slot_types, self._slot_inv = (
            self._make_slot_cells(cfs_box, on_adopt, on_bind, grid_cols=2)
        )

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

        slots_row = ttk.Frame(row, style=self._sf)
        slots_row.pack(side="left", fill="both", expand=True)
        for c in range(4):
            slots_row.columnconfigure(c, weight=1)
        self._slot_frames, self._slot_swatches, self._slot_labels, self._slot_types, self._slot_inv = (
            self._make_slot_cells(slots_row, on_adopt, on_bind, grid_cols=4, parent_is_row=True)
        )

    def set_inventory(self, inventory) -> None:
        self._inventory = inventory

    def _make_slot_cells(
        self,
        parent: tk.Misc,
        on_adopt: Callable[[int], None],
        on_bind: Callable[[int], None] | None,
        *,
        grid_cols: int,
        parent_is_row: bool = False,
    ) -> tuple[list[tk.Frame], list[tk.Label], list[ttk.Label], list[ttk.Label], list[ttk.Label]]:
        frames: list[tk.Frame] = []
        swatches: list[tk.Label] = []
        labels: list[ttk.Label] = []
        types: list[ttk.Label] = []
        invs: list[ttk.Label] = []
        px = max(40, self._swatch_px)

        for i in range(4):
            r, c = divmod(i, grid_cols)
            cell = tk.Frame(
                parent,
                bg=self._card_bg,
                padx=8,
                pady=8,
                highlightthickness=2,
                highlightbackground=self._card_bg,
            )
            if parent_is_row:
                cell.grid(row=0, column=i, padx=6, pady=4, sticky="nsew")
            else:
                cell.grid(row=r, column=c, padx=6, pady=6, sticky="nsew")
            cell.bind("<Button-1>", lambda _e, idx=i: self._select(idx))

            sw = tk.Label(
                cell,
                width=max(4, px // 12),
                height=max(2, px // 28),
                relief="flat",
                borderwidth=0,
                bg=self._border,
                cursor="hand2",
            )
            sw.pack(pady=(4, 6))
            sw.bind("<Button-1>", lambda _e, idx=i: self._select(idx))

            lb = ttk.Label(cell, text=SLOT_LABELS[i], style=self._sh, cursor="hand2")
            lb.pack()
            lb.bind("<Button-1>", lambda _e, idx=i: self._select(idx))

            ty = ttk.Label(cell, text="—", style=self._sm, cursor="hand2")
            ty.pack(pady=(2, 2))
            ty.bind("<Button-1>", lambda _e, idx=i: self._select(idx))

            inv = ttk.Label(cell, text="", style=self._sm, cursor="hand2", wraplength=72)
            inv.pack(pady=(0, 2))
            inv.bind("<Button-1>", lambda _e, idx=i: self._select(idx))

            adopt = tip(
                rounded_button(
                    cell,
                    "RFID" if self._creality else "→ RFID",
                    lambda idx=i: on_adopt(idx),
                    variant="secondary",
                    compact=True,
                ),
                "Material in RFID-Tab übernehmen.",
            )
            adopt.pack(pady=(0, 2))
            adopt.config(state="disabled")
            setattr(cell, "_adopt_btn", adopt)
            if on_bind:
                bind_btn = tip(
                    rounded_button(
                        cell,
                        "Spule",
                        lambda idx=i: on_bind(idx),
                        variant="secondary",
                        compact=True,
                    ),
                    "Mit „Meine Spulen“ verknüpfen.",
                )
                bind_btn.pack(pady=(0, 2))
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
            self._status_var.set(f"{SLOT_LABELS[index]}: leer — Spule einlegen")
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

    def update_from_state(self, state: dict) -> None:
        self._slots = parse_cfs_slots(state)
        meta = parse_cfs_meta(state)
        self._printer_active = meta.loaded_index
        self._printer_feeding = meta.feeding_index

        in_use = meta.feeding_index
        if in_use is None:
            in_use = meta.loaded_index
        if in_use is not None and 0 <= in_use < len(self._slots) and not self._slots[in_use].empty:
            self._active_var.set(f"Im Einsatz: {SLOT_LABELS[in_use]}")
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

        for i, slot in enumerate(self._slots):
            sw = self._slot_swatches[i]
            ty = self._slot_types[i]
            inv_lbl = self._slot_inv[i]
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
        if self._selected is not None and 0 <= self._selected < 4:
            slot = self._slots[self._selected]
            if not slot.empty:
                self._status_var.set(f"Gewählt {slot.label}: {slot.display}")
            else:
                self._status_var.set(f"{SLOT_LABELS[self._selected]}: leer")
