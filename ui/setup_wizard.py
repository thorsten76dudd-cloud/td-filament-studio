"""Kurzer Ersteinrichtungs-Dialog."""



from __future__ import annotations



import tkinter as tk

from collections.abc import Callable

from tkinter import ttk



from creality_nfc.smartcard_service import probe_pcsc, scard_status_message

from ui.components import scrollable_tab

from ui.dialog_theme import prepare_toplevel

from creality_nfc.config import MATERIAL_DB_PRINTER_ONLY





class SetupWizardDialog(tk.Toplevel):

    def __init__(

        self,

        parent: tk.Misc,

        *,

        has_database: bool,

        show_on_startup: bool = False,

        on_open_help: Callable[[], None],

        on_connect_reader: Callable[[], None],

        on_load_db: Callable[[], None],

        on_done: Callable[[bool], None],

    ) -> None:

        super().__init__(parent)

        self.title("Ersteinrichtung — TD Filament Studio")

        self.minsize(500, 420)



        footer = ttk.Frame(self, padding=(14, 10))

        footer.pack(side="bottom", fill="x")



        self.show_on_startup_var = tk.BooleanVar(value=show_on_startup)

        ttk.Checkbutton(

            footer,

            text="Ersteinrichtung bei jedem Programmstart anzeigen",

            variable=self.show_on_startup_var,

        ).pack(anchor="w", pady=(0, 10))



        btns = ttk.Frame(footer)

        btns.pack(fill="x")

        ttk.Button(btns, text="Hilfe öffnen", command=on_open_help, style="Secondary.TButton").pack(

            side="left", padx=(0, 8)

        )

        ttk.Button(btns, text="Reader verbinden", command=on_connect_reader, style="Secondary.TButton").pack(

            side="left", padx=(0, 8)

        )

        if not has_database:

            load_label = "Vom Drucker laden" if MATERIAL_DB_PRINTER_ONLY else "Cloud laden"

            ttk.Button(btns, text=load_label, command=on_load_db, style="Secondary.TButton").pack(

                side="left", padx=(0, 8)

            )

        ttk.Button(

            btns,

            text="Fertig",

            command=lambda: self._finish(on_done),

            style="Accent.TButton",

        ).pack(side="right")



        body = ttk.Frame(self)

        body.pack(fill="both", expand=True)

        _canvas, scroll = scrollable_tab(body)



        pad = {"padx": 14, "pady": 6}

        ttk.Label(

            scroll,

            text="Willkommen! Diese Checkliste hilft beim Start.",

            font=("Segoe UI", 11, "bold"),

        ).pack(anchor="w", **pad)



        ttk.Label(

            scroll,

            text="Für RFID-Tags brauchst du Reader + Tags + Material-DB.\n"

            "„Meine Spulen“ ist optional — Restgewicht und RFID-Verknüpfung lokal.",

            wraplength=480,

            justify="left",

            style="Muted.TLabel",

        ).pack(anchor="w", **pad)



        state = probe_pcsc()

        checks = [

            (

                "Windows Smartcard-Dienst",

                state in ("ok", "no_reader"),

                scard_status_message(state),

            ),

            (

                "NFC-Reader (ACR122U o.ä.)",

                state == "ok",

                "USB-Reader anschließen, dann „Reader verbinden“ im RFID-Tab.",

            ),

            (

                "Material-Datenbank",

                has_database,

                (

                    "Tab Material-Datenbank → „Vom Drucker (SSH)“ (Drucker-IP, Root-SSH)."

                    if MATERIAL_DB_PRINTER_ONLY

                    else "Tab Material-Datenbank → „Creality Cloud“ oder „Vom Drucker“."

                ),

            ),

            (

                "Tags: MIFARE Classic 1K, 25 mm",

                True,

                "Siehe Hilfe → „Benötigte Hardware & Tags“ oder „Tag-Halter (Links)…“ (Amazon-Beispiele).",

            ),

        ]



        for title, ok, hint in checks:

            row = ttk.Frame(scroll)

            row.pack(fill="x", **pad)

            mark = "✓" if ok else "○"

            color = "#4ade9a" if ok else "#9aa0a6"

            ttk.Label(row, text=f"{mark}  {title}", foreground=color).pack(anchor="w")

            ttk.Label(row, text=hint, wraplength=460, style="Muted.TLabel").pack(anchor="w", padx=(18, 0))



        ttk.Label(

            scroll,

            text="Reader verbinden → Material wählen → Tag auflegen → „Tag schreiben“.",

            wraplength=480,

            justify="left",

        ).pack(anchor="w", padx=14, pady=(8, 12))



        prepare_toplevel(self, parent, width=560, height=520)



    def _finish(self, on_done: Callable[[bool], None]) -> None:

        on_done(self.show_on_startup_var.get())

        self.destroy()

