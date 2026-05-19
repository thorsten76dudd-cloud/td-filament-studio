"""Tag-Farbe: Schreiben/Lesen."""

import unittest

from creality_nfc.tag_io import build_tag_payload, parse_tag_payload, payload_bytes_from_read
from ui.color_swatch import color_from_tag_field, normalize_hex


class TestTagColorRoundtrip(unittest.TestCase):
    def test_blue_roundtrip(self) -> None:
        payload = build_tag_payload("04001", "0000FF", "1 KG", "K2 Pro", serial="000063")
        info = parse_tag_payload(payload.decode("ascii"))
        self.assertEqual(normalize_hex(color_from_tag_field(info["color"])), "0000FF")

    def test_white_roundtrip(self) -> None:
        payload = build_tag_payload("04001", "FFFFFF", "1 KG", "K2 Pro")
        info = parse_tag_payload(payload.decode("ascii"))
        self.assertEqual(normalize_hex(color_from_tag_field(info["color"])), "FFFFFF")

    def test_payload_bytes_from_read_length(self) -> None:
        raw = build_tag_payload("04001", "0000FF", "1 KG", "K2 Pro").decode("ascii")
        b = payload_bytes_from_read(raw)
        self.assertEqual(len(b), 96)


if __name__ == "__main__":
    unittest.main()
