from creality_nfc.materials import FilamentProfile
from creality_nfc.spool_profile import profile_color_from_db, spool_fields_from_profile


def test_profile_color_from_kvparam():
    data = {
        "result": {
            "list": [
                {
                    "base": {"id": "101001", "brand": "Creality", "name": "Hyper PLA"},
                    "kvParam": {"default_filament_colour": "#1E90FF"},
                }
            ]
        }
    }
    p = FilamentProfile("101001", "Creality", "Hyper PLA", "PLA", "K2")
    assert profile_color_from_db(data, p) == "1E90FF"


def test_spool_fields_from_profile():
    data = {
        "result": {
            "list": [
                {
                    "base": {"id": "01001", "brand": "Generic", "name": "PLA"},
                    "kvParam": {"default_filament_colour": "0FF0000"},
                }
            ]
        }
    }
    p = FilamentProfile("01001", "Generic", "PLA", "PLA", "F008")
    fields = spool_fields_from_profile(p, data, current_label="Meine Spule")
    assert fields["label"] == "Generic — PLA"
    assert fields["brand"] == "Generic"
    assert fields["filament_id"] == "01001"
    assert fields["color_hex"] == "FF0000"
    assert fields["printer"] == "K2 Pro"
