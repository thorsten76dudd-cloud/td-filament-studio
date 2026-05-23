"""Tests: CFS-Vorschau (Demo-Layout)."""

import unittest

from creality_nfc.cfs_layout import parse_cfs_layout
from creality_nfc.cfs_simulate import build_simulated_boxs_info, merge_cfs_preview_state


class CfsSimulateTests(unittest.TestCase):
    def test_four_boxes_sixteen_slots(self) -> None:
        state = {"boxsInfo": build_simulated_boxs_info(4)}
        layout = parse_cfs_layout(state)
        self.assertEqual(layout.box_count(), 4)
        self.assertEqual(len(layout.all_slots()), 16)

    def test_merge_off_returns_real(self) -> None:
        real = {"boxsInfo": {"materialBoxs": [{"type": 0, "id": 1, "materials": []}]}}
        self.assertIs(merge_cfs_preview_state(real, preview_boxes=None), real)

    def test_merge_on_overrides(self) -> None:
        real = {"boxsInfo": {"materialBoxs": [{"type": 0, "id": 1, "materials": []}]}}
        merged = merge_cfs_preview_state(real, preview_boxes=4)
        self.assertEqual(parse_cfs_layout(merged).box_count(), 4)


if __name__ == "__main__":
    unittest.main()
