"""Tests: Multi-CFS-Layout (bis 4 Boxen)."""

import unittest

from creality_nfc.cfs_layout import cfs_slot_label, parse_cfs_layout, parse_slot_key


class CfsLayoutTests(unittest.TestCase):
    def test_slot_label(self) -> None:
        self.assertEqual(cfs_slot_label(1, 0), "1A")
        self.assertEqual(cfs_slot_label(2, 1), "2B")

    def test_parse_slot_key(self) -> None:
        self.assertEqual(parse_slot_key("2B"), (2, 1))
        self.assertEqual(parse_slot_key("CFS-S3"), (1, 2))

    def test_two_boxes(self) -> None:
        state = {
            "boxsInfo": {
                "materialBoxs": [
                    {
                        "type": 0,
                        "id": 1,
                        "materials": [
                            {"vendor": "A", "name": "PLA", "type": "PLA", "color": "FF0000"},
                        ],
                    },
                    {
                        "type": 0,
                        "id": 2,
                        "materials": [
                            {"vendor": "B", "name": "PETG", "type": "PETG", "color": "0000FF"},
                        ],
                    },
                ],
            },
        }
        layout = parse_cfs_layout(state)
        self.assertEqual(layout.box_count(), 2)
        all_s = layout.all_slots()
        self.assertEqual(len(all_s), 8)
        filled = [s for s in all_s if not s.empty]
        self.assertEqual(len(filled), 2)
        self.assertEqual(filled[0].box_id, 1)
        self.assertEqual(filled[1].box_id, 2)


if __name__ == "__main__":
    unittest.main()
