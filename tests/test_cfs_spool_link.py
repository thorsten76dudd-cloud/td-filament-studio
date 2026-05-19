"""Tests: CFS ↔ Spule."""

import tempfile
import unittest
from pathlib import Path

from creality_nfc.cfs_adopt import CfsSlotInfo
from creality_nfc.cfs_spool_link import bind_slot, find_spool_for_deduct, find_spool_for_slot
from creality_nfc.gcode_filament import GcodeFilamentSpec
from creality_nfc.spool_inventory import Spool, SpoolInventory


def _slot(**kwargs) -> CfsSlotInfo:
    base = dict(
        index=0,
        label="1A",
        vendor="",
        name="",
        material_type="",
        color_raw="",
        color_hex="FFFFFF",
        percent=None,
        rfid_id="",
        empty=False,
    )
    base.update(kwargs)
    return CfsSlotInfo(**base)


class CfsSpoolLinkTests(unittest.TestCase):
    def test_bind_slot_exclusive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inv = SpoolInventory(Path(tmp) / "spools.json")
            a = Spool(id="a", label="A", cfs_slot=0)
            b = Spool(id="b", label="B")
            inv.add(a)
            inv.add(b)
            bind_slot(inv, "b", 0)
            self.assertEqual(inv.get("b").cfs_slot, 0)
            self.assertIsNone(inv.get("a").cfs_slot)

    def test_find_by_filament_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inv = SpoolInventory(Path(tmp) / "spools.json")
            inv.add(Spool(id="x", label="X", filament_id="12345"))
            slot = _slot(rfid_id="12345", name="PLA")
            self.assertIsNotNone(find_spool_for_slot(inv, slot))

    def test_find_spool_for_deduct_by_color(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inv = SpoolInventory(Path(tmp) / "spools.json")
            blue = Spool(
                id="blue",
                label="PETG Blau",
                material_name="PETG",
                color_hex="#1E90FF",
            )
            white = Spool(
                id="white",
                label="PLA Weiß",
                material_name="PLA",
                color_hex="#FFFFFF",
                cfs_slot=3,
            )
            inv.add(blue)
            inv.add(white)
            slots = [
                _slot(index=0),
                _slot(index=1, label="1B", name="Blau", material_type="PETG", color_raw="1E90FF"),
                _slot(index=2),
                _slot(index=3, label="1D", name="Weiß", material_type="PLA"),
            ]
            spec = GcodeFilamentSpec(
                extruder_index=0,
                color_hex="#1E90FF",
                material_type="PETG",
                weight_g=2.0,
            )
            sp = find_spool_for_deduct(
                inv, slots, 1, spec, gcode_path="part_PETG_1h.gcode"
            )
            self.assertIsNotNone(sp)
            assert sp is not None
            self.assertEqual(sp.id, "blue")

    def test_deduct_does_not_steal_other_slot_spool(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inv = SpoolInventory(Path(tmp) / "spools.json")
            inv.add(
                Spool(
                    id="white",
                    label="PLA Weiß",
                    material_name="PLA",
                    color_hex="#FFFFFF",
                    cfs_slot=3,
                )
            )
            inv.add(
                Spool(
                    id="blue",
                    label="PETG Blau",
                    material_name="PETG",
                    color_hex="#1E90FF",
                )
            )
            slots = [
                _slot(index=1, label="1B", name="Blau", material_type="PETG", color_raw="1E90FF"),
                _slot(index=3, label="1D", name="Weiß", material_type="PLA"),
            ]
            spec = GcodeFilamentSpec(
                extruder_index=0,
                color_hex="#FFFFFF",
                material_type="PLA",
                weight_g=2.0,
            )
            sp = find_spool_for_deduct(
                inv,
                slots,
                1,
                spec,
                gcode_path="Körper_PETG_7m.gcode",
            )
            self.assertIsNotNone(sp)
            assert sp is not None
            self.assertEqual(sp.id, "blue")

    def test_extra_tag_uid_after_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inv = SpoolInventory(Path(tmp) / "spools.json")
            sp = Spool(id="a", label="Blau", tag_uid="AABBCCDD")
            inv.add(sp)
            self.assertIs(inv.find_by_uid("AABBCCDD"), sp)
            sp.register_tag_uid("11223344")
            inv.update(sp)
            self.assertIs(inv.find_by_uid("11223344"), sp)
            self.assertEqual(len(sp.all_tag_uids()), 2)
            self.assertIn("+1", sp.tag_uids_display(compact=True))
            self.assertIn("Chip 2:", sp.tag_uids_lines())
            sp.remove_tag_uid("AABBCCDD")
            self.assertEqual(sp.all_tag_uids(), ["11223344"])
            sp.remove_tag_uid("11223344")
            self.assertEqual(sp.all_tag_uids(), [])


if __name__ == "__main__":
    unittest.main()
