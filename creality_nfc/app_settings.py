"""Persisted app settings (auto-tag, serial counter, reader)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class AppSettings:
    auto_read_tag: bool = True
    auto_write_tag: bool = False
    auto_increment_serial: bool = True
    next_serial: int = 1
    fixed_serial: str = "000001"
    preferred_reader: str = ""
    check_updates: bool = True
    last_uid_written: str = ""
    merge_prefer: str = "local"  # local | cloud
    batch_write_mode: bool = False
    poll_reader_sec: int = 8
    setup_completed: bool = False
    show_setup_on_startup: bool = False
    auto_sync_spool_on_tag: bool = True
    low_filament_threshold_g: int = 200
    prompt_deduct_after_print: bool = True
    default_post_print_deduct_g: int = 0
    # G-Code-Dateien, für die der Verbrauchs-Dialog schon erledigt/abgebrochen wurde.
    post_print_deduct_handled: list[str] = field(default_factory=list)
    protect_tag_overwrite: bool = True
    # Vor Druck automatisch CFS einfädeln (oft problematisch wenn schon geladen).
    cfs_auto_feed_before_print: bool = False
    # Hintergrund-Wächter: TD Filament Studio starten, wenn Creality Print startet.
    launch_with_creality_print: bool = False
    # Veraltet (ab 1.5.45): kein Upload mehr — nur Lesen vom Drucker.
    auto_push_db_to_printer: bool = False
    auto_push_options_with_db: bool = False
    auto_reboot_after_db_push: bool = False
    # Bekannte funktionierende Kamera-Snapshot-URL pro Drucker-IP (schnellerer Start).
    camera_snapshot_by_host: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> AppSettings:
        if not path.is_file():
            return cls()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
            filtered = {k: v for k, v in raw.items() if k in known}
            cam = filtered.get("camera_snapshot_by_host")
            if not isinstance(cam, dict):
                filtered["camera_snapshot_by_host"] = {}
            return cls(**filtered)
        except Exception:
            return cls()

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def next_serial_str(self) -> str:
        if self.auto_increment_serial:
            s = str(self.next_serial).zfill(6)[-6:]
            self.next_serial = (self.next_serial % 999999) + 1
            return s
        return self.fixed_serial.zfill(6)[-6:]

    def bump_serial(self) -> None:
        if self.auto_increment_serial:
            self.next_serial = (self.next_serial % 999999) + 1

    _MAX_POST_PRINT_HANDLED = 40

    def is_post_print_deduct_handled(self, filename: str) -> bool:
        fn = (filename or "").strip()
        return bool(fn) and fn in self.post_print_deduct_handled

    def remember_post_print_deduct(self, filename: str) -> None:
        fn = (filename or "").strip()
        if not fn:
            return
        kept = [x for x in self.post_print_deduct_handled if x != fn]
        kept.insert(0, fn)
        self.post_print_deduct_handled = kept[: self._MAX_POST_PRINT_HANDLED]


def _default_settings_path() -> Path:
    from app.paths import DATA_DIR

    return DATA_DIR / "app_settings.json"


DEFAULT_SETTINGS_PATH = _default_settings_path()
