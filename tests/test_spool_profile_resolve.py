"""Spule → Filament-Profil für Tag-Schreiben."""

import unittest

from creality_nfc.materials import FilamentProfile, normalize_filament_id
from creality_nfc.spool_inventory import Spool
from creality_nfc.spool_profile import resolve_filament_profile


class SpoolProfileResolveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profiles = [
            FilamentProfile(
                filament_id="06001",
                brand="Creality",
                name="CR-PETG",
                material_type="PETG",
                printer="K2 Pro",
            ),
            FilamentProfile(
                filament_id="06002",
                brand="Creality",
                name="CR-PETG Blau",
                material_type="PETG",
                printer="K2 Pro",
            ),
        ]

    def test_by_filament_id(self) -> None:
        sp = Spool(
            id="1",
            label="Blau",
            brand="Creality",
            material_name="CR-PETG Blau",
            filament_id="06002",
        )
        p = resolve_filament_profile(sp, self.profiles)
        self.assertIsNotNone(p)
        assert p is not None
        self.assertEqual(normalize_filament_id(p.filament_id), "06002")

    def test_synthetic_when_id_not_in_db(self) -> None:
        sp = Spool(
            id="1",
            label="Grau",
            brand="Creality",
            material_name="CR-PETG Grau",
            filament_id="06099",
        )
        p = resolve_filament_profile(sp, [])
        self.assertIsNotNone(p)
        assert p is not None
        self.assertEqual(p.filament_id, "06099")

    def test_no_id_no_match(self) -> None:
        sp = Spool(id="1", label="Unbekannt", brand="X", material_name="Y")
        self.assertIsNone(resolve_filament_profile(sp, self.profiles))


if __name__ == "__main__":
    unittest.main()
