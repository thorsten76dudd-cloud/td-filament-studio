"""Tests: Material-DB-Einträge aus verschiedenen Creality-JSON-Formen."""

import unittest

from creality_nfc.materials import _identity_from_item, load_database_from_data


class MaterialsIdentityTests(unittest.TestCase):
    def test_standard_base(self) -> None:
        item = {
            "base": {"id": "06001", "brand": "Creality", "name": "CR-PETG", "meterialType": "PETG"},
            "printerIntName": "F008",
        }
        fid, brand, name, mtype = _identity_from_item(item)
        self.assertEqual(fid, "06001")
        self.assertEqual(brand, "Creality")
        self.assertEqual(name, "CR-PETG")
        self.assertEqual(mtype, "PETG")

    def test_metadata_name(self) -> None:
        item = {
            "base": {"id": "06002"},
            "metadata": {"name": "Mein PETG", "vendor": "Creality", "type": "PETG"},
        }
        profiles = load_database_from_data({"result": {"list": [item]}})
        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0].name, "Mein PETG")

    def test_notes_in_kvparam(self) -> None:
        item = {
            "base": {"brand": "Thorsten", "meterialType": "PETG"},
            "kvParam": {
                "filament_notes": (
                    '{"id":"06099","vendor":"Thorsten","type":"PETG","name":"Thorsten PETG TD1000"}'
                ),
            },
        }
        fid, brand, name, mtype = _identity_from_item(item)
        self.assertEqual(fid, "06099")
        self.assertEqual(name, "Thorsten PETG TD1000")
        self.assertEqual(mtype, "PETG")
        profiles = load_database_from_data({"result": {"list": [item]}})
        self.assertEqual(len(profiles), 1)


if __name__ == "__main__":
    unittest.main()
