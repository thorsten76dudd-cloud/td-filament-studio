"""Slicer-Profil-Import."""

import json
import tempfile
import unittest
from pathlib import Path

from creality_nfc.slicer_import import (
    collect_slicer_profiles_from_paths,
    parse_slicer_filament_json,
)


class SlicerImportTests(unittest.TestCase):
    def test_metadata_in_notes(self) -> None:
        data = {
            "type": "filament",
            "name": "ignored",
            "description": '{"id":"06099","vendor":"ELEGOO","type":"PETG","name":"Fast PETG"}',
            "nozzle_temperature": [240],
            "bed_temperature": [70],
        }
        p = parse_slicer_filament_json(data)
        self.assertIsNotNone(p)
        assert p is not None
        self.assertEqual(p.filament_id, "06099")
        self.assertEqual(p.brand, "ELEGOO")
        self.assertEqual(p.name, "Fast PETG")

    def test_collect_from_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "filament.json"
            path.write_text(
                json.dumps(
                    {
                        "type": "filament",
                        "name": "CR-PETG",
                        "filament_vendor": ["Creality"],
                        "filament_type": ["PETG"],
                        "nozzle_temperature": [250],
                    }
                ),
                encoding="utf-8",
            )
            found = collect_slicer_profiles_from_paths([path])
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0].material_type, "PETG")


if __name__ == "__main__":
    unittest.main()
