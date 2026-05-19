"""Read/write Creality CFS RFID payload on MIFARE Classic 1K."""

from __future__ import annotations

from .crypto import KEY_DEFAULT, cipher_data, create_tag_key
from .reader import CrealityNfcReader, NfcReaderError

KEY_TYPE_A = 0x60
KEY_TYPE_B = 0x61

WEIGHT_CODES = {
    "1 KG": "0330",
    "750 G": "0247",
    "600 G": "0198",
    "500 G": "0165",
    "250 G": "0082",
}


def build_tag_payload(
    material_id: str,
    color_hex: str,
    weight_label: str,
    printer_model: str,
    vendor_id: str = "0276",
    serial: str = "000001",
) -> bytes:
    """Build 96-byte ASCII payload."""
    mid = "".join(c for c in material_id if c.isdigit())[-5:].zfill(5)
    filament_id = "1" + mid
    color = color_hex.replace("#", "").upper()
    if len(color) == 6:
        color = "0" + color
    elif len(color) == 7 and not color.startswith("0"):
        color = "0" + color[-6:]
    color = color[:7].ljust(7, "0")

    wkey = weight_label.strip().upper()
    if wkey == "1KG":
        wkey = "1 KG"
    length = WEIGHT_CODES.get(wkey, "0330")
    serial_s = "".join(c for c in serial if c.isdigit())[-6:].zfill(6)

    body = (
        "AB124"
        + vendor_id
        + "A2"
        + filament_id
        + color
        + length
        + serial_s
        + "00000000000000"
        + printer_model
    )
    return body.ljust(96).encode("ascii")


def payload_bytes_from_read(raw: str) -> bytes:
    """96-Byte-Payload für write_payload (1:1-Kopie eines gelesenen Tags)."""
    return str(raw or "").encode("ascii", errors="replace").ljust(96)[:96]


def payload_is_empty(raw: str) -> bool:
    """True wenn kein Creality-Filament-Payload auf dem Tag liegt."""
    return len(str(raw or "").replace("\x00", "").strip()) < 8


_EMPTY_S1_WIRE: bytes | None = None


def empty_sector1_wire_bytes() -> bytes:
    """Verschlüsselter Leer-Inhalt (Blöcke 4–6 sehen „voll“ aus, z. B. C3B98E…)."""
    global _EMPTY_S1_WIRE
    if _EMPTY_S1_WIRE is None:
        _EMPTY_S1_WIRE = cipher_data(1, bytes(48))
    return _EMPTY_S1_WIRE


def wire_sector1_is_empty(s1: bytes) -> bool:
    if len(s1) != 48:
        return False
    if not any(s1):
        return True
    return s1 == empty_sector1_wire_bytes()


def parse_tag_payload(raw: str) -> dict[str, str]:
    if payload_is_empty(raw):
        return {
            "date": "",
            "vendor_id": "",
            "batch": "",
            "material_id": "",
            "color": "",
            "weight_code": "",
            "serial": "",
            "printer": "",
        }
    s = raw.strip()
    if len(s) < 34:
        raise ValueError(
            "Tag-Daten unvollständig (beschädigt oder kein Creality-Format).\n"
            "„Tag leeren…“ und neu schreiben."
        )
    return {
        "date": s[0:5],
        "vendor_id": s[5:9],
        "batch": s[9:11],
        "material_id": s[12:17],
        "color": s[17:24],
        "weight_code": s[24:28],
        "serial": s[28:34],
        "printer": s[48:].strip() if len(s) > 48 else "",
    }


def tag_material_id(material_id: str) -> str:
    """5-stellige ID wie auf dem Tag (ohne führende 1)."""
    return "".join(c for c in material_id if c.isdigit())[-5:].zfill(5)


def verify_tag_payload(
    info: dict[str, str],
    *,
    material_id: str,
    color_hex: str,
    weight_label: str,
    printer_model: str,
    serial: str,
) -> list[str]:
    """Vergleicht Gelesenes mit Erwartetem; leere Liste = OK."""
    errors: list[str] = []
    expected_id = tag_material_id(material_id)
    if info.get("material_id", "") != expected_id:
        errors.append(f"Material-ID: erwartet {expected_id}, gelesen {info.get('material_id', '?')}")

    exp_color = color_hex.replace("#", "").upper()
    if len(exp_color) == 6:
        exp_color = "0" + exp_color
    read_color = (info.get("color") or "").strip().upper()
    if read_color and exp_color and read_color != exp_color[:7].ljust(7, "0")[:7]:
        if read_color.lstrip("0")[-6:] != exp_color.lstrip("0")[-6:]:
            errors.append(f"Farbe: erwartet #{exp_color[-6:]}, gelesen {read_color}")

    wkey = weight_label.strip().upper()
    if wkey == "1KG":
        wkey = "1 KG"
    exp_w = WEIGHT_CODES.get(wkey, "")
    if exp_w and info.get("weight_code") != exp_w:
        errors.append(f"Gewicht: erwartet {wkey}, Code {info.get('weight_code', '?')}")

    exp_serial = "".join(c for c in serial if c.isdigit())[-6:].zfill(6)
    if info.get("serial") != exp_serial:
        errors.append(f"Serie: erwartet {exp_serial}, gelesen {info.get('serial', '?')}")

    if printer_model.strip() and info.get("printer", "").strip():
        if printer_model.strip() not in info.get("printer", ""):
            errors.append(
                f"Drucker: erwartet „{printer_model}“, gelesen „{info.get('printer', '')}“"
            )
    return errors


def _auth(r: CrealityNfcReader, block: int, key_num: int) -> bool:
    return r.auth_block(block, KEY_TYPE_A, key_num) or r.auth_block(block, KEY_TYPE_B, key_num)


def _auth_sector(r: CrealityNfcReader, sector: int, key_num: int) -> bool:
    """Sektor authentifizieren (erster Datenblock oder Trailer)."""
    base = sector * 4
    return _auth(r, base, key_num) or _auth(r, base + 3, key_num)


def _sector1_to_plain(s1: bytes) -> bytes:
    """Sektor-1-Rohdaten → Klartext (leere Blöcke 00 ohne Entschlüsselung)."""
    if len(s1) != 48:
        return cipher_data(0, s1)
    if not any(s1):
        return bytes(48)
    plain = cipher_data(0, s1)
    if not any(plain):
        return bytes(48)
    return plain


def _read_sector_data_blocks(
    r: CrealityNfcReader,
    sector: int,
    blocks: tuple[int, ...],
    key_nums: tuple[int, ...],
) -> bytes:
    """Liest Datenblöcke mit Re-Auth vor jedem Block (ACR122U-Stabilität)."""
    out = bytearray()
    for block in blocks:
        chunk: bytes | None = None
        for kn in key_nums:
            if not _auth_sector(r, sector, kn):
                continue
            for _ in range(2):
                try:
                    chunk = r.read_block(block)
                    break
                except NfcReaderError:
                    _auth_sector(r, sector, kn)
            if chunk is not None:
                break
        if chunk is None:
            raise NfcReaderError(
                f"Block {block} lesen fehlgeschlagen.\n\n"
                "Mögliche Ursachen:\n"
                "• Kein MIFARE Classic 1K (25 mm) — NTAG/andere Chips funktionieren nicht.\n"
                "• Leerer oder fremder Tag — im Tab RFID „Tag leeren…“, dann „Tag schreiben“.\n"
                "• Tag während des Lesens bewegt — flach und ruhig auf den Reader legen."
            )
        out.extend(chunk)
    return bytes(out)


class TagSession:
    def __init__(self, reader: CrealityNfcReader) -> None:
        self.reader = reader
        self.uid = reader.get_uid()
        self.enc_key = create_tag_key(self.uid)
        reader.load_key(0, KEY_DEFAULT)
        reader.load_key(1, self.enc_key)

    def read_payload(self) -> str:
        r = self.reader
        if not (_auth_sector(r, 1, 1) or _auth_sector(r, 1, 0)):
            raise NfcReaderError(
                "Sektor 1 nicht lesbar — Tag leer, falscher Chip-Typ oder unbekannte Schlüssel.\n"
                "„Tag leeren…“ und neu beschreiben (nur MIFARE Classic 1K)."
            )
        s1 = _read_sector_data_blocks(r, 1, (4, 5, 6), (1, 0))
        plain = _sector1_to_plain(s1)

        if not _auth_sector(r, 2, 0):
            raise NfcReaderError("Sektor 2 nicht lesbar — „Tag leeren…“ und Tag neu schreiben.")
        s2 = _read_sector_data_blocks(r, 2, (8, 9, 10), (0,))
        return (plain + s2).decode("ascii", errors="replace").rstrip("\x00")

    def write_payload(self, payload: bytes) -> None:
        if len(payload) != 96:
            raise ValueError("Payload muss 96 Bytes sein.")

        r = self.reader
        if _auth_sector(r, 1, 1):
            key_slot = 1
        elif _auth_sector(r, 1, 0):
            key_slot = 0
        else:
            raise RuntimeError("Authentifizierung Sektor 1 fehlgeschlagen.")

        self._write_sector1_payload(payload[:48], key_slot=key_slot)

        if key_slot == 0 and _auth_sector(r, 1, 0):
            trailer = bytearray(r.read_block(7))
            trailer[0:6] = self.enc_key
            trailer[10:16] = self.enc_key
            r.write_block(7, bytes(trailer))

        for i in range(3):
            block = 8 + i
            if not _auth_sector(r, 2, 0):
                raise RuntimeError("Authentifizierung Sektor 2 fehlgeschlagen.")
            r.write_block(block, payload[48 + i * 16 : 48 + (i + 1) * 16])

    def _write_sector1_payload(self, plain48: bytes, *, key_slot: int) -> None:
        r = self.reader
        if len(plain48) != 48:
            raise ValueError("Sektor 1 braucht 48 Bytes.")
        body = cipher_data(1, plain48) if key_slot == 1 else plain48
        for i in range(3):
            block = 4 + i
            if not _auth_sector(r, 1, key_slot):
                raise NfcReaderError(f"Block {block} — Authentifizierung fehlgeschlagen.")
            r.write_block(block, body[i * 16 : (i + 1) * 16])

    def _promote_sector1_uid_keys(self) -> bool:
        """Trailer Sektor 1 auf UID-Schlüssel (wie nach Tag schreiben)."""
        r = self.reader
        if not _auth_sector(r, 1, 0):
            return False
        trailer = bytearray(r.read_block(7))
        trailer[0:6] = self.enc_key
        trailer[10:16] = self.enc_key
        r.write_block(7, bytes(trailer))
        return _auth_sector(r, 1, 1)

    def format_tag(self) -> tuple[str, bool]:
        """Creality-Daten löschen. Gibt (Protokoll, Tag wirklich leer) zurück."""
        empty48 = bytes(48)
        empty16 = bytes(16)
        r = self.reader
        lines: list[str] = []

        if _auth_sector(r, 1, 1):
            key_slot = 1
        elif _auth_sector(r, 1, 0):
            key_slot = 0
        else:
            raise NfcReaderError(
                "Tag konnte nicht geleert werden — Sektor 1 nicht beschreibbar.\n"
                "Tag-Typ prüfen (MIFARE Classic 1K) oder anderen Tag versuchen."
            )

        self._write_sector1_payload(empty48, key_slot=key_slot)
        lines.append(f"Sektor 1: geleert (Schlüssel {'UID' if key_slot == 1 else 'FF'})")

        if key_slot == 0 and self._promote_sector1_uid_keys():
            self._write_sector1_payload(empty48, key_slot=1)
            key_slot = 1
            lines.append("Sektor 1: Creality-Verschlüsselung (UID-Schlüssel) gesetzt")
        elif key_slot == 1:
            self._promote_sector1_uid_keys()

        if not _auth_sector(r, 2, 0):
            raise NfcReaderError("Sektor 2 nicht beschreibbar — Tag nur teilweise geleert.")
        for block in (8, 9, 10):
            if not _auth_sector(r, 2, 0):
                raise NfcReaderError(f"Block {block} — Authentifizierung fehlgeschlagen.")
            r.write_block(block, empty16)
        lines.append("Sektor 2: geleert")

        verified = self.is_payload_empty()
        if verified:
            lines.append("Prüfung: Keine Filament-Daten — Tag ist leer.")
        else:
            lines.append(
                "Warnung: Daten noch lesbar — Tag 2 Sek. vom Reader nehmen, wieder auflegen, "
                "erneut „Tag leeren…“."
            )
        return "\n".join(lines), verified

    def is_payload_empty(self) -> bool:
        try:
            return payload_is_empty(self.read_payload())
        except Exception:
            return False

    def describe_reading(self) -> str:
        """Diagnose: UID, Blöcke, dekodierter Payload."""
        lines = [f"UID: {self.uid.hex().upper()}", ""]
        try:
            dump = self.read_memory_dump()
            lines.append("Blöcke 0–15 (hex):")
            for block in range(16):
                if block in dump:
                    data = dump[block]
                    asc = "".join(chr(b) if 32 <= b < 127 else "." for b in data)
                    lines.append(f"  {block:2d}: {data.hex().upper()}  |{asc}|")
                else:
                    lines.append(f"  {block:2d}: (nicht lesbar)")
        except Exception as exc:
            lines.append(f"Block-Dump: {exc}")

        lines.append("")
        try:
            raw = self.read_payload()
            lines.append(f"Payload-Roh ({len(raw)} Zeichen):")
            lines.append(repr(raw[:120] + ("…" if len(raw) > 120 else "")))
            if payload_is_empty(raw):
                lines.append("")
                lines.append("★ TAG IST LEER ★")
                lines.append(
                    "Keine Filament-Daten. Blöcke 4–6 können verschlüsselt aussehen "
                    "(z. B. C3B98E0E7A3D…) — das ist normal nach „Tag leeren“, nicht der alte Inhalt."
                )
            elif len(raw.strip("\x00")) >= 8:
                info = parse_tag_payload(raw)
                lines.append("")
                lines.append("Dekodiert:")
                for key, val in info.items():
                    lines.append(f"  {key}: {val}")
            else:
                lines.append("(Payload leer / nur Nullen)")
        except Exception as exc:
            lines.append(f"Payload: nicht lesbar — {exc}")
        return "\n".join(lines)

    def read_memory_dump(self) -> dict[int, bytes]:
        """Read blocks 0–15 (sectors 0–3) for diagnostics."""
        r = self.reader
        dump: dict[int, bytes] = {}
        r.load_key(0, KEY_DEFAULT)
        r.load_key(1, self.enc_key)
        sector_keys: dict[int, tuple[int, ...]] = {
            0: (0,),
            1: (1, 0),
            2: (0,),
            3: (0,),
        }
        for block in range(16):
            sector = block // 4
            if block % 4 == 3:
                if any(_auth_sector(r, sector, kn) for kn in sector_keys.get(sector, (0,))):
                    try:
                        dump[block] = r.read_block(block)
                    except NfcReaderError:
                        pass
                continue
            for kn in sector_keys.get(sector, (0,)):
                if _auth_sector(r, sector, kn):
                    try:
                        dump[block] = r.read_block(block)
                    except NfcReaderError:
                        pass
                    break
        return dump
