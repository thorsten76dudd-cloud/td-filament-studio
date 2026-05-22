"""Tag memory viewer and format dialog."""

from __future__ import annotations

import tkinter as tk
from tkinter import scrolledtext, ttk

from ui.messaging import alert, confirm, notify

from creality_nfc.reader import CrealityNfcReader, NfcReaderError
from creality_nfc.smartcard_service import probe_pcsc, scard_status_message
from creality_nfc.tag_io import TagSession, parse_tag_payload, payload_is_empty
from ui.dialog_theme import prepare_toplevel


class TagToolsDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, reader: CrealityNfcReader) -> None:
        super().__init__(parent)
        self.title("Tag-Speicher")
        self.reader = reader

        pad = {"padx": 10, "pady": 4}
        btns = ttk.Frame(self)
        btns.pack(fill="x", **pad)
        ttk.Button(btns, text="Speicher lesen", command=self.read_memory).pack(side="left")
        ttk.Button(btns, text="Payload dekodieren", command=self.decode_payload).pack(
            side="left", padx=8
        )
        ttk.Button(btns, text="Tag formatieren…", command=self.format_tag).pack(side="right")

        self.text = scrolledtext.ScrolledText(self, height=20, font=("Consolas", 9))
        self.text.pack(fill="both", expand=True, padx=10, pady=8)

        prepare_toplevel(self, parent, width=520, height=420, geometry_key="tag_tools")

    def _session(self) -> TagSession:
        self.reader.connect()
        return TagSession(self.reader)

    def _ensure_reader(self) -> bool:
        state = probe_pcsc()
        if state == "ok":
            return True
        alert(
            self,
            scard_status_message(state) + "\n\nReader per USB verbinden.",
            "warn",
            "NFC-Reader",
        )
        return False

    def read_memory(self) -> None:
        if not self._ensure_reader():
            return
        try:
            session = self._session()
            dump = session.read_memory_dump()
            lines = [f"UID: {session.uid.hex().upper()}\n"]
            for block in sorted(dump):
                data = dump[block]
                hexs = data.hex(" ").upper()
                ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in data)
                lines.append(f"Block {block:2d}: {hexs}  |{ascii_part}|")
            self.text.delete("1.0", "end")
            self.text.insert("1.0", "\n".join(lines))
        except Exception as exc:
            alert(self, str(exc), "error", "Tag-Speicher")

    def decode_payload(self) -> None:
        if not self._ensure_reader():
            return
        try:
            session = self._session()
            raw = session.read_payload()
            self.text.delete("1.0", "end")
            if payload_is_empty(raw):
                self.text.insert(
                    "1.0",
                    f"UID: {session.uid.hex().upper()}\n\nTag ist leer (kein Filament-Payload).",
                )
            else:
                info = parse_tag_payload(raw)
                self.text.insert(
                    "1.0",
                    f"UID: {session.uid.hex().upper()}\n\n"
                    f"Roh (96):\n{raw!r}\n\n"
                    + "\n".join(f"{k}: {v}" for k, v in info.items()),
                )
        except Exception as exc:
            alert(self, str(exc), "error", "Tag-Speicher")

    def format_tag(self) -> None:
        def do_format() -> None:
            if not self._ensure_reader():
                return
            try:
                session = self._session()
                report, tag_empty = session.format_tag()
                notify(
                    self,
                    "Tag formatiert.\n\n" + report,
                    "ok" if tag_empty else "warn",
                )
                self.text.delete("1.0", "end")
                self.text.insert("1.0", session.describe_reading())
            except NfcReaderError as exc:
                alert(self, str(exc), "error", "Tag-Speicher")
            except Exception as exc:
                alert(self, str(exc), "error", "Tag-Speicher")

        confirm(
            self,
            "Tag-Inhalt löschen (Sektoren 1–2)?\n"
            "Nur für leere/neue Tags — nicht für fabrikversiegelte Creality-Spulen.",
            do_format,
        )
