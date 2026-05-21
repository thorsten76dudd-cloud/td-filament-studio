"""Beispiel-Links für RFID-Tags und NFC-Reader (z. B. Amazon)."""

from __future__ import annotations

# Kurz-URLs ohne Tracking-Parameter
URL_AMAZON_ACR122U = "https://www.amazon.de/dp/B0DSC293JN"
URL_AMAZON_MF1_S50_TAGS = "https://www.amazon.de/dp/B0BL2YJ5GB"

# (Titel, Beschreibung, URL)
AMAZON_HARDWARE_LINKS: tuple[tuple[str, str, str], ...] = (
    (
        "NFC-Lesegerät (ACR122U-kompatibel)",
        "Ieron RFID/NFC Reader ACR122U, ISO 14443A/B — am PC mit Smartcard-Dienst.",
        URL_AMAZON_ACR122U,
    ),
    (
        "RFID-Tags (MF1 S50, 25 mm)",
        "YARONGTECH MIFARE Classic 1K Sticker, 13,56 MHz, Durchmesser 25 mm (10 Stück).",
        URL_AMAZON_MF1_S50_TAGS,
    ),
)

HARDWARE_SHOP_HELP_TEXT = """
Beispiel-Produkte (vom Entwickler getestet/gekauft, keine Werbung):
• NFC-Reader: Ieron ACR122U-kompatibel — {reader}
• RFID-Tags: YARONGTECH MF1 S50, 25 mm — {tags}

Andere Marken mit gleichem Chip-Typ (MIFARE Classic 1K) und ACR122U-Clones funktionieren meist ebenfalls.
""".format(reader=URL_AMAZON_ACR122U, tags=URL_AMAZON_MF1_S50_TAGS).strip()
