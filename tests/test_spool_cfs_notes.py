from creality_nfc.spool_inventory import Spool, SpoolInventory, parse_cfs_slot_index
from pathlib import Path
import tempfile


def test_parse_cfs_slot_from_notes():
    assert parse_cfs_slot_index("CFS-S1") == 0
    assert parse_cfs_slot_index("CFS-S3") == 2
    assert parse_cfs_slot_index("CFS_S4") == 3
    assert parse_cfs_slot_index("1B") == 1
    assert parse_cfs_slot_index("") is None


def test_sorted_spools_uses_notes_cfs():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "spools.json"
        path.write_text(
            """{
  "version": 2,
  "spools": [
    {"id": "z", "label": "Zebra", "notes": ""},
    {"id": "s1", "label": "Orange", "notes": "CFS-S1"},
    {"id": "s3", "label": "Grey", "notes": "CFS-S3"}
  ]
}""",
            encoding="utf-8",
        )
        inv = SpoolInventory(path)
        ordered = [s.id for s in inv.sorted_spools()]
        assert ordered[0] == "s1"
        assert ordered[1] == "s3"
        assert ordered[2] == "z"
        assert inv.get("s1").cfs_slot == 0
