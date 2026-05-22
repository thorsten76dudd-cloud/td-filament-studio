"""Drucker-Tab: Unterseiten Monitor / Steuerung / Filament / Dateien."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

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

_SPEED_LABELS = {
    25: "Still",
    50: "Stabil 50%",
    100: "Standard 100%",
    125: "Ultraschnell 125%",
}


def _build_settings(panel: PrinterDevicePanel, parent: ttk.Frame) -> None:
    """Druckeinstellungen — 2 Spalten, ohne Scrollen."""
    parent.columnconfigure(0, weight=1)
    parent.columnconfigure(1, weight=1)

    left = ttk.Frame(parent, style="Printer.Card.TFrame")
    left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
    right = ttk.Frame(parent, style="Printer.Card.TFrame")
    right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

    temps = ttk.LabelFrame(left, text="  Temperaturen  ", padding=8, style=_SEC)
    temps.pack(fill="x", pady=(0, 8))
    tg = ttk.Frame(temps, style="Printer.Card.TFrame")
    tg.pack(fill="x")
    for col, (title, attr) in enumerate(
        (("Düse", "nozzle_lbl"), ("Bett", "bed_lbl"), ("Kammer", "box_lbl"))
    ):
        tg.columnconfigure(col, weight=1)
        cell = tk.Frame(tg, bg=SURFACE_DARK, padx=6, pady=8)
        cell.grid(row=0, column=col, sticky="nsew", padx=3)
        ttk.Label(cell, text=title, style="Printer.TempSub.TLabel").pack(anchor="w")
        lbl = ttk.Label(cell, text="— / — °C", style="Printer.Temp.TLabel")
        lbl.pack(anchor="w", pady=(2, 0))
        setattr(panel, attr, lbl)

    tgt = ttk.LabelFrame(left, text="  Soll-Temperatur  ", padding=8, style=_SEC)
    tgt.pack(fill="x")
    panel.nozzle_tgt = tk.IntVar(value=0)
    panel.bed_tgt = tk.IntVar(value=0)
    panel.box_tgt = tk.IntVar(value=0)
    tg2 = ttk.Frame(tgt, style="Printer.Card.TFrame")
    tg2.pack(fill="x")
    for col, (lbl, var, cmd) in enumerate(
        (
            ("Düse", panel.nozzle_tgt, panel._apply_nozzle),
            ("Bett", panel.bed_tgt, panel._apply_bed),
            ("Kammer", panel.box_tgt, panel._apply_chamber),
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
            rounded_button(row, "Set", cmd, variant="secondary", compact=True),
            f"Soll-{lbl} senden.",
        ).pack(side="left", padx=4)

    led = ttk.LabelFrame(right, text="  LED & Achsen  ", padding=8, style=_SEC)
    led.pack(fill="x", pady=(0, 8))
    panel.led_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(
        led, text="LED ein", variable=panel.led_var, command=panel._toggle_led, style="Printer.TCheckbutton"
    ).pack(anchor="w", pady=(0, 6))
    button_grid(
        led,
        [
            ("Licht an", lambda: panel._set_light(True), _BTN, "LED an."),
            ("Licht aus", lambda: panel._set_light(False), _BTN, "LED aus."),
            ("Home XY", lambda: panel._cmd("Home XY", home_xy), _BTN, "X/Y Home."),
            ("Home Z", lambda: panel._cmd("Home Z", home_z), _BTN, "Z Home."),
        ],
        columns=2,
    ).pack(fill="x")

    fan_box = ttk.LabelFrame(right, text="  Lüfter  ", padding=8, style=_SEC)
    fan_box.pack(fill="x", pady=(0, 8))
    panel.fan_vars = [tk.IntVar(value=0) for _ in range(3)]
    for i, name in enumerate(("Modell", "Gehäuse", "Seite")):
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
            rounded_button(row, "Set", lambda ch=i: panel._apply_fan(ch), variant="secondary", compact=True),
            f"Lüfter {name}.",
        ).pack(side="left")

    spd = ttk.LabelFrame(right, text="  Druckgeschwindigkeit  ", padding=8, style=_SEC)
    spd.pack(fill="x")
    sr = ttk.Frame(spd, style="Printer.Card.TFrame")
    sr.pack(fill="x")
    for col, (pct, _label) in enumerate(PRINT_SPEED_PRESETS):
        sr.columnconfigure(col, weight=1)
        ttk.Radiobutton(
            sr,
            text=_SPEED_LABELS.get(pct, _label),
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

    ctrl = tk.Frame(parent, bg=CARD)
    ctrl.pack(fill="x", pady=(6, 0))
    ttk.Label(
        ctrl,
        text="Start: Creality Print / Drucker-Display",
        style=_MUTED,
    ).pack(side="left", padx=(0, 12))
    panel._btn_pause = tip(
        rounded_button(ctrl, "Pause", panel._pause_print, variant="secondary"),
        "Pausieren.",
    )
    panel._btn_pause.pack(side="left", padx=4)
    panel._btn_resume = tip(
        rounded_button(ctrl, "Fortsetzen", panel._resume_print, variant="secondary"),
        "Fortsetzen.",
    )
    panel._btn_resume.pack(side="left", padx=4)
    tip(
        rounded_button(ctrl, "Stopp", panel._stop_print, variant="danger"),
        "Abbrechen.",
    ).pack(side="left", padx=4)
    panel._btn_deduct = tip(
        rounded_button(
            ctrl,
            "Verbrauch abziehen…",
            panel._manual_post_print_deduct,
            variant="secondary",
        ),
        "Filament von verknüpften Spulen abziehen (nach Druckende).",
    )
    panel._btn_deduct.pack(side="right", padx=4)


def build_creality_dashboard(panel: PrinterDevicePanel, outer: ttk.Frame) -> None:
    """Unterseiten statt einer überfüllten Einzelseite."""

    conn = ttk.LabelFrame(outer, text="  Verbindung  ", padding=6, style=_SEC)
    conn.pack(fill="x", pady=(0, 6))
    panel.conn_var = tk.StringVar(value="Nicht verbunden — IP im Tab RFID-Tag eintragen")
    ttk.Label(conn, textvariable=panel.conn_var, style=_MUTED).pack(anchor="w", pady=(0, 4))
    button_grid(
        conn,
        [
            ("Verbinden", panel.connect, _ACC, "WebSocket-Verbindung."),
            ("Trennen", panel.disconnect, _BTN, "Trennen."),
            ("Creality Web-UI", panel._open_creality_web_ui, _BTN, "Browser-Oberfläche."),
            ("Klipper / Web-UI", panel.open_klipper_ui, _BTN, "Klipper-UI."),
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
    nb.add(tab_mon, text="  Monitor  ")

    cam_card = ttk.LabelFrame(tab_mon, text="  Kamera  ", padding=4, style=_SEC)
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
        text="Verbinde mit dem Drucker — Kamera startet automatisch",
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
        rounded_button(cam_bar, "Live-Kamera", panel._toggle_live_camera, variant="accent"),
        "Livebild in der App (funktioniert auf jedem Monitor).",
    ).pack(side="left", padx=(0, 6))
    tip(
        rounded_button(cam_bar, "Vollbild", panel._open_camera_fullscreen, variant="secondary"),
        "Separates Edge-Fenster (WebRTC).",
    ).pack(side="left")
    panel._cam_status_var = tk.StringVar(value="")
    ttk.Label(cam_bar, textvariable=panel._cam_status_var, style=_MUTED).pack(side="left", padx=10)

    print_card = ttk.LabelFrame(tab_mon, text="  Aktueller Druck  ", padding=8, style=_SEC)
    print_card.grid(row=1, column=0, sticky="ew")
    _build_print_strip(panel, print_card)

    # —— Steuerung ——
    tab_ctrl = ttk.Frame(nb, padding=8, style="Printer.TFrame")
    tab_ctrl.rowconfigure(0, weight=1)
    tab_ctrl.columnconfigure(0, weight=1)
    nb.add(tab_ctrl, text="  Steuerung  ")
    settings_wrap = ttk.Frame(tab_ctrl, style="Printer.TFrame")
    settings_wrap.pack(fill="both", expand=True)
    _build_settings(panel, settings_wrap)

    # —— Filament ——
    tab_fil = ttk.Frame(nb, padding=4, style="Printer.TFrame")
    nb.add(tab_fil, text="  Filament  ")
    panel.cfs_dashboard = CfsDashboard(
        tab_fil,
        appearance="printer",
        layout="creality",
        on_adopt=panel._adopt_cfs_slot,
        on_refresh=panel._refresh_cfs,
        on_feed=panel._cfs_feed,
        on_retract=panel._cfs_retract,
        on_bind_spool=panel._bind_cfs_spool_slot,
        inventory=panel.app.inventory,
    )
    panel.cfs_dashboard.pack(fill="both", expand=True)

    # —— Dateien: Liste links, G-Code-Vorschau rechts ——
    tab_files = ttk.Frame(nb, padding=8, style="Printer.TFrame")
    tab_files.rowconfigure(1, weight=1)
    tab_files.columnconfigure(0, weight=2)
    tab_files.columnconfigure(1, weight=3)
    nb.add(tab_files, text="  Dateien  ")

    panel._status_var = tk.StringVar(value="Nicht verbunden")
    ttk.Label(tab_files, textvariable=panel._status_var, style=_MUTED).grid(
        row=0, column=0, columnspan=2, sticky="w", pady=(0, 4)
    )

    list_card = ttk.LabelFrame(tab_files, text="  G-Code auf dem Drucker  ", padding=4, style=_SEC)
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

    prev_card = ttk.LabelFrame(tab_files, text="  Vorschau  ", padding=4, style=_SEC)
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
    panel._gcode_prev_nb.add(tab_thumb, text="  Bild  ")
    panel._gcode_prev_nb.add(tab_gcode, text="  G-Code  ")

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
        text="Datei wählen\n\n(Vorschaubild vom Slicer,\nfalls vorhanden)",
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
    panel._gcode_text_status = tk.StringVar(
        value="Datei wählen — G-Code per SSH (Anfang/Ende). Markieren, kopieren, lokal bearbeiten."
    )
    ttk.Label(gcode_txt_frame, textvariable=panel._gcode_text_status, style=_MUTED).grid(
        row=0, column=0, sticky="ew", pady=(0, 2)
    )
    gcode_hdr = ttk.Frame(gcode_txt_frame, style="Printer.TFrame")
    gcode_hdr.grid(row=1, column=0, sticky="ew", pady=(0, 2))
    gcode_hdr.columnconfigure(0, weight=3)
    gcode_hdr.columnconfigure(1, weight=2)
    ttk.Label(gcode_hdr, text="G-Code", style=_BODY).grid(row=0, column=0, sticky="w")
    ttk.Label(gcode_hdr, text="Was der Drucker macht", style=_BODY).grid(
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
    panel.gcode_hint_text = tk.Text(
        txt_wrap,
        height=22,
        wrap="none",
        font=("Segoe UI", 8),
        state="disabled",
        cursor="arrow",
    )
    apply_text_area_style(panel.gcode_hint_text, bg=SURFACE_DARK)
    panel.gcode_hint_text.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
    scroll_gcode.grid(row=0, column=2, sticky="ns")
    panel.gcode_text.insert(
        "1.0",
        "; G-Code-Text erscheint hier nach Auswahl einer Datei.\n"
        "; Root-SSH und Drucker-IP wie beim Herunterladen.\n",
    )
    panel.gcode_hint_text.config(state="normal")
    panel.gcode_hint_text.insert(
        "1.0",
        "Hinweis nach Dateiauswahl\nSSH wie beim Herunterladen",
    )
    panel.gcode_hint_text.config(state="disabled")
    for _w in (txt_wrap, panel.gcode_text, panel.gcode_hint_text):
        _w.bind("<MouseWheel>", _gcode_wheel)
        _w.bind("<Button-4>", _gcode_wheel)
        _w.bind("<Button-5>", _gcode_wheel)

    gcode_act = ttk.Frame(gcode_txt_frame, style="Printer.TFrame")
    gcode_act.grid(row=3, column=0, sticky="ew", pady=(4, 0))
    rounded_button(
        gcode_act,
        "Alles kopieren",
        panel._copy_gcode_display,
        variant="secondary",
        compact=True,
    ).pack(side="left", padx=(0, 6))
    rounded_button(
        gcode_act,
        "Speichern unter…",
        panel._save_gcode_edited_local,
        variant="secondary",
        compact=True,
    ).pack(side="left")
    tip(
        gcode_act,
        "Strg+C kopiert markierten Text. Bearbeitungen sind nur lokal — nicht auf dem Drucker.",
    )

    button_grid(
        tab_files,
        [
            ("Aktualisieren", panel._refresh_gcode_list, _BTN, "Liste neu laden."),
            ("Hochladen…", panel._upload_gcode, _BTN, "Hochladen."),
            ("Herunterladen…", panel._download_gcode, _BTN, "G-Code komplett speichern."),
            ("G-Code laden", panel._reload_gcode_text, _BTN, "Text neu vom Drucker holen."),
            ("Löschen", panel._delete_gcode, _BTN, "Löschen."),
        ],
        columns=3,
    ).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
