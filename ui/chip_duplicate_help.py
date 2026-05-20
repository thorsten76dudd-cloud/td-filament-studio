"""Texte für den Assistenten „Chip duplizieren“."""

CHIP_DUP_TOOLTIP = (
    "Kopiert einen funktionierenden Chip 1:1 auf einen zweiten Tag "
    "(z. B. links + rechts an der Spule). Jeder Chip hat eine eigene UID."
)

CHIP_DUP_INTRO = (
    "Chip duplizieren — Kurzanleitung\n"
    "================================\n\n"
    "Wofür?\n"
    "• Pro Spule oft 2 RFID-Sticker (links + rechts am Flansch)\n"
    "• Beide müssen dieselben Filament-Daten haben\n"
    "• Jeder Chip hat eine andere UID — die App speichert alle UIDs zur gleichen Spule\n\n"
    "Ablauf:\n"
    "1. Vorlagen-Chip auf den Reader legen (bereits beschrieben)\n"
    "2. Vorlagen-Chip wegnehmen\n"
    "3. Leeren/neuen Chip auflegen → bestätigen → wird kopiert\n"
    "4. Optional: weiteren Chip kopieren (z. B. andere Seite der Spule)\n\n"
    "Wichtig:\n"
    "• Quell-Chip zuerst unter „Meine Spulen“ speichern — sonst heißt der neue Chip "
    "„Nicht in Meine Spulen“ (Daten sind trotzdem auf dem Chip)\n"
    "• Gleiche UID wie die Vorlage = noch der alte Chip — wirklich wechseln\n"
    "• Tag flach und ruhig auf den ACR122U legen"
)

CHIP_DUP_STEP_HINTS: dict[str, str] = {
    "source": (
        "Schritt 1 von 2 — Vorlagen-Chip auf den Reader legen\n"
        "Der Chip wird automatisch gelesen (2× geprüft). "
        "Danach den Chip wegnehmen."
    ),
    "target": (
        "Schritt 2 von 2 — Neuen Chip auflegen (nicht derselbe wie eben)\n"
        "Es erscheint eine Frage „Jetzt kopieren?“ — mit Ja bestätigen. "
        "Für die zweite Spulenseite: Vorgang wiederholen."
    ),
}
