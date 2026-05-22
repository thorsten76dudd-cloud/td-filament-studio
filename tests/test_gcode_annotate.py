"""Tests: G-Code-Zeilen-Erklärungen."""

import unittest

from creality_nfc.gcode_annotate import annotate_gcode_text, explain_gcode_line


class GcodeAnnotateTests(unittest.TestCase):
    def test_comment_layer_not_raw(self) -> None:
        self.assertEqual("Schicht 5", explain_gcode_line(";LAYER:5"))
        self.assertNotIn("LAYER", explain_gcode_line("; layer 5"))

    def test_comment_type_outer_wall(self) -> None:
        self.assertEqual("Außenwand drucken", explain_gcode_line(";TYPE:Outer wall"))

    def test_g1_extrude_german(self) -> None:
        h = explain_gcode_line("G1 X10 Y20 E1.5 F1200")
        self.assertIn("Drucklinie", h)
        self.assertNotIn("G1", h)

    def test_g0_travel_no_code(self) -> None:
        h = explain_gcode_line("G0 X100 Y100 F30000")
        self.assertIn("Schnell", h)
        self.assertNotIn("G0", h)

    def test_m104_german(self) -> None:
        h = explain_gcode_line("M104 S210")
        self.assertIn("210", h)
        self.assertNotIn("M104", h)

    def test_line_count(self) -> None:
        body = ";\nG28\nG1 X1 E1\n"
        ann = annotate_gcode_text(body)
        self.assertEqual(len(ann.splitlines()), len(body.splitlines()))


if __name__ == "__main__":
    unittest.main()
