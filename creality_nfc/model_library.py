"""Lokale STL/3MF-Sammlung mit Ordnern."""

from __future__ import annotations

import json
import shutil
import tempfile
import uuid
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


MODEL_EXT = {".stl", ".3mf"}
ATTACHMENT_EXT = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".bmp",
    ".txt",
    ".md",
    ".csv",
    ".json",
    ".gcode",
    ".bgcode",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".zip",
}
ALLOWED_EXT = MODEL_EXT | ATTACHMENT_EXT
ARCHIVE_EXT = {".zip"}


def _safe_zip_member(name: str) -> bool:
    parts = PurePosixPath(name.replace("\\", "/")).parts
    if not parts or parts[-1].startswith("."):
        return False
    if any(p in ("..", "") for p in parts):
        return False
    return PurePosixPath(name).suffix.lower() in ALLOWED_EXT


@dataclass
class ModelFolder:
    id: str
    name: str
    parent_id: str | None = None


@dataclass
class ModelEntry:
    id: str
    folder_id: str
    display_name: str
    storage: str  # copy | link
    rel_path: str = ""
    abs_path: str = ""
    source_url: str = ""
    notes: str = ""
    file_ext: str = ""
    added: str = field(default_factory=_now)
    done: bool = False

    def resolved_path(self, library_root: Path) -> Path | None:
        if self.storage == "link":
            p = Path(self.abs_path)
            return p if p.is_file() else None
        p = library_root / "files" / self.rel_path
        return p if p.is_file() else None


class ModelLibrary:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.index_path = root / "index.json"
        self.files_dir = root / "files"
        self.folders: list[ModelFolder] = []
        self.entries: list[ModelEntry] = []
        self.load()

    def load(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.files_dir.mkdir(parents=True, exist_ok=True)
        if not self.index_path.is_file():
            self.folders = [ModelFolder(id="root", name="Bibliothek", parent_id=None)]
            self.entries = []
            self.save()
            return
        try:
            raw = json.loads(self.index_path.read_text(encoding="utf-8"))
            self.folders = [ModelFolder(**row) for row in raw.get("folders", [])]
            self.entries = [ModelEntry(**row) for row in raw.get("entries", [])]
        except Exception:
            self.folders = [ModelFolder(id="root", name="Bibliothek", parent_id=None)]
            self.entries = []
        if not any(f.id == "root" for f in self.folders):
            self.folders.insert(0, ModelFolder(id="root", name="Bibliothek", parent_id=None))

    def save(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        data = {
            "version": 1,
            "folders": [asdict(f) for f in self.folders],
            "entries": [asdict(e) for e in self.entries],
        }
        self.index_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def folder_by_id(self, folder_id: str) -> ModelFolder | None:
        for f in self.folders:
            if f.id == folder_id:
                return f
        return None

    def child_folders(self, parent_id: str) -> list[ModelFolder]:
        pid = parent_id or "root"
        return sorted(
            [
                f
                for f in self.folders
                if f.id != "root" and (f.parent_id or "root") == pid
            ],
            key=lambda f: f.name.lower(),
        )

    def entries_in_folder(self, folder_id: str) -> list[ModelEntry]:
        return sorted(
            [e for e in self.entries if e.folder_id == folder_id],
            key=lambda e: e.display_name.lower(),
        )

    def ancestor_ids(self, folder_id: str) -> list[str]:
        chain: list[str] = []
        fid: str | None = folder_id
        while fid:
            chain.insert(0, fid)
            if fid == "root":
                break
            folder = self.folder_by_id(fid)
            if not folder:
                break
            pid = folder.parent_id or "root"
            if pid == fid:
                break
            fid = pid
        return chain

    def folder_breadcrumb(self, folder_id: str) -> str:
        parts: list[str] = []
        for fid in self.ancestor_ids(folder_id):
            folder = self.folder_by_id(fid)
            if folder:
                parts.append(folder.name)
        return " / ".join(parts) if parts else "Bibliothek"

    def subfolder_ids(self, folder_id: str) -> set[str]:
        found: set[str] = set()
        stack = [folder_id]
        while stack:
            pid = stack.pop()
            for child in self.child_folders(pid):
                if child.id in found:
                    continue
                found.add(child.id)
                stack.append(child.id)
        return found

    def entry_count(self, folder_id: str, *, include_subfolders: bool = False) -> int:
        if not include_subfolders:
            return len(self.entries_in_folder(folder_id))
        allowed = {folder_id} | self.subfolder_ids(folder_id)
        return sum(1 for e in self.entries if e.folder_id in allowed)

    def all_folders_for_picker(self) -> list[tuple[str, str]]:
        rows: list[tuple[str, str]] = []

        def walk(parent_id: str, depth: int) -> None:
            for folder in self.child_folders(parent_id):
                indent = "  " * depth
                rows.append((f"{indent}{folder.name}", folder.id))
                walk(folder.id, depth + 1)

        root = self.folder_by_id("root")
        rows.append((root.name if root else "Bibliothek", "root"))
        walk("root", 0)
        return rows

    def move_entry(self, entry_id: str, target_folder_id: str) -> bool:
        entry = self.get_entry(entry_id)
        if not entry:
            return False
        entry.folder_id = target_folder_id
        self.save()
        return True

    def folder_move_blocked(self, folder_id: str, new_parent_id: str) -> str | None:
        """Grund, warum ein Ordner nicht verschoben werden kann — sonst None."""
        if folder_id == "root":
            return "Bibliothek kann nicht verschoben werden."
        if folder_id == new_parent_id:
            return "Ordner ist bereits hier."
        if new_parent_id in self.subfolder_ids(folder_id):
            return "Ziel liegt im zu verschiebenden Ordner."
        if not self.folder_by_id(folder_id) or not self.folder_by_id(new_parent_id):
            return "Ordner nicht gefunden."
        return None

    def move_folder(self, folder_id: str, new_parent_id: str) -> bool:
        if self.folder_move_blocked(folder_id, new_parent_id):
            return False
        folder = self.folder_by_id(folder_id)
        if not folder:
            return False
        folder.parent_id = new_parent_id
        self.save()
        return True

    def get_or_create_subfolder(self, parent_id: str, name: str) -> str:
        """Unterordner mit Namen anlegen oder vorhandene ID zurückgeben."""
        clean = name.strip() or "Ordner"
        for child in self.child_folders(parent_id):
            if child.name.lower() == clean.lower():
                return child.id
        return self.add_folder(clean, parent_id).id

    def add_folder(self, name: str, parent_id: str = "root") -> ModelFolder:
        folder = ModelFolder(id=_new_id(), name=name.strip() or "Ordner", parent_id=parent_id)
        self.folders.append(folder)
        self.save()
        return folder

    def rename_folder(self, folder_id: str, name: str) -> None:
        f = self.folder_by_id(folder_id)
        if not f:
            return
        f.name = name.strip() or f.name
        self.save()

    def set_entry_done(self, entry_id: str, done: bool) -> bool:
        entry = self.get_entry(entry_id)
        if not entry:
            return False
        entry.done = done
        self.save()
        return True

    def rename_entry(self, entry_id: str, display_name: str) -> bool:
        entry = self.get_entry(entry_id)
        if not entry:
            return False
        entry.display_name = display_name.strip() or entry.display_name
        self.save()
        return True

    def delete_folder(self, folder_id: str) -> bool:
        if folder_id == "root":
            return False
        if self.child_folders(folder_id) or self.entries_in_folder(folder_id):
            return False
        self.folders = [f for f in self.folders if f.id != folder_id]
        self.save()
        return True

    def delete_folder_recursive(self, folder_id: str) -> int:
        """Ordner inkl. Unterordner und Dateien entfernen. Gibt Anzahl gelöschter Dateien zurück."""
        if folder_id == "root":
            return 0
        to_remove = {folder_id} | self.subfolder_ids(folder_id)
        removed = 0
        for entry in list(self.entries):
            if entry.folder_id in to_remove:
                self.delete_entry(entry.id)
                removed += 1
        self.folders = [f for f in self.folders if f.id not in to_remove]
        self.save()
        return removed

    def import_zip(self, src: Path, folder_id: str, *, notes: str = "", source_url: str = "") -> list[ModelEntry]:
        """STL/3MF aus ZIP extrahieren (inkl. Unterordner aus dem Archiv)."""
        if src.suffix.lower() not in ARCHIVE_EXT:
            raise ValueError("Nur .zip wird unterstützt.")
        if not src.is_file():
            raise FileNotFoundError(str(src))
        zip_note = notes.strip() or f"Aus ZIP: {src.name}"
        imported: list[ModelEntry] = []
        with zipfile.ZipFile(src, "r") as zf:
            members = sorted(
                n
                for n in zf.namelist()
                if _safe_zip_member(n) and not n.endswith("/")
            )
            if not members:
                raise ValueError(f"Keine unterstützten Dateien in „{src.name}“ gefunden.")
            for member in members:
                rel = PurePosixPath(member.replace("\\", "/"))
                if any(p.lower() == "__macosx" for p in rel.parts):
                    continue
                target_folder = folder_id
                for part in rel.parent.parts:
                    target_folder = self.get_or_create_subfolder(target_folder, part)
                suffix = rel.suffix.lower()
                with zf.open(member) as src_file:
                    data = src_file.read()
                tmp_path: Path | None = None
                try:
                    with tempfile.NamedTemporaryFile(
                        suffix=suffix,
                        delete=False,
                    ) as tmp:
                        tmp.write(data)
                        tmp_path = Path(tmp.name)
                    entry = self.import_file(
                        tmp_path,
                        target_folder,
                        notes=zip_note,
                        source_url=source_url,
                    )
                    entry.display_name = rel.stem
                    self.update_entry(entry)
                    imported.append(entry)
                finally:
                    if tmp_path and tmp_path.is_file():
                        try:
                            tmp_path.unlink()
                        except OSError:
                            pass
        return imported

    def import_file(self, src: Path, folder_id: str, *, notes: str = "", source_url: str = "") -> ModelEntry:
        ext = src.suffix.lower()
        if ext not in ALLOWED_EXT:
            raise ValueError(f"Dateityp „{ext}“ wird nicht unterstützt.")
        entry_id = _new_id()
        safe_name = f"{entry_id}{ext}"
        dest = self.files_dir / safe_name
        shutil.copy2(src, dest)
        entry = ModelEntry(
            id=entry_id,
            folder_id=folder_id,
            display_name=src.stem,
            storage="copy",
            rel_path=safe_name,
            source_url=source_url.strip(),
            notes=notes.strip(),
            file_ext=ext,
        )
        self.entries.append(entry)
        self.save()
        return entry

    def link_file(self, src: Path, folder_id: str, *, notes: str = "", source_url: str = "") -> ModelEntry:
        ext = src.suffix.lower()
        if ext not in ALLOWED_EXT:
            raise ValueError(f"Dateityp „{ext}“ wird nicht unterstützt.")
        if not src.is_file():
            raise FileNotFoundError(str(src))
        entry = ModelEntry(
            id=_new_id(),
            folder_id=folder_id,
            display_name=src.stem,
            storage="link",
            abs_path=str(src.resolve()),
            source_url=source_url.strip(),
            notes=notes.strip(),
            file_ext=ext,
        )
        self.entries.append(entry)
        self.save()
        return entry

    def update_entry(self, entry: ModelEntry) -> None:
        for i, e in enumerate(self.entries):
            if e.id == entry.id:
                self.entries[i] = entry
                self.save()
                return

    def delete_entry(self, entry_id: str) -> None:
        entry = self.get_entry(entry_id)
        if not entry:
            return
        if entry.storage == "copy" and entry.rel_path:
            p = self.files_dir / entry.rel_path
            if p.is_file():
                try:
                    p.unlink()
                except OSError:
                    pass
        self.entries = [e for e in self.entries if e.id != entry_id]
        self.save()

    def get_entry(self, entry_id: str) -> ModelEntry | None:
        for e in self.entries:
            if e.id == entry_id:
                return e
        return None

    def library_dir_for_folder(self, folder_id: str) -> Path:
        """Physischer Unterordner (optional für manuelle Ablage)."""
        d = self.root / "folders" / folder_id
        d.mkdir(parents=True, exist_ok=True)
        return d
