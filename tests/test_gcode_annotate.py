"""Tests: G-Code-Zeilen-Erklärungen."""

import unittest

from creality_nfc.gcode_annotate import annotate_gcode_text, explain_gcode_line


class GcodeAnnotateTests(unittest.TestCase):
    def test_comment(self) -> None:
        self.assertEqual("layer 5", explain_gcode_line("; layer 5"))

    def test_g1_extrude(self) -> None:
        h = explain_gcode_line("G1 X10 Y20 E1.5 F1200")
        self.assertIn("Druck", h)

    def test_g0_travel(self) -> None:
        h = explain_gcode_line("G0 X100 Y100 F30000")
        self.assertIn("Schnell", h)

    def test_line_count(self) -> None:
        body = ";\nG28\nG1 X1 E1\n"
        ann = annotate_gcode_text(body)
        self.assertEqual(len(ann.splitlines()), len(body.splitlines()))


if __name__ == "__main__":
    unittest.main()
