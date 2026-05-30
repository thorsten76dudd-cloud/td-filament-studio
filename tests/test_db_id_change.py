"""Tests: Material-ID in DB ändern."""

import unittest

from creality_nfc.db_id_change import change_profile_filament_id, find_profile_index, id_collision


def _sample_db() -> dict:
    return {
        "result": {
            "list": [
                {
                    "base": {
                        "id": "06001",
                        "brand": "Creality",
                        "name": "CR-PETG",
                        "meterialType": "PETG",
                    },
                    "kvParam": {
                        "filament_notes": (
                            '{"id":"06001","vendor":"Creality","type":"PETG","name":"CR-PETG"}'
                        ),
                    },
                },
                {
                    "base": {
                        "id": "06001",
                        "brand": "Thorsten",
                        "name": "Thorsten PETG TD1000",
                        "meterialType": "PETG",
                    },
                },
            ],
            "count": 2,
        }
    }


class DbIdChangeTests(unittest.TestCase):
    def test_change_id_updates_base_and_notes(self) -> None:
        data = _sample_db()
        out = change_profile_filament_id(
            data,
            old_id="06001",
            brand="Thorsten",
            name="Thorsten PETG TD1000",
            new_id="06099",
        )
        idx = find_profile_index(
            out, filament_id="06099", brand="Thorsten", name="Thorsten PETG TD1000"
        )
        item = out["result"]["list"][idx]
        self.assertEqual(item["base"]["id"], "06099")
        still = find_profile_index(
            out, filament_id="06001", brand="Creality", name="CR-PETG"
        )
        self.assertEqual(out["result"]["list"][still]["base"]["id"], "06001")

    def test_collision_raises(self) -> None:
        data = _sample_db()
        with self.assertRaises(ValueError) as ctx:
            change_profile_filament_id(
                data,
                old_id="06001",
                brand="Thorsten",
                name="Thorsten PETG TD1000",
                new_id="06001",
            )
        self.assertIn("identisch", str(ctx.exception))

    def test_id_collision_detects_other_profile(self) -> None:
        data = _sample_db()
        hit = id_collision(data, "06001", brand="Thorsten", name="Thorsten PETG TD1000")
        self.assertEqual(hit, ("Creality", "CR-PETG"))


if __name__ == "__main__":
    unittest.main()
