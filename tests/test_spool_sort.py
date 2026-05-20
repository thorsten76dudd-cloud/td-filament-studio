from creality_nfc.spool_inventory import Spool, SpoolInventory
from pathlib import Path
import tempfile


def test_sorted_spools_cfs_first_then_alpha():
    with tempfile.TemporaryDirectory() as tmp:
        inv = SpoolInventory(Path(tmp) / "spools.json")
        inv.spools = [
            Spool(id="a", label="Zebra", cfs_slot=None),
            Spool(id="b", label="Alpha", cfs_slot=2),
            Spool(id="c", label="Mittel", cfs_slot=None),
            Spool(id="d", label="Beta", cfs_slot=0),
        ]
        ordered = [s.id for s in inv.sorted_spools()]
        assert ordered == ["d", "b", "c", "a"]
