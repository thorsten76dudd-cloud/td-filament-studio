"""Tests für G-Code-Umschreibung (Spulen-IDs)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from creality_nfc.gcode_rewrite import (
    apply_rewrite_plan,
    build_spool_mappings,
    parse_gcode_for_rewrite,
)
from creality_nfc.spool_inventory import Spool


class GcodeRewriteTests(unittest.TestCase):
    def test_rewrite_filament_ids(self) -> None:
        footer = (
            "END_PRINT\n"
            "; filament used [g] = 0.00, 23.58, 0.00, 0.00\n"
            "; CONFIG_BLOCK_START\n"
            "; filament_colour = #ffff00;#0000ff;#ff0000;#ffffff\n"
            "; filament_type = PETG;PETG;PETG;PLA\n"
            "; filament_ids = 06001;06001;06001;04001\n"
            '; filament_notes = ;;;\n'
            '; filament_settings_id = "CR-PETG";"CR-PETG";"CR-PETG";"PLA Support"\n'
            "; CONFIG_BLOCK_END\n"
        )
        head = (
            "; HEADER\n"
            "START_PRINT EXTRUDER_TEMP=250 BED_TEMP=70\n"
            "T1\n"
            "G1 X0\n"
        )
        with tempfile.NamedTemporaryFile("wb", suffix=".gcode", delete=False) as f:
            f.write(head.encode("utf-8"))
            f.write(b"G1 X1\n" * 100)
            f.write(footer.encode("utf-8"))
            path = Path(f.name)
        out: Path | None = None
        try:
            plan = parse_gcode_for_rewrite(path)
            self.assertEqual(plan.initial_tool, 1)
            blue_spool = Spool(
                id="s1",
                label="Creality — CR-PETG @ Thorsten",
                brand="Creality",
                material_name="CR-PETG @ Thorsten",
                filament_id="06098",
                color_hex="0000FF",
                cfs_slot=1,
                cfs_box_id=1,
            )
            plan = build_spool_mappings(plan, [blue_spool], only_active=False)
            m1 = plan.mappings[1]
            self.assertEqual(m1.new_id, "06098")
            self.assertIn("06098", m1.new_notes)

            out = path.with_name("out_TD.gcode")
            apply_rewrite_plan(plan, out)
            tail = out.read_text(encoding="utf-8")[-800:]
            self.assertIn(";06098;", tail)
            self.assertRegex(tail, r"filament_ids\s*=\s*[^;\n]*;06098;")
        finally:
            path.unlink(missing_ok=True)
            if out is not None and out.is_file():
                out.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
