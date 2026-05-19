"""PC/SC reader for ACR122U and compatible devices."""

from __future__ import annotations

from smartcard.Exceptions import NoCardException
from smartcard.System import readers
from smartcard.util import toHexString


class NfcReaderError(Exception):
    pass


def is_no_tag_on_reader_error(exc: BaseException) -> bool:
    """Windows 0x80100069 — Reader OK, aber kein Tag auf der Antenne."""
    if isinstance(exc, NoCardException):
        return True
    msg = str(exc).lower()
    raw = str(exc)
    return (
        "80100069" in raw
        or "removed card" in msg
        or "smartcard entfernt" in msg
        or "entfernt wurde" in msg
        or "no smart card" in msg
    )


class CrealityNfcReader:
    def __init__(self) -> None:
        self._reader = None
        self._connection = None
        self._reader_name: str | None = None
        self._tagless_ready = False

    @staticmethod
    def list_readers() -> list[str]:
        return [str(r) for r in readers()]

    @staticmethod
    def list_readers_safe() -> list[str]:
        """Like list_readers but returns [] if Smartcard service is stopped."""
        try:
            return CrealityNfcReader.list_readers()
        except Exception:
            return []

    def connect(self, reader_name: str | None = None) -> str:
        try:
            available = readers()
        except Exception as exc:
            msg = str(exc)
            if "8010001D" in msg or "Ressourcen-Manager" in msg or "Resource Manager" in msg:
                raise NfcReaderError("SMARTCARD_STOPPED") from exc
            raise NfcReaderError(msg) from exc
        if not available:
            raise NfcReaderError("Kein NFC-Reader gefunden. ACR122U per USB anschließen.")

        if reader_name:
            match = [r for r in available if reader_name in str(r)]
            if not match:
                raise NfcReaderError(f"Reader nicht gefunden: {reader_name}")
            reader = match[0]
        else:
            reader = available[0]

        self._reader = reader
        self._tagless_ready = False
        self._connection = None
        conn = reader.createConnection()
        try:
            conn.connect()
            self._connection = conn
        except Exception as exc:
            if is_no_tag_on_reader_error(exc):
                self._tagless_ready = True
            else:
                self._reader = None
                raise NfcReaderError(str(exc)) from exc
        self._reader_name = str(reader)
        return self._reader_name

    @property
    def direct_mode(self) -> bool:
        """Reader erkannt, PC/SC-Session erst wenn ein Tag aufliegt."""
        return self._tagless_ready

    @property
    def is_ready(self) -> bool:
        return self._reader is not None

    def disconnect(self) -> None:
        if self._connection:
            try:
                self._connection.disconnect()
            except Exception:
                pass
        self._reader = None
        self._connection = None
        self._reader_name = None
        self._tagless_ready = False

    def _ensure_connected(self) -> None:
        if self._reader is None:
            raise NfcReaderError("Reader nicht verbunden. Zuerst „Reader verbinden“.")
        if self._connection is not None:
            return
        self._connection = self._reader.createConnection()
        try:
            self._connection.connect()
            self._tagless_ready = False
        except Exception as exc:
            self._connection = None
            if is_no_tag_on_reader_error(exc):
                raise NfcReaderError(
                    "Kein Tag auf dem Reader — MIFARE-Classic-Tag (25 mm) flach auflegen."
                ) from exc
            raise NfcReaderError(str(exc)) from exc

    def _transmit(self, apdu: list[int]) -> tuple[list[int], int, int]:
        self._ensure_connected()
        assert self._connection is not None
        data, sw1, sw2 = self._connection.transmit(apdu)
        return data, sw1, sw2

    def _ok(self, sw1: int, sw2: int) -> bool:
        return sw1 == 0x90 and sw2 == 0x00

    def get_uid(self) -> bytes:
        data, sw1, sw2 = self._transmit([0xFF, 0xCA, 0x00, 0x00, 0x00])
        if not self._ok(sw1, sw2) or len(data) < 4:
            raise NfcReaderError("Tag nicht lesbar (kein MIFARE Classic?).")
        return bytes(data[:4])

    def load_key(self, key_number: int, key: bytes, structure: int = 0) -> None:
        apdu = [0xFF, 0x82, structure, key_number, 0x06, *key]
        _, sw1, sw2 = self._transmit(apdu)
        if not self._ok(sw1, sw2):
            raise NfcReaderError("Schlüssel konnte nicht geladen werden.")

    def auth_block(self, block: int, key_type: int, key_number: int) -> bool:
        # 6-byte auth
        _, sw1, sw2 = self._transmit(
            [0xFF, 0x88, 0x00, block, key_type, key_number]
        )
        if self._ok(sw1, sw2):
            return True
        # 10-byte auth fallback
        _, sw1, sw2 = self._transmit(
            [0xFF, 0x86, 0x00, 0x00, 0x05, 0x01, 0x00, block, key_type, key_number]
        )
        return self._ok(sw1, sw2)

    def read_block(self, block: int) -> bytes:
        data, sw1, sw2 = self._transmit([0xFF, 0xB0, 0x00, block, 0x10])
        if not self._ok(sw1, sw2):
            raise NfcReaderError(f"Block {block} lesen fehlgeschlagen.")
        return bytes(data)

    def write_block(self, block: int, payload: bytes) -> None:
        if len(payload) != 16:
            raise ValueError("Block muss 16 Bytes haben.")
        apdu = [0xFF, 0xD6, 0x00, block, 0x10, *payload]
        _, sw1, sw2 = self._transmit(apdu)
        if not self._ok(sw1, sw2):
            raise NfcReaderError(f"Block {block} schreiben fehlgeschlagen.")

    @property
    def uid_hex(self) -> str:
        return toHexString(self.get_uid()).replace(" ", "")
