"""App-wide constants."""

from app.paths import APP_DIR, DATA_DIR, ensure_data_dir

# Voll unterstützt: K2-RFID-Tags, CFS, WebSocket :9999, Material-DB (SSH/Cloud)
# Siehe README / Hilfe → „Unterstützte Drucker“
K2_CFS_PRINTERS: tuple[str, ...] = (
    "K2 Pro",
    "K2 Plus",
    "K2",
    "K2 Max",
    "K2 SE",
)

DEFAULT_PRINTER = "K2 Pro"

# Nur diese Modelle in Dropdowns (Drucker verwalten, RFID-Tab, …)
PRINTER_OPTIONS = K2_CFS_PRINTERS

SUPPORTED_PRINTERS_SHORT = (
    "Unterstützt: Creality K2 mit CFS — K2 Pro, K2 Plus, K2, K2 Max, K2 SE "
    "(RFID-Tags, Material-DB, Live-Steuerung)."
)

SKIP_DATA_JSON = frozenset({"printer_settings.json", "app_settings.json", "spools.json"})


def normalize_printer_model(label: str) -> str:
    """Unbekanntes/älteres Label auf ein unterstütztes K2-Modell abbilden."""
    s = (label or "").strip()
    if s in PRINTER_OPTIONS:
        return s
    low = s.lower().replace(" ", "")
    if "k2" not in low:
        return DEFAULT_PRINTER
    if "max" in low:
        return "K2 Max"
    if "plus" in low:
        return "K2 Plus"
    if "se" in low:
        return "K2 SE"
    if "pro" in low:
        return "K2 Pro"
    return "K2"


def is_supported_printer(label: str) -> bool:
    return normalize_printer_model(label) == (label or "").strip() and (label or "").strip() in PRINTER_OPTIONS


__all__ = [
    "APP_DIR",
    "DATA_DIR",
    "DEFAULT_PRINTER",
    "K2_CFS_PRINTERS",
    "PRINTER_OPTIONS",
    "SKIP_DATA_JSON",
    "SUPPORTED_PRINTERS_SHORT",
    "ensure_data_dir",
    "is_supported_printer",
    "normalize_printer_model",
]
