"""Tests: G-Code-Pfade auf dem K2 (usr/data vs. UDISK)."""

import unittest

from creality_nfc.printer_ssh import _gcode_path_candidates


class GcodePathCandidatesTests(unittest.TestCase):
    def test_includes_both_roots_for_usr_path(self) -> None:
        remote = "/usr/data/printer_data/gcodes/part.gcode"
        paths = _gcode_path_candidates(remote)
        self.assertIn(remote, paths)
        self.assertIn("/mnt/UDISK/printer_data/gcodes/part.gcode", paths)

    def test_name_only_gets_both_dirs(self) -> None:
        paths = _gcode_path_candidates("/usr/data/printer_data/gcodes/foo.gcode")
        self.assertGreaterEqual(len(paths), 2)


if __name__ == "__main__":
    unittest.main()
