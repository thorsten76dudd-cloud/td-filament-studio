"""Beispiel-Links für RFID-Tags und NFC-Reader (z. B. Amazon)."""

from __future__ import annotations

from creality_nfc.i18n import t as _t

URL_AMAZON_ACR122U = "https://www.amazon.de/dp/B0DSC293JN"
URL_AMAZON_MF1_S50_TAGS = "https://www.amazon.de/dp/B0BL2YJ5GB"


def amazon_hardware_links() -> tuple[tuple[str, str, str], ...]:
    return (
        (
            _t("hw.reader_label"),
            _t("hw.reader_desc"),
            URL_AMAZON_ACR122U,
        ),
        (
            _t("hw.tags_title"),
            _t("hw.tags_label"),
            URL_AMAZON_MF1_S50_TAGS,
        ),
    )


AMAZON_HARDWARE_LINKS = amazon_hardware_links()


def hardware_shop_help_text() -> str:
    return _t(
        "hw.shop_help",
        reader=URL_AMAZON_ACR122U,
        tags=URL_AMAZON_MF1_S50_TAGS,
    )


HARDWARE_SHOP_HELP_TEXT = hardware_shop_help_text()
