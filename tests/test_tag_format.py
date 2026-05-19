"""Tag leeren — Kryptografie & Erkennung leerer Payloads."""

import unittest

from creality_nfc.crypto import cipher_data
from creality_nfc.tag_io import (
    _sector1_to_plain,
    empty_sector1_wire_bytes,
    payload_is_empty,
    wire_sector1_is_empty,
)


class TestTagFormat(unittest.TestCase):
    def test_encrypted_empty_roundtrip(self) -> None:
        enc = cipher_data(1, bytes(48))
        self.assertTrue(any(enc))
        plain = _sector1_to_plain(enc)
        self.assertEqual(plain, bytes(48))
        raw = (plain + bytes(48)).decode("ascii", errors="replace")
        self.assertTrue(payload_is_empty(raw))

    def test_plain_zero_sector1(self) -> None:
        plain = _sector1_to_plain(bytes(48))
        self.assertEqual(plain, bytes(48))

    def test_wire_empty_fingerprint(self) -> None:
        wire = empty_sector1_wire_bytes()
        self.assertTrue(wire_sector1_is_empty(wire))
        self.assertTrue(wire.hex().upper().startswith("C3B98E"))


if __name__ == "__main__":
    unittest.main()
