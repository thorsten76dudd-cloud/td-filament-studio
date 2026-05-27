"""One-off script to wire main_window.py strings to _t()."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
mw = ROOT / "app" / "main_window.py"
text = mw.read_text(encoding="utf-8")

pairs = [
    ('text="  Aktionen  "', 'text=_t("mw.ui.actions")'),
    ('text="— Tag auflegen oder „Tag lesen“ —"', 'text=_t("mw.spool.placeholder_read")'),
    ('text="UID"', 'text=_t("mw.ui.uid")'),
    ('text="Farbe…"', 'text=_t("mw.btn.color")'),
    ('text="Presets"', 'text=_t("mw.btn.presets")'),
    ('text="Foto…"', 'text=_t("mw.btn.photo")'),
    ('text="Tag lesen"', 'text=_t("mw.btn.read_tag")'),
    ('text="Tag schreiben"', 'text=_t("mw.btn.write_tag")'),
    ('text="Tag leeren…"', 'text=_t("mw.btn.format_tag")'),
    ('text="Chip duplizieren…"', 'text=_t("mw.btn.duplicate_chip")'),
    ('text="Tag export…"', 'text=_t("mw.btn.export_tag")'),
    ('text="Spule speichern"', 'text=_t("mw.btn.save_spool")'),
    ('text="Reader verbinden"', 'text=_t("mw.btn.connect_reader")'),
    ('text="Smartcard starten"', 'text=_t("mw.btn.smartcard_start")'),
    ('text="Tag-Speicher…"', 'text=_t("mw.btn.tag_memory")'),
    ('text="Gleiche Spule nochmal"', 'text=_t("mw.btn.same_spool_again")'),
    ('section(scroll, "NFC-Reader")', 'section(scroll, _t("mw.section.nfc_reader"))'),
    ('text="Profil bearbeiten"', 'text=_t("mw.btn.edit_profile")'),
    ('text="Neues Profil…"', 'text=_t("mw.btn.new_profile")'),
    ('text="Datenbank laden…"', 'text=_t("mw.btn.load_database")'),
    ('text="  Optionen  "', 'text=_t("mw.ui.options")'),
    ('text="Auto lesen"', 'text=_t("settings.auto_read")'),
    ('text="Auto schreiben"', 'text=_t("settings.auto_write")'),
    ('text="Stapelmodus"', 'text=_t("settings.batch_write")'),
    ('text="SN"', 'text=_t("mw.ui.sn")'),
    ('text="Auto +1"', 'text=_t("settings.auto_serial")'),
    ('text="Spule in „Meine Spulen“ sync"', 'text=_t("settings.auto_sync_spool")'),
    ('section(scroll, "Tag-Rohdaten (Reader-Auslesen)")', 'section(scroll, _t("mw.section.tag_raw"))'),
    ('text="Jetzt vom Tag lesen"', 'text=_t("mw.btn.read_now")'),
    ('section(top, "Material-Datenbank (nur vom Drucker)")', 'section(top, _t("mw.section.material_db_printer"))'),
    ('text="Lade…"', 'text=_t("mw.ui.db_loading")'),
    ('section(top, "Alle Material-Profile")', 'section(top, _t("mw.section.all_profiles"))'),
    ('text="0 Profile — Suche filtert die Liste"', 'text=_t("mw.ui.profile_list_empty")'),
    ('text="Doppelklick = RFID-Tag · Bearbeiten: Tab „Filament-Profil“"', 'text=_t("mw.ui.db_list_hint")'),
    ('text="Drucker & SSH →"', 'text=_t("mw.ui.goto_printer_ssh")'),
    ('text="Bereit"', 'text=_t("scard.state.ok")'),
    ('text="Ja"', 'text=_t("btn.yes")'),
    ('text="Nein"', 'text=_t("btn.no")'),
    ('text="Protokoll"', 'text=_t("statusbar.log")'),
    ('text="Protokoll ▾"', 'text=_t("statusbar.log") + " ▾"'),
    ('self.btn_scard.config(text="Smartcard starten")', 'self.btn_scard.config(text=_t("mw.btn.smartcard_start"))'),
    ('self.btn_scard.config(text="Neu starten (UAC)")', 'self.btn_scard.config(text=_t("mw.btn.smartcard_restart_uac"))'),
    ('_grid_row(0, "Drucker-IP"', '_grid_row(0, _t("mw.label.printer_ip")'),
    ('_grid_row(2, "Suche"', '_grid_row(2, _t("mw.label.search")'),
    ('_grid_row(3, "Drucker (am Tag)"', '_grid_row(3, _t("mw.label.printer_on_tag")'),
    ('_grid_row(5, "Marke"', '_grid_row(5, _t("mw.label.brand")'),
    ('_grid_row(6, "Material"', '_grid_row(6, _t("mw.label.material")'),
    ('_grid_row(7, "Profil"', '_grid_row(7, _t("mw.label.profile")'),
    ('_grid_row(8, "Gewicht (Tag)"', '_grid_row(8, _t("mw.label.weight_tag")'),
    ('_grid_row(9, "Meine Spule"', '_grid_row(9, _t("mw.label.my_spool")'),
    ('text="→ Tab Filament-Profil (Druckparameter)"', 'text=_t("mw.label.goto_profile_tab")'),
    ('text="Automatisch"', 'text=_t("mw.btn.auto")'),
    ('text="Zuweisen"', 'text=_t("mw.btn.assign")'),
    ('text="Gramm:"', 'text=_t("deduct.grams")'),
    ('text="Abbrechen"', 'text=_t("btn.cancel")'),
    ('text="Abziehen"', 'text=_t("deduct.btn_apply")'),
    ('text="Datenbank: …"', 'text=_t("mw.ui.database_loading")'),
    ('"Vom Drucker (SSH)"', '_t("mw.db.from_printer_ssh")'),
    ('"CFS-RFID ZIP…"', '_t("mw.db.cfs_zip")'),
    ('"Von Creality Cloud"', '_t("mw.db.from_cloud")'),
    ('"Cloud mergen"', '_t("mw.db.cloud_merge")'),
    ('"Slicer-Profile import…"', '_t("mw.db.slicer_import")'),
    ('"DB speichern…"', '_t("mw.db.save_as")'),
]

notify_pairs = [
    ('self.notify("Einstellungen gespeichert", "ok")', 'self.notify(_t("mw.notify.settings_saved"), "ok")'),
    (
        'self.notify("Smartcard-Anleitung — Tab „Hilfe“ → Programm-Anleitung", "info")',
        'self.notify(_t("mw.notify.smartcard_help"), "info")',
    ),
    ('self.notify("Smartcard-Dienst aus", "warn")', 'self.notify(_t("mw.notify.smartcard_off"), "warn")'),
    ('title="NFC-Reader"', 'title=_t("mw.notify.title_nfc")'),
    ('title="NFC"', 'title=_t("mw.notify.title_nfc_short")'),
    (
        'self.notify("Creality-Cloud-Import ist deaktiviert — nur „Vom Drucker“.", "warn")',
        'self.notify(_t("mw.notify.cloud_import_disabled"), "warn")',
    ),
    (
        'self.notify("Cloud-Merge ist deaktiviert — nur „Vom Drucker“.", "warn")',
        'self.notify(_t("mw.notify.cloud_merge_disabled"), "warn")',
    ),
    (
        'self.notify("Datei-Import ist deaktiviert — nur „Vom Drucker (SSH)“.", "warn")',
        'self.notify(_t("mw.notify.file_import_disabled"), "warn")',
    ),
    (
        'self.notify("Slicer-Import ist deaktiviert — nur „Vom Drucker (SSH)“.", "warn")',
        'self.notify(_t("mw.notify.slicer_import_disabled"), "warn")',
    ),
    (
        'self.notify("„DB speichern unter“ ist deaktiviert — nur „Vom Drucker (SSH)“.", "warn")',
        'self.notify(_t("mw.notify.save_db_disabled"), "warn")',
    ),
    (
        'self.notify("Neue Profile nur am Drucker / in Creality Print — nicht in TD Studio.", "warn")',
        'self.notify(_t("mw.notify.new_profiles_printer_only"), "warn")',
    ),
    ('self.notify("Bitte Gramm als Zahl eingeben.", "warn")', 'self.notify(_t("mw.notify.enter_grams_number"), "warn")'),
    (
        'self.notify("Keine Spulen in „Meine Spulen“ — bitte zuerst anlegen.", "warn")',
        'self.notify(_t("mw.notify.no_spools_create_first"), "warn")',
    ),
    (
        'self.notify("Noch kein Tag geschrieben — zuerst einmal „Tag schreiben“.", "warn")',
        'self.notify(_t("notify.tag_template_missing"), "warn")',
    ),
    ('self.notify("UAC-Dialog fehlgeschlagen.", "error")', 'self.notify(_t("mw.notify.uac_failed"), "error")'),
    ('self.notify("Bereit — NFC-Reader erkannt.", "ok")', 'self.notify(_t("mw.notify.reader_ready"), "ok")'),
    (
        'self.notify("Material geladen — neuen Tag auflegen und „Tag schreiben“.", "ok")',
        'self.notify(_t("mw.notify.material_loaded_rewrite"), "ok")',
    ),
    (
        'self.notify("Zuerst „Tag lesen“ — dann kann exportiert werden.", "warn")',
        'self.notify(_t("mw.notify.read_before_export"), "warn")',
    ),
    (
        'self.notify("Einstellungen — Tab „Einstellungen“ oben", "info")',
        'self.notify(_t("mw.notify.open_settings_tab"), "info")',
    ),
    (
        'self.notify("Tab „Drucker“ ist noch nicht bereit — bitte kurz warten.", "warn")',
        'self.notify(_t("mw.notify.printer_tab_not_ready"), "warn")',
    ),
    (
        'self.notify("CFS-Vorschau beendet — wieder echte CFS-Daten vom Drucker.", "ok")',
        'self.notify(_t("mw.notify.cfs_preview_ended"), "ok")',
    ),
    (
        'self.notify("Tray-Symbol konnte nicht gestartet werden.", "warn")',
        'self.notify(_t("mw.notify.tray_start_failed"), "warn")',
    ),
    (
        'self.spool_match_label.config(text="Tag leer — bereit zum Schreiben"',
        'self.spool_match_label.config(text=_t("mw.tag.empty_ready")',
    ),
    ('self.notify(f"Druck beendet: {fn}", "ok")', 'self.notify(_t("notify.print_finished", filename=fn), "ok")'),
    (
        'self.notify(f"{label}… (kann 1–2 Minuten dauern)", "info")',
        'self.notify(_t("mw.notify.task_duration", label=label), "info")',
    ),
    ('self.notify(f"{label} abgeschlossen.", "ok")', 'self.notify(_t("mw.notify.task_done", label=label), "ok")'),
    (
        'self.notify(f"RFID-Tag: {profile.brand} — {profile.name}", "ok")',
        'self.notify(_t("mw.notify.rfid_tag_profile", brand=profile.brand, name=profile.name), "ok")',
    ),
    (
        'self.notify(f"Drucker-Einstellungen nicht gespeichert: {exc}", "warn")',
        'self.notify(_t("mw.notify.printer_settings_not_saved", exc=exc), "warn")',
    ),
    (
        'self.notify(f"Verbrauch abgezogen ({len(deductions)} Spule(n)).", "ok")',
        'self.notify(_t("mw.notify.deduct_done", n=len(deductions)), "ok")',
    ),
    (
        'self.notify(f"Farbe aus Foto: #{hex_code}", "ok")',
        'self.notify(_t("mw.notify.color_from_photo", hex_code=hex_code), "ok")',
    ),
    (
        'self.notify(f"Tag-Daten gespeichert:\\n{path}", "ok")',
        'self.notify(_t("mw.notify.tag_exported", path=path), "ok")',
    ),
    (
        'self.notify(f"IP {p.host} · Modell {p.model}", "ok")',
        'self.notify(_t("mw.notify.printer_ip_model", host=p.host, model=p.model), "ok")',
    ),
    (
        'self.notify(f"{n} Dateien wiederhergestellt. App neu starten empfohlen.", "ok")',
        'self.notify(_t("mw.notify.restore_count", n=n), "ok")',
    ),
    (
        'self._set_status("Smartcard OK — Reader per USB verbinden")',
        'self._set_status(_t("mw.notify.smartcard_ok_connect_usb"))',
    ),
    (
        'self._set_status("Duplizieren Schritt 1/2: Vorlagen-Chip auflegen …")',
        'self._set_status(_t("mw.notify.dup_step1_status"))',
    ),
    (
        'self._tag_finished("Schritt 1 fertig — Vorlage gelesen"',
        'self._tag_finished(_t("mw.notify.dup_step1_done")',
    ),
    (
        'self.notify("Reader nicht bereit — Vorgang abgebrochen.", "warn")',
        'self.notify(_t("mw.notify.reader_not_ready_abort"), "warn")',
    ),
    (
        'self.notify("Lesen fehlgeschlagen — Tag auflegen und erneut versuchen.", "warn")',
        'self.notify(_t("mw.notify.read_failed"), "warn")',
    ),
    ('self.notify("Reader nicht bereit.", "warn")', 'self.notify(_t("mw.notify.reader_not_ready"), "warn")'),
    ('colorchooser.askcolor(title="Filamentfarbe")', 'colorchooser.askcolor(title=_t("mw.color.title"))'),
]

missing = []
for old, new in pairs + notify_pairs:
    if old not in text:
        missing.append(old[:70])
    else:
        text = text.replace(old, new)

if missing:
    print("MISSING", len(missing))
    for m in missing:
        print(" ", m)
else:
    print("All replacements applied")

mw.write_text(text, encoding="utf-8")
