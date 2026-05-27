"""Drucker-Tab: Unterseiten Monitor / Steuerung / Filament / Dateien."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from creality_nfc.i18n import t as _t
from creality_nfc.printer_control import PRINT_SPEED_PRESETS
from creality_nfc.printer_control import home_xy, home_z
from ui.components import button_grid
from ui.panels.cfs_dashboard import CfsDashboard
from ui.printer_tab_theme import P_BORDER, P_CARD_ALT, P_MUTED, style_listbox, style_scrollbar
from ui.rounded_widgets import rounded_button
from ui.theme import CARD, SURFACE_DARK
from ui.tooltip import tip

if TYPE_CHECKING:
    from ui.panels.printer_device_panel import PrinterDevicePanel

CAM_MIN_HEIGHT = 420

_SEC = "Printer.TLabelframe"
_BTN = "Printer.Secondary.TButton"
_ACC = "Printer.Accent.TButton"
_MUTED = "Printer.CardMuted.TLabel"
_BODY = "Printer.Card.TLabel"
_PROG = "Printer.Accent.Horizontal.TProgressbar"
_NB = "Printer.TNotebook"

def _speed_labels() -> dict[int, str]:
    return {
        25: _t("printer.speed.silent"),
        50: _t("printer.speed.stable"),
        100: _t("printer.speed.standard"),
        125: _t("printer.speed.ultra"),
    }


def _build_settings(panel: PrinterDevicePanel, parent: ttk.Frame) -> None:
    """Druckeinstellungen — 2 Spalten, ohne Scrollen."""
    parent.columnconfigure(0, weight=1)
    parent.columnconfigure(1, weight=1)

    left = ttk.Frame(parent, style="Printer.Card.TFrame")
    left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
    right = ttk.Frame(parent, style="Printer.Card.TFrame")
    right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

    temps = ttk.LabelFrame(left, text=_t("printer.section.temperatures"), padding=8, style=_SEC)
    temps.pack(fill="x", pady=(0, 8))
    tg = ttk.Frame(temps, style="Printer.Card.TFrame")
    tg.pack(fill="x")
    for col, (title, attr) in enumerate(
        (
            (_t("printer.temp.nozzle"), "nozzle_lbl"),
            (_t("printer.temp.bed"), "bed_lbl"),
            (_t("printer.temp.chamber"), "box_lbl"),
        )
    ):
        tg.columnconfigure(col, weight=1)
        cell = tk.Frame(tg, bg=SURFACE_DARK, padx=6, pady=8)
        cell.grid(row=0, column=col, sticky="nsew", padx=3)
        ttk.Label(cell, text=title, style="Printer.TempSub.TLabel").pack(anchor="w")
        lbl = ttk.Label(cell, text="— / — °C", style="Printer.Temp.TLabel")
        lbl.pack(anchor="w", pady=(2, 0))
        setattr(panel, attr, lbl)

    tgt = ttk.LabelFrame(left, text=_t("printer.section.target_temp"), padding=8, style=_SEC)
    tgt.pack(fill="x")
    panel.nozzle_tgt = tk.IntVar(value=0)
    panel.bed_tgt = tk.IntVar(value=0)
    panel.box_tgt = tk.IntVar(value=0)
    tg2 = ttk.Frame(tgt, style="Printer.Card.TFrame")
    tg2.pack(fill="x")
    for col, (lbl, var, cmd) in enumerate(
        (
            (_t("printer.temp.nozzle"), panel.nozzle_tgt, panel._apply_nozzle),
            (_t("printer.temp.bed"), panel.bed_tgt, panel._apply_bed),
            (_t("printer.temp.chamber"), panel.box_tgt, panel._apply_chamber),
        )
    ):
        tg2.columnconfigure(col, weight=1)
        f = ttk.Frame(tg2, style="Printer.Card.TFrame")
        f.grid(row=0, column=col, padx=4, sticky="ew")
        ttk.Label(f, text=f"{lbl} °C", style=_MUTED).pack(anchor="w")
        row = ttk.Frame(f, style="Printer.Card.TFrame")
        row.pack(fill="x", pady=2)
        spin = ttk.Spinbox(
            row, from_=0, to=300, textvariable=var, width=5, style="Printer.TSpinbox"
        )
        spin.pack(side="left")
        spin.bind("<FocusIn>", panel._on_temp_spin_focus)
        tip(
            rounded_button(row, _t("printer.btn.set"), cmd, variant="secondary", compact=True),
            _t("printer.tip.target_temp", label=lbl),
        ).pack(side="left", padx=4)

    led = ttk.LabelFrame(right, text=_t("printer.section.led_axes"), padding=8, style=_SEC)
    led.pack(fill="x", pady=(0, 8))
    panel.led_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(
        led, text=_t("printer.dashboard.led_on"), variable=panel.led_var, command=panel._toggle_led, style="Printer.TCheckbutton"
    ).pack(anchor="w", pady=(0, 6))
    button_grid(
        led,
        [
            (_t("printer.btn.light_on"), lambda: panel._set_light(True), _BTN, _t("printer.tip.led_on")),
            (_t("printer.btn.light_off"), lambda: panel._set_light(False), _BTN, _t("printer.tip.led_off")),
            (_t("printer.btn.home_xy"), lambda: panel._cmd("Home XY", home_xy), _BTN, _t("printer.tip.home_xy")),
            (_t("printer.btn.home_z"), lambda: panel._cmd("Home Z", home_z), _BTN, _t("printer.tip.home_z")),
        ],
        columns=2,
    ).pack(fill="x")

    fan_box = ttk.LabelFrame(right, text=_t("printer.section.fans"), padding=8, style=_SEC)
    fan_box.pack(fill="x", pady=(0, 8))
    panel.fan_vars = [tk.IntVar(value=0) for _ in range(3)]
    for i, name in enumerate(
        (_t("printer.fan.model"), _t("printer.fan.housing"), _t("printer.fan.side"))
    ):
        row = ttk.Frame(fan_box, style="Printer.Card.TFrame")
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=name, width=8, style=_BODY).pack(side="left")
        sc = ttk.Scale(
            row,
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            variable=panel.fan_vars[i],
            style="Horizontal.Printer.TScale",
        )
        sc.pack(side="left", fill="x", expand=True, padx=6)
        sc.bind("<ButtonPress-1>", lambda _e: panel._set_fan_drag(True))
        sc.bind("<ButtonRelease-1>", lambda _e: panel._set_fan_drag(False))
        tip(
            rounded_button(
                row,
                _t("printer.btn.set"),
                lambda ch=i: panel._apply_fan(ch),
                variant="secondary",
                compact=True,
            ),
            _t("printer.tip.fan", name=name),
        ).pack(side="left")

    spd = ttk.LabelFrame(right, text=_t("printer.section.print_speed"), padding=8, style=_SEC)
    spd.pack(fill="x")
    sr = ttk.Frame(spd, style="Printer.Card.TFrame")
    sr.pack(fill="x")
    for col, (pct, _label) in enumerate(PRINT_SPEED_PRESETS):
        sr.columnconfigure(col, weight=1)
        ttk.Radiobutton(
            sr,
            text=_speed_labels().get(pct, _label),
            value=pct,
            variable=panel._speed_var,
            command=lambda p=pct: panel._apply_speed_preset(p),
            style="Printer.TRadiobutton",
        ).grid(row=0, column=col, sticky="ew", padx=2, pady=2)


def _build_print_strip(panel: PrinterDevicePanel, parent: ttk.Frame) -> None:
    panel.print_file_var = tk.StringVar(value="—")
    panel.print_prog_var = tk.StringVar(value="—")
    panel.print_time_var = tk.StringVar(value="")
    panel._print_hint_var = tk.StringVar(value="")

    head = ttk.Frame(parent, style="Printer.Card.TFrame")
    head.pack(fill="x")
    ttk.Label(head, textvariable=panel.print_file_var, style="Printer.CardHeading.TLabel").pack(
        side="left", anchor="w"
    )
    ttk.Label(head, textvariable=panel.print_time_var, style=_MUTED).pack(side="right")

    panel._prog_bar = ttk.Progressbar(parent, maximum=100, mode="determinate", style=_PROG)
    panel._prog_bar.pack(fill="x", pady=6)

    mid = ttk.Frame(parent, style="Printer.Card.TFrame")
    mid.pack(fill="x")
    ttk.Label(mid, textvariable=panel.print_prog_var, style=_MUTED).pack(side="left")
    ttk.Label(mid, textvariable=panel._print_hint_var, style=_MUTED).pack(side="right")

    panel._filament_live_var = tk.StringVar(value="")
    ttk.Label(
        parent,
        textvariable=panel._filament_live_var,
        style=_MUTED,
        wraplength=560,
    ).pack(anchor="w", pady=(0, 4))

    hist_row = ttk.Frame(parent, style="Printer.TFrame")
    hist_row.pack(fill="x", pady=(0, 4))
    rounded_button(
        hist_row,
        _t("printer.btn.print_check"),
        panel.show_print_check,
        variant="secondary",
        compact=True,
    ).pack(side="left", padx=(0, 6))
    tip(hist_row, _t("printer.tip.print_check_running"))
    rounded_button(
        hist_row,
        _t("printer.btn.print_history"),
        panel.show_print_history,
        variant="secondary",
        compact=True,
    ).pack(side="left", padx=(0, 6))
    rounded_button(
        hist_row,
        _t("printer.btn.spool_location"),
        panel.show_spool_locations,
        variant="secondary",
        compact=True,
    ).pack(side="left")

    ctrl = tk.Frame(parent, bg=CARD)
    ctrl.pack(fill="x", pady=(6, 0))
    ttk.Label(
        ctrl,
        text=_t("printer.dashboard.start_creality"),
        style=_MUTED,
    ).pack(side="left", padx=(0, 12))
    panel._btn_pause = tip(
        rounded_button(ctrl, _t("printer.btn.pause"), panel._pause_print, variant="secondary"),
        _t("printer.tip.pause"),
    )
    panel._btn_pause.pack(side="left", padx=4)
    panel._btn_resume = tip(
        rounded_button(ctrl, _t("printer.btn.resume"), panel._resume_print, variant="secondary"),
        _t("printer.tip.resume"),
    )
    panel._btn_resume.pack(side="left", padx=4)
    tip(
        rounded_button(ctrl, _t("printer.btn.stop"), panel._stop_print, variant="danger"),
        _t("printer.tip.stop"),
    ).pack(side="left", padx=4)
    panel._btn_deduct = tip(
        rounded_button(
            ctrl,
            _t("printer.btn.deduct_consumption") + "\u2026",
            panel._manual_post_print_deduct,
            variant="secondary",
        ),
        _t("printer.tip.deduct"),
    )
    panel._btn_deduct.pack(side="right", padx=4)


def build_creality_dashboard(panel: PrinterDevicePanel, outer: ttk.Frame) -> None:
    """Unterseiten statt einer überfüllten Einzelseite."""

    conn = ttk.LabelFrame(outer, text=_t("printer.section.connection_pad"), padding=6, style=_SEC)
    conn.pack(fill="x", pady=(0, 6))
    panel.conn_var = tk.StringVar(value=_t("printer.conn.not_connected_hint"))
    ttk.Label(conn, textvariable=panel.conn_var, style=_MUTED).pack(anchor="w", pady=(0, 4))
    button_grid(
        conn,
        [
            (_t("printer.btn.connect"), panel.connect, _ACC, _t("printer.tip.websocket")),
            (_t("printer.btn.disconnect"), panel.disconnect, _BTN, _t("printer.tip.disconnect")),
            (_t("printer.btn.creality_webui"), panel._open_creality_web_ui, _BTN, _t("printer.tip.creality_webui")),
            (_t("printer.btn.klipper_webui"), panel.open_klipper_ui, _BTN, _t("printer.tip.klipper")),
        ],
        columns=4,
        pad=3,
    ).pack(fill="x")

    nb = ttk.Notebook(outer, style=_NB)
    nb.pack(fill="both", expand=True)
    panel._main_nb = nb
    nb.bind("<<NotebookTabChanged>>", lambda _e: panel.on_printer_subtab_shown())

    # —— Monitor: große Kamera + Druckstatus ——
    tab_mon = ttk.Frame(nb, padding=6, style="Printer.TFrame")
    tab_mon.rowconfigure(0, weight=1)
    tab_mon.rowconfigure(1, weight=0)
    tab_mon.columnconfigure(0, weight=1)
    nb.add(tab_mon, text=_t("printer.tab.monitor_pad"))

    cam_card = ttk.LabelFrame(tab_mon, text=_t("printer.section.camera_pad"), padding=4, style=_SEC)
    cam_card.grid(row=0, column=0, sticky="nsew", pady=(0, 6))

    panel._cam_preview_host = tk.Frame(
        cam_card,
        bg=P_CARD_ALT,
        highlightbackground=P_BORDER,
        highlightthickness=1,
        height=CAM_MIN_HEIGHT,
    )
    panel._cam_preview_host.pack(fill="both", expand=True, padx=4, pady=4)
    panel._cam_preview_host.pack_propagate(False)
    panel._preview_host = panel._cam_preview_host  # Kamera / WebRTC

    panel.cam_preview_label = tk.Label(
        panel._cam_preview_host,
        text=_t("printer.cam.connecting_msg"),
        anchor="center",
        bg=P_CARD_ALT,
        fg=P_MUTED,
        font=("Segoe UI", 11),
        wraplength=700,
    )
    panel.cam_preview_label.place(relx=0, rely=0, relwidth=1, relheight=1)
    panel.preview_label = panel.cam_preview_label

    cam_bar = tk.Frame(cam_card, bg=CARD)
    cam_bar.pack(fill="x", padx=4, pady=(0, 4))
    tip(
        rounded_button(cam_bar, _t("printer.btn.live_camera"), panel._toggle_live_camera, variant="accent"),
        _t("printer.tip.live_camera"),
    ).pack(side="left", padx=(0, 6))
    tip(
        rounded_button(cam_bar, _t("printer.btn.fullscreen"), panel._open_camera_fullscreen, variant="secondary"),
        _t("printer.tip.fullscreen"),
    ).pack(side="left")
    panel._cam_status_var = tk.StringVar(value="")
    ttk.Label(cam_bar, textvariable=panel._cam_status_var, style=_MUTED).pack(side="left", padx=10)

    print_card = ttk.LabelFrame(tab_mon, text=_t("printer.section.current_print_pad"), padding=8, style=_SEC)
    print_card.grid(row=1, column=0, sticky="ew")
    _build_print_strip(panel, print_card)

    # —— Steuerung ——
    tab_ctrl = ttk.Frame(nb, padding=8, style="Printer.TFrame")
    tab_ctrl.rowconfigure(0, weight=1)
    tab_ctrl.columnconfigure(0, weight=1)
    nb.add(tab_ctrl, text=_t("printer.tab.control_pad"))
    settings_wrap = ttk.Frame(tab_ctrl, style="Printer.TFrame")
    settings_wrap.pack(fill="both", expand=True)
    _build_settings(panel, settings_wrap)

    # —— Filament ——
    tab_fil = ttk.Frame(nb, padding=4, style="Printer.TFrame")
    nb.add(tab_fil, text=_t("printer.tab.filament_pad"))
    panel.cfs_dashboard = CfsDashboard(
        tab_fil,
        appearance="printer",
        layout="creality",
        on_adopt=panel._adopt_cfs_slot,
        on_refresh=panel._refresh_cfs,
        on_feed=panel._cfs_feed,
        on_retract=panel._cfs_retract,
        on_bind_spool=panel._bind_cfs_spool_slot,
        on_batch_scan=panel.show_cfs_batch_scan,
        on_preview_toggle=panel._toggle_cfs_preview_from_tab,
        inventory=panel.app.inventory,
    )
    panel.cfs_dashboard.pack(fill="both", expand=True)

    # —— Dateien: Liste links, G-Code-Vorschau rechts ——
    tab_files = ttk.Frame(nb, padding=8, style="Printer.TFrame")
    tab_files.rowconfigure(1, weight=1)
    tab_files.columnconfigure(0, weight=2)
    tab_files.columnconfigure(1, weight=3)
    nb.add(tab_files, text=_t("printer.tab.files_pad"))

    panel._status_var = tk.StringVar(value=_t("printer.label.not_connected"))
    ttk.Label(tab_files, textvariable=panel._status_var, style=_MUTED).grid(
        row=0, column=0, columnspan=2, sticky="w", pady=(0, 4)
    )

    list_card = ttk.LabelFrame(tab_files, text=_t("printer.files.gcode_on_printer"), padding=4, style=_SEC)
    list_card.grid(row=1, column=0, sticky="nsew", padx=(0, 6))
    list_card.rowconfigure(0, weight=1)
    list_card.columnconfigure(0, weight=1)
    list_frame = ttk.Frame(list_card, style="Printer.TFrame")
    list_frame.grid(row=0, column=0, sticky="nsew")
    scroll_files = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
    style_scrollbar(scroll_files)
    panel.file_list = tk.Listbox(
        list_frame,
        height=16,
        yscrollcommand=scroll_files.set,
        exportselection=False,
        font=("Segoe UI", 10),
        activestyle="none",
    )
    style_listbox(panel.file_list)
    scroll_files.config(command=panel.file_list.yview)
    panel.file_list.pack(side="left", fill="both", expand=True)
    scroll_files.pack(side="right", fill="y")
    panel.file_list.bind("<<ListboxSelect>>", panel._on_gcode_select)

    prev_card = ttk.LabelFrame(tab_files, text=_t("printer.files.preview"), padding=4, style=_SEC)
    prev_card.grid(row=1, column=1, sticky="nsew")
    prev_card.rowconfigure(0, weight=1)
    prev_card.columnconfigure(0, weight=1)
    panel._gcode_prev_nb = ttk.Notebook(prev_card, style=_NB)
    panel._gcode_prev_nb.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)

    tab_thumb = ttk.Frame(panel._gcode_prev_nb, style="Printer.TFrame")
    tab_gcode = ttk.Frame(panel._gcode_prev_nb, style="Printer.TFrame")
    tab_thumb.rowconfigure(0, weight=1)
    tab_thumb.columnconfigure(0, weight=1)
    tab_gcode.rowconfigure(0, weight=1)
    tab_gcode.columnconfigure(0, weight=1)
    panel._gcode_prev_nb.add(tab_thumb, text=_t("printer.files.image"))
    panel._gcode_prev_nb.add(tab_gcode, text=_t("printer.files.gcode"))

    panel._gcode_preview_host = tk.Frame(
        tab_thumb,
        bg=P_CARD_ALT,
        highlightbackground=P_BORDER,
        highlightthickness=1,
        width=380,
        height=140,
    )
    panel._gcode_preview_host.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
    panel._gcode_preview_host.grid_propagate(False)
    panel._gcode_preview_host.bind("<Configure>", lambda _e: panel._on_gcode_preview_resize())

    panel.gcode_preview_label = tk.Label(
        panel._gcode_preview_host,
        text=_t("printer.files.choose_file"),
        anchor="center",
        bg=P_CARD_ALT,
        fg=P_MUTED,
        font=("Segoe UI", 10),
        wraplength=340,
        justify="center",
    )
    panel.gcode_preview_label.place(relx=0, rely=0, relwidth=1, relheight=1)

    from ui.theme import apply_text_area_style

    gcode_txt_frame = ttk.Frame(tab_gcode, style="Printer.TFrame")
    gcode_txt_frame.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
    gcode_txt_frame.rowconfigure(2, weight=1)
    gcode_txt_frame.columnconfigure(0, weight=1)
    panel._gcode_text_status = tk.StringVar(value=_t("printer.files.choose_file_help"))
    ttk.Label(gcode_txt_frame, textvariable=panel._gcode_text_status, style=_MUTED).grid(
        row=0, column=0, sticky="ew", pady=(0, 2)
    )
    gcode_hdr = ttk.Frame(gcode_txt_frame, style="Printer.TFrame")
    gcode_hdr.grid(row=1, column=0, sticky="ew", pady=(0, 2))
    gcode_hdr.columnconfigure(0, weight=3)
    gcode_hdr.columnconfigure(1, weight=2)
    ttk.Label(gcode_hdr, text=_t("printer.gcode.col_gcode"), style=_BODY).grid(row=0, column=0, sticky="w")
    ttk.Label(gcode_hdr, text=_t("printer.gcode.col_what"), style=_BODY).grid(
        row=0, column=1, sticky="w", padx=(8, 0)
    )
    txt_wrap = ttk.Frame(gcode_txt_frame, style="Printer.TFrame")
    txt_wrap.grid(row=2, column=0, sticky="nsew")
    txt_wrap.rowconfigure(0, weight=1)
    txt_wrap.columnconfigure(0, weight=3)
    txt_wrap.columnconfigure(1, weight=2)
    scroll_gcode = ttk.Scrollbar(txt_wrap, orient=tk.VERTICAL)
    style_scrollbar(scroll_gcode)

    def _gcode_yscroll_sync(first: str, last: str) -> None:
        scroll_gcode.set(first, last)
        panel._sync_gcode_hint_to_gcode()

    def _gcode_scroll_both(*args: object) -> None:
        panel.gcode_text.yview(*args)
        panel._sync_gcode_hint_to_gcode()

    def _gcode_wheel(event: tk.Event) -> str:
        if event.delta:
            panel.gcode_text.yview_scroll(int(-1 * (event.delta / 120)), "units")
        elif getattr(event, "num", None) == 4:
            panel.gcode_text.yview_scroll(-3, "units")
        elif getattr(event, "num", None) == 5:
            panel.gcode_text.yview_scroll(3, "units")
        panel._sync_gcode_hint_to_gcode()
        return "break"

    scroll_gcode.config(command=_gcode_scroll_both)
    panel.gcode_text = tk.Text(
        txt_wrap,
        height=22,
        wrap="none",
        font=("Consolas", 9),
        undo=True,
        yscrollcommand=_gcode_yscroll_sync,
    )
    apply_text_area_style(panel.gcode_text, bg=P_CARD_ALT)
    panel.gcode_text.grid(row=0, column=0, sticky="nsew")
    panel.gcode_text.bind("<Button-1>", panel._gcode_on_click)
    panel.gcode_hint_text = tk.Text(
        txt_wrap,
        height=22,
        wrap="none",
        font=("Consolas", 9),
        state="disabled",
        cursor="arrow",
    )
    apply_text_area_style(panel.gcode_hint_text, bg=SURFACE_DARK)
    panel.gcode_hint_text.configure(fg=P_MUTED)
    panel.gcode_hint_text.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
    scroll_gcode.grid(row=0, column=2, sticky="ns")
    panel.gcode_text.insert("1.0", _t("printer.gcode.placeholder"))
    panel.gcode_hint_text.config(state="normal")
    panel.gcode_hint_text.insert("1.0", _t("printer.gcode.hint_panel"))
    panel.gcode_hint_text.config(state="disabled")
    for _w in (txt_wrap, panel.gcode_text, panel.gcode_hint_text):
        _w.bind("<MouseWheel>", _gcode_wheel)
        _w.bind("<Button-4>", _gcode_wheel)
        _w.bind("<Button-5>", _gcode_wheel)

    gcode_search = ttk.Frame(gcode_txt_frame, style="Printer.TFrame")
    gcode_search.grid(row=3, column=0, sticky="ew", pady=(4, 0))
    gcode_search.columnconfigure(1, weight=1)
    ttk.Label(gcode_search, text=_t("printer.gcode.search"), style=_MUTED).grid(row=0, column=0, sticky="w")
    ttk.Entry(gcode_search, textvariable=panel._gcode_search_var, width=24).grid(
        row=0, column=1, sticky="ew", padx=(6, 6)
    )
    rounded_button(
        gcode_search,
        _t("printer.gcode.search_next"),
        lambda: panel._gcode_find_next(backward=False),
        variant="secondary",
        compact=True,
    ).grid(row=0, column=2, padx=(0, 4))
    rounded_button(
        gcode_search,
        _t("printer.gcode.search_prev"),
        lambda: panel._gcode_find_next(backward=True),
        variant="secondary",
        compact=True,
    ).grid(row=0, column=3)

    gcode_act = ttk.Frame(gcode_txt_frame, style="Printer.TFrame")
    gcode_act.grid(row=4, column=0, sticky="ew", pady=(4, 0))
    rounded_button(
        gcode_act,
        _t("printer.btn.print_check"),
        panel.show_print_check,
        variant="accent",
        compact=True,
    ).pack(side="left", padx=(0, 8))
    tip(gcode_act, _t("printer.tip.print_check_file"))
    rounded_button(
        gcode_act,
        _t("printer.btn.copy_all"),
        panel._copy_gcode_display,
        variant="secondary",
        compact=True,
    ).pack(side="left", padx=(0, 6))
    rounded_button(
        gcode_act,
        _t("printer.btn.save_as"),
        panel._save_gcode_edited_local,
        variant="secondary",
        compact=True,
    ).pack(side="left", padx=(0, 6))
    rounded_button(
        gcode_act,
        _t("printer.btn.html_export"),
        panel._export_gcode_html,
        variant="secondary",
        compact=True,
    ).pack(side="left")
    tip(gcode_act, _t("printer.tip.copy_save_gcode"))

    button_grid(
        tab_files,
        [
            (_t("printer.btn.print_check"), panel.show_print_check, _BTN, _t("printer.tip.print_check_running")),
            (_t("printer.btn.refresh"), panel._refresh_gcode_list, _BTN, _t("printer.tip.refresh_list")),
            (_t("printer.btn.upload"), panel._upload_gcode, _BTN, _t("printer.tip.upload")),
            (_t("printer.btn.download"), panel._download_gcode, _BTN, _t("printer.tip.download")),
            (_t("printer.btn.load_gcode"), panel._reload_gcode_text, _BTN, _t("printer.tip.reload_gcode")),
            (_t("printer.btn.delete"), panel._delete_gcode, _BTN, _t("printer.tip.delete")),
        ],
        columns=3,
    ).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
