"""Verbrauchsschätzung aus G-Code."""

import tempfile
import unittest
from pathlib import Path

from creality_nfc.gcode_filament import (
    parse_filament_grams_from_file,
    plausible_filament_grams,
    total_job_filament_grams,
)


class GcodeGramsTotalTests(unittest.TestCase):
    def test_ignore_tiny_metadata(self) -> None:
        self.assertIsNone(plausible_filament_grams(1.0))
        self.assertIsNone(plausible_filament_grams(3.0))
        self.assertEqual(plausible_filament_grams(42.0), 42.0)

    def test_total_from_header(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".gcode", delete=False, encoding="utf-8") as f:
            f.write("; total filament used [g] = 128.4\nG28\n")
            path = Path(f.name)
        try:
            state = {
                "retGcodeFileInfo2": [
                    {"name": path.name, "filamentWeight": "1.0", "material": "PETG"}
                ]
            }
            est = total_job_filament_grams(state, path.name, local_path=path)
            self.assertIsNotNone(est)
            assert est is not None
            self.assertEqual(est[0], 128)
        finally:
            path.unlink(missing_ok=True)

    def test_orca_colon_format(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".gcode", delete=False, encoding="utf-8") as f:
            f.write("; total filament weight [g] : 55.0\n")
            path = Path(f.name)
        try:
            self.assertAlmostEqual(parse_filament_grams_from_file(path), 55.0, places=1)
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
