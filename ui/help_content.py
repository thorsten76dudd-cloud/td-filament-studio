"""Hilfetexte für TD Filament Studio."""

PROGRAM_HELP = """
TD FILAMENT STUDIO — Kurzanleitung
==================================

Überblick
---------
TD Filament Studio programmiert Creality K2/CFS RFID-Tags (MIFARE Classic) und verwaltet
die Material-Datenbank (material_database.json) auf dem Drucker.

Der RFID-Tag speichert NUR: Material-ID, Farbe, Gewichtsklasse, Seriennummer, Druckermodell.
Alle Druckparameter (Temperaturen, Flow, Retraction) liegen in der JSON-Datenbank
auf dem Drucker — nicht auf dem Tag.

Die Drucker-IP gilt für RFID-Tab, Tab „Drucker“ und SSH (ein Feld, überall gleich).


Benötigte Hardware & Tags (Einkaufsliste)
-----------------------------------------
Zum Beschreiben der RFID-Tags am PC brauchst du genau diese Kombination:

RFID-Tags (pro Spule)
• Chip-Typ: MIFARE Classic 1K (ISO 14443A) — oft verkauft als „MF1 S50“, „1K“, „M1“
• Form: runde Sticker/Scheiben, typisch 25 mm Durchmesser (1 Zoll)
• Nicht geeignet: NTAG213/215/216, NTAG2xx, reine UID-Tags ohne Classic-1K-Speicher
• Creality-Original-Tags an Spulen funktionieren; leere Nachbautag-Sticker ebenfalls
• Empfehlung: 2 Tags pro Spule (links + rechts am Flansch), beide gleich beschreiben
• Packungen „10 Stück × 2“ = 20 Sticker für 10 Spulen

NFC-Reader (am PC)
• USB-Reader mit PC/SC-Treiber, bewährt: ACS ACR122U (oder kompatibler Clone)
• Am PC per USB; LED leuchtet, Tag flach auflegen zum Lesen/Schreiben
• Unter Windows: Geräte-Manager → „Smartcard-Lesegeräte“ (wenn Treiber OK)
• iPhone/iPad: Tags können damit nicht beschrieben werden (kein Classic-1K-Zugriff)

Windows (Voraussetzung)
• Dienst „Smartcard“ (SCardSvr) muss laufen — siehe Abschnitt „Smartcard-Dienst“
• TD Filament Studio braucht kein Admin für normale Nutzung; nur zum Dienst-Start ggf. UAC

Optional
• 3D-Halter: „Tag-Halter STL speichern…“ (mitgeliefert) oder „Tag-Halter (Links)…“ im Tab RFID-Tag
• K2/CFS-Drucker + WLAN: nur für Material-DB und Live-Steuerung, nicht fürs Tag-Schreiben


Tab: RFID-Tag
-------------
Oben in der Aktionsleiste
• Große Zeile: Spulenname oder „Tag leer — bereit zum Schreiben“
• UID und Hinweis, ob die Spule in „Meine Spulen“ verknüpft ist

Reader & Tags
• Reader verbinden — ACR122U per USB; Smartcard-Dienst muss laufen (siehe unten).
  Ohne Tag auf dem Leser möglich; zum Lesen/Schreiben Tag flach auflegen.
• Smartcard starten / Neu starten (UAC) — wenn der Dienst aus oder hängt
• Tag lesen / Tag schreiben — mit Prüfung nach dem Schreiben (Dialog „fertig“)
• Tag-Schutz (Einstellungen): Warnung, wenn der Chip schon Filament-Daten hat
• Tag leeren… — Creality-Daten löschen; danach oft Blöcke C3B98E… in Rohdaten
  (verschlüsseltes Leer — normal). Tag 2–3 s abheben, wieder auflegen.
• Chip duplizieren… — Quell-Chip lesen, Ziel-Chip 1:1 kopieren; Ziel-UID wird
  ggf. an dieselbe Spule in „Meine Spulen“ gehängt (zweiter Sticker)
• Gleiche Spule nochmal — letztes Material erneut (Seriennummer +1)
• Tag export… — letzten Lesevorgang als JSON
• Presets / Farbe… / Foto… — Farbe für den Tag
• Spule speichern — Formular → „Meine Spulen“

Filament für den Tag (unten scrollen)
• Marke / Material — „Name · ID 12345“; darunter muss eine ID-Zeile erscheinen
• Tag schreiben am PC: Spule muss NICHT im CFS stecken — nur Material wählen
• Schnellweg: Tab „Meine Spulen“ → Spule wählen → „→ RFID-Tab“ (übernimmt Daten)
• Suchfeld leer lassen, sonst fehlt das Material in der Liste
• Spule mit Filament-ID kann geschrieben werden, auch ohne exakten DB-Eintrag
• Profil bearbeiten / Neues Profil… / Datenbank laden…
• Tag-Speicher… / „Jetzt vom Tag lesen“ — Rohdaten (Blöcke 0–15)

Automatik (Optionen)
• Auto lesen — Tag auflegen → Daten werden gelesen, Spule ggf. zugeordnet
• Auto schreiben — Tag auflegen → gewähltes Material wird geschrieben
• Spule in „Meine Spulen“ sync — nach jedem Tag-Schreiben Spule anlegen/aktualisieren (UID, Farbe, Material)
• Stapelmodus — für viele Tags hintereinander (siehe unten)
• Auto +1 — Seriennummer nach jedem Schreiben erhöhen

Stapelmodus (kurz)
------------------
Nur sinnvoll zusammen mit „Auto schreiben“.
1. Material wählen, Stapelmodus + Auto schreiben aktivieren.
2. Ersten Tag auf den Reader legen → wird beschrieben.
3. Status: „Tag OK — nächsten Tag auflegen“.
4. Tag wegnehmen, nächsten Tag auflegen → wieder automatisch schreiben.
Ohne Stapelmodus schreibt die App nur bei einer neuen Tag-UID (anderer Tag).


Tab: Filament-Profil
--------------------
Bearbeitung der Druckparameter in der Material-Datenbank (nicht auf dem RFID-Tag).
• Auswahl: Tab „RFID-Tag“ → Marke und Material (mit ID in der Liste)
• Tabs: Basis (ID, Marke, Name, Typ, Min/Max °C), Druckparameter, JSON (kvParam)
• „Vor Cloud/Drucker-Update schützen“ — eigene Temperaturen bleiben bei Cloud-Merge erhalten
• In Datenbank speichern — Änderungen in k2_pro.json (lokal), danach ggf. „Zum Drucker“

Wichtig: Mehrere Profile können dieselbe 5-stellige ID haben (z. B. drei× „06001“).
Immer das exakte Material in der Liste wählen (Name · ID), sonst falsche Temperaturen.


Tab: Material-Datenbank
-----------------------
• Cloud — offizielle Creality-Profile (Internet)
• Vom Drucker — per SSH vom K2 laden (Root aktivieren, gleiches WLAN)
• Zum Drucker — geänderte DB auf den K2 kopieren (danach Drucker neu starten)
• Merge Cloud — Cloud-Profile in lokale DB einfügen
• Slicer-Profile import… — Orca/Creality JSON (Notizen: {"id","vendor","type","name"})
• Drucker SSH — IP und Passwort im Tab
• Drucker-Dashboard — Status, DB vergleichen, material_options.json, Neustart

Menü „Datei“
• DB öffnen / speichern unter…
• material_options.json exportieren… — Markenliste fürs Display
• Daten sichern (ZIP)… / wiederherstellen… — kompletter data/-Ordner
• Einstellungen → Programm zurücksetzen… — alles löschen wie Neuinstallation (vorher ZIP!)
• CFS-RFID ZIP importieren… — Daten aus älterem CFS-RFID-Tool


Tab: Drucker
------------
Verbindung
• Verbinden — Live-WebSocket (Port 9999), wie Creality Print
• Beim Öffnen des Tabs und nach Start mit eingetragener IP oft automatisch
• Trennen — Verbindung beenden
• Live-Daten hängen? App verbindet nach einigen Sekunden ohne Antwort selbst neu
• Statuszeile unten: „Verbunden — IP“; Meldungen auch dort (nicht mehr dauerhaft schwarz)

G-Code
• Liste vom Drucker, Vorschaubild beim Anklicken
• Hochladen… — Datei vom PC auf den Drucker
• Herunterladen… — ausgewählte Datei auf den PC speichern
• Löschen — Datei auf dem Drucker entfernen
• Aktualisieren — Liste neu laden
• Druck starten: Creality Print oder Display am Drucker (nicht in TD Filament Studio)

Druck steuern (Monitor)
• Pause / Fortsetzen / Stopp — laufenden Job aus der App
• Fortsetzen nur nach Pause — neuen Job in Creality Print starten
• Verbrauch abziehen… — nach Druckende manuell (wenn kein Dialog kam)
• Nach Druckende erscheint oft automatisch „Filament-Verbrauch“ (Abbrechen / Abziehen)

Druck mit CFS
• Start und Farb-Matching: Creality Print (zuverlässiger als App-Druckstart)
• TD Studio: CFS-Slots anzeigen, Spule verknüpfen, manuell Zufuhr/Zurückziehen
• Fehler TR0116: Filament fehlt im Extruder → in Creality Print einfädeln
• Fehler FR0121: CFS-Filament im Extruder, Job für Spulenhalter gesliced
  → in Creality Print zurückziehen oder CFS im Slicer aktivieren

CFS-Anzeige (1A–1D)
• Farbige Kästchen = Filamentfarbe (schwarz, blau, weiß …), kein Status
• Oranger Rahmen = Filament „im Einsatz“ (Zufuhr / vom Drucker gemeldet)
• Text unten: „Im Einsatz: 1B“ usw.
• → RFID — Material des Slots in den RFID-Tab übernehmen
• Zufuhr / Zurückziehen — experimentell (Filament laden/entladen)
• ↻ — CFS-Daten neu anfordern

Kamera / Vorschau
• Live-Kamera — Bild in der Vorschau (auf jedem Monitor); „Vollbild“ = separates Edge-Fenster
• Klipper / Web-UI — Browser zu Moonraker/Klipper, falls aktiv

Steuerung & Temp
• Licht, Geschwindigkeit, Home XY/Z
• Düse, Bett, Kammer — Live-Anzeige; Zielwerte setzen
• Lüfter — Schieberegler + „Set“


Tab: Modell-Bibliothek
----------------------
Deine Projekte von Printables & Co.: STL/3MF, PDF-Anleitungen, Bilder — nicht vom Drucker.

• Ordner links — Unterordner, Umbenennen, Löschen (inkl. Inhalt), Pfad „Bibliothek / …“
• Überordner — eine Ebene nach oben springen
• Umbenennen — Ordner (links) oder Datei (oben / F2)
• In Ordner verschieben — Datei in anderen Ordner legen (oder per Drag & Drop: Datei auf Ordner ziehen)
• Datei importieren — oder vom Windows-Explorer auf den Tab ziehen (Drag & Drop)
• Unterstützt: STL, 3MF, PDF, Bilder, TXT …, ZIP (alles darin, mit Ordnern), ganze Ordner
• Verknüpfung — nur Pfad merken (Datei bleibt z. B. in Downloads)
• STL/3MF — „In Creality öffnen“ oder „3D-Viewer wählen…“ (Windows-Standard bzw. 3D Viewer / Paint 3D)
• Erledigt ✓ — Spalte „✓“ anklicken oder Haken in Details (grün = fertig/gedruckt, bleibt gespeichert)
• Details — Name, Quelle-URL, Bemerkung
• Suche / Nur offen — Dateiliste filtern
• Speichern unter… — eine Datei: Speicherdialog; mehrere (Strg+Klick): Zielordner wählen
• Im Explorer öffnen — Datei oder Ordner anzeigen


Tab: Meine Spulen
-----------------
Lokales Inventar (data/spools.json): Liste links, Bearbeitung rechts.
• Doppelklick oder „→ RFID-Tab“ — Spule für Tag-Schreiben übernehmen (wichtig:
  Filament-ID in der Spule hilft; danach „Tag schreiben“)
• CFS-Slot (1A–1D) — nur für Druck/Abzug, nicht Pflicht zum Tag-Beschreiben am PC
• RFID-Chips: Haupt-UID + weitere Chips; „Chip entfernen“ / „Alle trennen“
• Restgewicht, Verbrauch abziehen, Verlauf — Gramm werden protokolliert
• Duplizieren — Kopie einer Spule (neuer Tag möglich)
• Warnung — Rest unter Schwelle (Einstellungen) wird hervorgehoben

Tab: Drucker → Filament
-----------------------
• Live CFS 1A–1D mit Farbe und verknüpfter Spule aus „Meine Spulen“
• Spule — Slot einer Inventar-Spule zuweisen (automatisch per RFID-ID wenn möglich)
• RFID — Material vom Slot in den RFID-Tab übernehmen
• Nach Druckende — Verbrauch abfragen; Gramm aus Slicer-Kommentar (G-Code-Datei in data/gcode_cache/ oder Downloads)
• Unrealistische Drucker-Werte (<4 g) werden ignoriert — dann Slicer-Kopfzeile verwendet


Tab: Einstellungen
------------------
• Automatik (lesen, schreiben, Stapelmodus) — wie RFID-Tab
• Mit Creality Print starten — Hintergrund-Wächter öffnet TD Filament Studio, wenn Creality Print läuft
• Seriennummer — fest oder automatisch hochzählen
• NFC-Reader — bevorzugter Reader-Name (leer = erster gefundener)
• DB-Merge — bei Konflikt lokal oder Cloud behalten (geschützte Profile ausgenommen)
• Ersteinrichtung… — Checkliste beim ersten Start erneut anzeigen
• Spulen & CFS — Rest-Warnschwelle; Spule fest an 1A–1D verknüpfen für korrekten Abzug
• Nach Druck Filament abfragen — automatischer Abzugs-Dialog (Tab Einstellungen)
• Tag-Schutz — vor Überschreiben warnen (Tab Einstellungen)
• Mehrfarbig — mehrere Zeilen im Abzugs-Dialog (eine pro Farbe mit Verbrauch > 0 g)
• Updates beim Start prüfen — vergleicht mit GitHub-Releases deines Repos (Navigation → Nach Updates suchen)
• Fehlerprotokoll — data/app.log bei Abstürzen

Ersteinrichtung
---------------
Beim ersten Start: Checkliste (Smartcard, Reader, Datenbank, Tag-Typ).
„Fertig“ ohne „bei jedem Start anzeigen“ speichert den Abschluss in app_settings.json.


Tab: Hilfe
----------
• Programm-Anleitung — dieser Text
• JSON kvParam — alle Felder der Material-Datenbank (suchbar)
• G-Code M-Befehle — Referenz (Marlin/Klipper, Creality-Macros)


Statusleiste (unten)
--------------------
• Kurzmeldungen (Bereit, Verbunden, Fehler …)
• Protokoll — Meldungsverlauf ein- und ausblenden (optional)
• Einstellungen, Anleitung (Smartcard), Smartcard starten


Unterstützte Drucker
--------------------
TD Filament Studio ist für Creality K2 mit CFS ausgelegt (offenes K2-RFID-Format).

Voll unterstützt (RFID-Tags, CFS, Live-Steuerung WebSocket :9999, Material-DB):
• K2 Pro
• K2 Plus
• K2
• K2 Max
• K2 SE

Nicht unterstützt in dieser App (andere RFID-/UI-Welt):
• K1 / K1 Max / K1C / K1 SE
• Creality Hi / andere Hersteller ohne K2-CFS

In Dropdowns und „Drucker verwalten“ werden nur die K2-Modelle oben angeboten.


Drucker verwalten (Menü Extras)
-------------------------------
Mehrere Drucker speichern: Name, IP, Modell (nur K2-Liste), SSH-Passwort.
„Übernehmen“ setzt IP, Passwort und Modell in der App.


Smartcard-Dienst (Windows)
--------------------------
Ohne laufenden Dienst „Smartcard“ (SCardSvr) funktioniert kein NFC.
• Win+R → services.msc → Smartcard → Neu starten
• Oder in der Statusleiste: „Neu starten (UAC)“ / „Smartcard starten“
Der RFID-Reader ist nur zum Tag lesen/schreiben nötig — nicht für den Dienst-Test.


Drucker SSH (K2)
----------------
Benutzer: root
Standard-Passwort oft: creality_2024
Am Drucker: Einstellungen → Root-Konto aktivieren
Pfad DB: /mnt/UDISK/creality/userdata/box/material_database.json
Pfad Display-Menü: …/material_options.json (Markenliste auf dem Touchscreen)


RFID-Tag an der Spule
----------------------
• Chip auf den Flansch, ca. 25 mm vom Außenrand — nicht in die Mitte/Nabe
• 1 Tag reicht oft; empfohlen: 2 Tags (links + rechts), beide gleich beschreiben
• Am PC beschreiben: Material in der App wählen — Spule nicht im CFS nötig
• Zum Drucken: in der CFS einfädeln; RFID-Erkennung in Creality Print aktivieren
• Am PC: Tag flach auf den NFC-Reader zum Lesen/Schreiben

3D-Halter (Download)
--------------------
Tab RFID-Tag → „Tag-Halter STL speichern…“
Speichert die mitgelieferten STL (Deckel + Komponente 1–4) für 25-mm-MIFARE-Tags
an offiziellen Creality-Kunststoffspulen (pro Spule 2× komplett drucken).

Tab RFID-Tag → „Tag-Halter (Links)…“ (oder Navigation → Tag-Halter (Links)…)
Weitere Modelle im Browser (STL/3MF selbst herunterladen):

• Creality Spule Hex inkl. RFID-Fach — Printables (komplette Spule drucken)
  https://www.printables.com/model/1204576-creality-cfs-rfid-reusable-spool-hex

• Creality Kartonspulen (K2/CFS) — Printables (nur Karton, nicht Kunststoff)
  https://www.printables.com/model/1159112-k2-cfs-rdif-tag-holder-for-creality-cardboard-spoo

• Creality Cloud — Kartonspulen (3MF)
  https://www.crealitycloud.com/model-detail/rfid-cfs-tag-holders-cardboard-spools

• AMOYBABY / Flashforge-Spulen — Printables
  https://www.printables.com/model/1220708-creality-cfs-rfid-spool-tab

• Extrudr-Spulen — Printables
  https://www.printables.com/model/1151473-creality-cfs-rfid-tag-holder-for-extrudr-spools

• Universal (2× pro Spule, Aufkleben) — Printables
  https://www.printables.com/model/1280735-cfs-rfid-tag-for-spools

Pro Spule 2× drucken (PLA/PETG, 0,2 mm). Tag nach dem Beschreiben einsetzen oder kleben.


Updates (GitHub)
----------------
Navigation → „Nach Updates suchen“ oder Einstellungen → „Beim Start auf Updates prüfen“.

Die App fragt das neueste Release auf GitHub ab (Repo in creality_nfc/config.py:
GITHUB_RELEASES_REPO). Gibt es eine neuere Version als installiert, erscheint ein Dialog —
„Im Browser öffnen“ lädt die Release-Seite oder den direkten Download (Setup-EXE, falls
als Release-Asset hochgeladen).

Auf GitHub pro Version ein Release anlegen, Tag z. B. v1.5.31, Asset:
installer_output/TD-Filament-Studio-Setup.exe (oder dist/TD Filament Studio.exe).


Dateien (data/)
---------------
• k2_pro.json — Material-DB pro Druckermodell
• spools.json — Meine Spulen
• app_settings.json — App-Einstellungen
• printers.json — gespeicherte Drucker
• printer_settings.json — zuletzt gewählter Drucker
"""
