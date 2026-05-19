import unittest

from creality_nfc.tag_io import parse_tag_payload, payload_is_empty


class TestTagPayloadEmpty(unittest.TestCase):
    def test_empty_payload_no_error(self) -> None:
        self.assertTrue(payload_is_empty("\x00" * 96))
        info = parse_tag_payload("\x00" * 96)
        self.assertEqual(info["material_id"], "")

    def test_valid_min_length(self) -> None:
        raw = "AB124" + "0276" + "A2" + "10600" + "0FFFFFF" + "0330" + "000001" + "0" * 14 + "K2 Pro"
        self.assertFalse(payload_is_empty(raw))
        info = parse_tag_payload(raw.ljust(96))
        self.assertTrue(info["material_id"])


if __name__ == "__main__":
    unittest.main()
