"""Material-Datenbank und Box-Dateien vom K2/K1 per SSH."""

from __future__ import annotations

import json
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

BOX_DIR_CANDIDATES = (
    "/mnt/UDISK/creality/userdata/box",
    "/usr/data/creality/userdata/box",
)
REMOTE_OPTIONS_NAME = "material_options.json"
REMOTE_DB_NAME = "material_database.json"
GCODE_REMOTE_DIR = "/usr/data/printer_data/gcodes"
GCODE_DIR_CANDIDATES = (
    GCODE_REMOTE_DIR,
    "/mnt/UDISK/printer_data/gcodes",
)

DEFAULT_PASSWORDS = {
    "k2": "creality_2024",
    "k1": "creality_2023",
    "hi": "creality_2024",
}


def normalize_host(host: str) -> str:
    h = host.strip()
    for prefix in ("https://", "http://"):
        if h.lower().startswith(prefix):
            h = h[len(prefix) :]
    h = h.split("/")[0].strip()
    return h


def default_password(printer_label: str) -> str:
    low = printer_label.lower()
    if "k1" in low:
        return DEFAULT_PASSWORDS["k1"]
    if "hi" in low:
        return DEFAULT_PASSWORDS["hi"]
    return DEFAULT_PASSWORDS["k2"]


def remote_db_path(printer_label: str) -> str:
    """Legacy-Pfad-Hinweis; echte Pfade via resolve_box_dir."""
    if "k1" in printer_label.lower() and "k2" not in printer_label.lower():
        return f"{BOX_DIR_CANDIDATES[1]}/{REMOTE_DB_NAME}"
    return f"{BOX_DIR_CANDIDATES[0]}/{REMOTE_DB_NAME}"


def remote_options_path(printer_label: str) -> str:
    if "k1" in printer_label.lower() and "k2" not in printer_label.lower():
        return f"{BOX_DIR_CANDIDATES[1]}/{REMOTE_OPTIONS_NAME}"
    return f"{BOX_DIR_CANDIDATES[0]}/{REMOTE_OPTIONS_NAME}"


@contextmanager
def ssh_client(
    host: str,
    password: str,
    username: str = "root",
    port: int = 22,
) -> Iterator:
    try:
        import paramiko
    except ImportError as exc:
        raise RuntimeError("Paket 'paramiko' fehlt. Bitte: pip install paramiko") from exc

    host = normalize_host(host)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        host,
        port=port,
        username=username,
        password=password,
        timeout=15,
        allow_agent=False,
        look_for_keys=False,
    )
    try:
        yield client
    finally:
        client.close()


def _read_remote_file(client, path: str) -> bytes:
    sftp = client.open_sftp()
    try:
        with sftp.open(path, "rb") as remote:
            return remote.read()
    finally:
        sftp.close()


def _write_remote_file(client, path: str, payload: bytes) -> None:
    sftp = client.open_sftp()
    try:
        with sftp.open(path, "wb") as remote:
            remote.write(payload)
    finally:
        sftp.close()


def _run_command(client, command: str, timeout: float = 12.0) -> tuple[int, str, str]:
    _stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    code = stdout.channel.recv_exit_status()
    return code, out, err


def resolve_box_dir(client) -> str:
    """Findet den box-Ordner anhand von material_database.json."""
    for box in BOX_DIR_CANDIDATES:
        code, out, _ = _run_command(
            client,
            f"test -f '{box}/{REMOTE_DB_NAME}' && echo OK",
        )
        if code == 0 and "OK" in out:
            return box

    code, out, _ = _run_command(
        client,
        "find /mnt /usr /oem /data -name 'material_database.json' 2>/dev/null | head -5",
        timeout=25.0,
    )
    if code == 0 and out:
        for line in out.splitlines():
            path = line.strip()
            if path.endswith(REMOTE_DB_NAME):
                return path[: -len(REMOTE_DB_NAME)].rstrip("/")

    listing = []
    for box in BOX_DIR_CANDIDATES:
        code, out, _ = _run_command(client, f"ls -1 '{box}' 2>/dev/null | head -20")
        if code == 0 and out:
            listing.append(f"{box}:\n  " + "\n  ".join(out.splitlines()))
    detail = "\n".join(listing) if listing else "Keine Kandidaten lesbar."
    raise RuntimeError(
        "material_database.json nicht gefunden.\n"
        f"Geprüft:\n  " + "\n  ".join(BOX_DIR_CANDIDATES) + f"\n\nInhalt:\n{detail}"
    )


def list_box_files(
    host: str,
    password: str,
    printer_label: str = "K2 Pro",
    username: str = "root",
    port: int = 22,
) -> tuple[str, list[str]]:
    host = normalize_host(host)
    with ssh_client(host, password, username, port) as client:
        box = resolve_box_dir(client)
        code, out, err = _run_command(client, f"ls -la '{box}'")
        if code != 0:
            raise RuntimeError(err or f"ls fehlgeschlagen: {box}")
        names = []
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 9 and not parts[0].startswith("d"):
                names.append(parts[-1])
            elif line and not line.startswith("total"):
                m = re.search(r"\S+$", line)
                if m:
                    names.append(m.group(0))
        return box, sorted(set(names))


def download_database_from_printer(
    host: str,
    password: str,
    printer_label: str,
    username: str = "root",
    port: int = 22,
) -> dict:
    del printer_label
    host = normalize_host(host)
    with ssh_client(host, password, username, port) as client:
        box = resolve_box_dir(client)
        path = f"{box}/{REMOTE_DB_NAME}"
        raw = _read_remote_file(client, path)
    if not raw:
        raise RuntimeError(f"Leere Datei: {path}")
    data = json.loads(raw.decode("utf-8", errors="replace"))
    lst = data.get("result", {}).get("list") if isinstance(data.get("result"), dict) else None
    if not lst and isinstance(data.get("list"), list):
        data = {"code": 0, "msg": "ok", "result": {"list": data["list"]}}
        lst = data["result"]["list"]
    if not lst:
        raise RuntimeError(
            f"Keine Material-Profile in {path}.\n"
            "Erwartet: JSON mit result.list (Creality material_database.json)."
        )
    return data


def upload_database_to_printer(
    host: str,
    password: str,
    printer_label: str,
    data: dict,
    username: str = "root",
    port: int = 22,
) -> None:
    del printer_label
    host = normalize_host(host)
    payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
    with ssh_client(host, password, username, port) as client:
        box = resolve_box_dir(client)
        _write_remote_file(client, f"{box}/{REMOTE_DB_NAME}", payload)


def list_gcode_files_ssh(
    host: str,
    password: str,
    *,
    username: str = "root",
    port: int = 22,
) -> list[dict[str, Any]]:
    """G-Code-Dateien per SSH/SFTP (Fallback wenn WebSocket-Liste leer)."""
    host = normalize_host(host)
    found: dict[str, dict[str, Any]] = {}
    with ssh_client(host, password, username, port) as client:
        sftp = client.open_sftp()
        for directory in GCODE_DIR_CANDIDATES:
            try:
                for name in sftp.listdir(directory):
                    if not str(name).lower().endswith(".gcode"):
                        continue
                    remote = f"{directory}/{name}"
                    try:
                        attr = sftp.stat(remote)
                        mtime = float(attr.st_mtime)
                        size = int(attr.st_size)
                    except OSError:
                        mtime = None
                        size = None
                    found[str(name)] = {
                        "name": str(name),
                        "path": remote,
                        "size": size,
                        "mtime": mtime,
                    }
            except OSError:
                continue
    files = list(found.values())
    files.sort(key=lambda f: (-(f.get("mtime") or 0.0), f.get("name", "").lower()))
    return files


def _gcode_path_candidates(remote: str) -> list[str]:
    remote = remote.strip().replace("\\", "/")
    paths: list[str] = []
    if remote:
        paths.append(remote)
    name = remote.rsplit("/", 1)[-1] if remote else ""
    for directory in GCODE_DIR_CANDIDATES:
        if name:
            candidate = f"{directory}/{name.lstrip('/')}"
            if candidate not in paths:
                paths.append(candidate)
    if remote.startswith(GCODE_REMOTE_DIR):
        alt = remote.replace(GCODE_REMOTE_DIR, GCODE_DIR_CANDIDATES[1], 1)
        if alt not in paths:
            paths.append(alt)
    elif remote.startswith(GCODE_DIR_CANDIDATES[1]):
        alt = remote.replace(GCODE_DIR_CANDIDATES[1], GCODE_REMOTE_DIR, 1)
        if alt not in paths:
            paths.append(alt)
    return paths


def _pick_largest_gcode_remote(sftp, remote: str) -> tuple[str, int]:
    """K2: gleicher Name in usr/data und UDISK — größte Datei = vollständiger G-Code."""
    best_path = ""
    best_size = -1
    last_err: OSError | None = None
    for path in _gcode_path_candidates(remote):
        try:
            size = int(sftp.stat(path).st_size)
        except OSError as exc:
            last_err = exc
            continue
        if size > best_size:
            best_size = size
            best_path = path
    if not best_path or best_size < 0:
        raise FileNotFoundError(
            f"G-Code auf dem Drucker nicht gefunden: {remote}"
        ) from last_err
    return best_path, best_size


def _sftp_download(client, remote: str, local: Path) -> None:
    sftp = client.open_sftp()
    try:
        best_path, expected = _pick_largest_gcode_remote(sftp, remote)
        sftp.get(best_path, str(local))
        got = local.stat().st_size
        if got != expected:
            raise OSError(
                f"Download unvollständig ({got:,} von {expected:,} Bytes): {best_path}"
            )
    finally:
        sftp.close()


def download_gcode_from_printer(
    host: str,
    password: str,
    remote_path: str,
    local_path: str | Path,
    *,
    username: str = "root",
    port: int = 22,
) -> Path:
    """G-Code vom Drucker per SFTP speichern."""
    local = Path(local_path)
    remote = remote_path.strip().replace("\\", "/")
    if not remote:
        raise ValueError("Kein Drucker-Pfad.")
    host = normalize_host(host)
    with ssh_client(host, password, username, port) as client:
        _sftp_download(client, remote, local)
    return local


def delete_gcode_on_printer_ssh(
    host: str,
    password: str,
    remote_path: str,
    *,
    username: str = "root",
    port: int = 22,
) -> None:
    """G-Code auf dem Drucker löschen (SFTP rm)."""
    remote = remote_path.strip().replace("\\", "/")
    if not remote:
        raise ValueError("Kein Drucker-Pfad.")
    host = normalize_host(host)
    with ssh_client(host, password, username, port) as client:
        sftp = client.open_sftp()
        removed = False
        last_err: Exception | None = None
        try:
            for path in _gcode_path_candidates(remote):
                try:
                    sftp.remove(path)
                    removed = True
                    break
                except OSError as exc:
                    last_err = exc
        finally:
            sftp.close()
        if not removed:
            raise FileNotFoundError(f"Datei nicht gefunden: {remote}") from last_err


def upload_gcode_to_printer(
    host: str,
    password: str,
    local_path: str | Path,
    *,
    remote_name: str | None = None,
    username: str = "root",
    port: int = 22,
) -> str:
    """G-Code per SFTP nach gcodes/ — gibt Drucker-Pfad zurück."""
    path = Path(local_path)
    if not path.is_file():
        raise FileNotFoundError(f"Datei nicht gefunden: {path}")
    name = (remote_name or path.name).strip()
    if not name.lower().endswith(".gcode"):
        raise ValueError("Nur .gcode-Dateien können hochgeladen werden.")
    data = path.read_bytes()
    if len(data) < 64:
        raise ValueError("Datei ist zu klein für G-Code.")

    host = normalize_host(host)
    remote = f"{GCODE_REMOTE_DIR}/{name}"
    with ssh_client(host, password, username, port) as client:
        _run_command(client, f"mkdir -p '{GCODE_REMOTE_DIR}'")
        _write_remote_file(client, remote, data)
    return remote


def download_options_from_printer(
    host: str,
    password: str,
    printer_label: str,
    username: str = "root",
    port: int = 22,
) -> dict:
    del printer_label
    host = normalize_host(host)
    with ssh_client(host, password, username, port) as client:
        box = resolve_box_dir(client)
        path = f"{box}/{REMOTE_OPTIONS_NAME}"
        try:
            raw = _read_remote_file(client, path)
        except (OSError, IOError) as exc:
            files: list[str] = []
            try:
                _, files = list_box_files(host, password, username=username, port=port)
            except Exception:
                pass
            hint = (
                f"Datei fehlt: {path}\n"
                f"Dateien im Ordner: {', '.join(files) or '—'}\n\n"
                "Am K2 gibt es oft nur material_database.json.\n"
                "Nutze „Options zum Drucker“ — die Datei wird neu erzeugt."
            )
            raise RuntimeError(hint) from exc
    if not raw:
        raise RuntimeError(f"Leere Datei: {path}")
    return json.loads(raw.decode("utf-8", errors="replace"))


def upload_options_to_printer(
    host: str,
    password: str,
    printer_label: str,
    options: dict,
    username: str = "root",
    port: int = 22,
) -> None:
    del printer_label
    host = normalize_host(host)
    payload = json.dumps(options, ensure_ascii=False, indent=2).encode("utf-8")
    with ssh_client(host, password, username, port) as client:
        box = resolve_box_dir(client)
        _write_remote_file(client, f"{box}/{REMOTE_OPTIONS_NAME}", payload)


def fetch_printer_info(
    host: str,
    password: str,
    printer_label: str,
    username: str = "root",
    port: int = 22,
) -> dict[str, str]:
    del printer_label
    host = normalize_host(host)
    info: dict[str, str] = {"host": host}

    with ssh_client(host, password, username, port) as client:
        box = resolve_box_dir(client)
        info["box_dir"] = box

        _, hostname, _ = _run_command(client, "hostname")
        info["hostname"] = hostname or "—"

        _, uname, _ = _run_command(client, "uname -a")
        info["system"] = (uname[:120] if uname else "—")

        code, df_out, _ = _run_command(client, f"df -h '{box}' 2>/dev/null | tail -1")
        info["disk"] = df_out if code == 0 and df_out else "—"

        try:
            raw = _read_remote_file(client, f"{box}/{REMOTE_DB_NAME}")
            data = json.loads(raw.decode("utf-8", errors="replace"))
            info["profile_count"] = str(len(data.get("result", {}).get("list", [])))
        except Exception:
            info["profile_count"] = "?"

        for name in (REMOTE_DB_NAME, REMOTE_OPTIONS_NAME):
            code, size_out, _ = _run_command(client, f"wc -c < '{box}/{name}' 2>/dev/null")
            if code == 0 and size_out.strip().isdigit():
                info[name] = f"{int(size_out.strip()) // 1024} KB"
            else:
                info[name] = "fehlt"

        _, listing, _ = _run_command(client, f"ls -1 '{box}' 2>/dev/null")
        info["box_files"] = listing.replace("\n", ", ")[:200] if listing else "—"

    return info


def _ssh_disconnect_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(
        token in text
        for token in (
            "eof",
            "reset",
            "closed",
            "broken pipe",
            "timed out",
            "timeout",
            "connection lost",
            "forcibly closed",
        )
    )


def _ssh_try_reboot(client) -> bool:
    """Blockierender Neustart — Verbindungsabbruch gilt als Erfolg."""
    commands = (
        "sync; shutdown -r now",
        "sync; busybox reboot -f",
        "sync; /sbin/reboot -f",
        "sync; reboot -f",
        "reboot",
    )
    for cmd in commands:
        try:
            _stdin, stdout, stderr = client.exec_command(cmd, timeout=5.0)
            stdout.channel.settimeout(5.0)
            try:
                code = stdout.channel.recv_exit_status()
                if code == 0:
                    return True
            except Exception as exc:
                if _ssh_disconnect_error(exc):
                    return True
            err = stderr.read().decode("utf-8", errors="replace").strip()
            if err and "not found" not in err.lower():
                continue
        except Exception as exc:
            if _ssh_disconnect_error(exc):
                return True
    return False


def reboot_printer_ws(host: str) -> str | None:
    """K2-Neustart per WebSocket (Port 9999). Gibt den verwendeten Parameter zurueck."""
    from creality_nfc.printer_ws import PrinterWsError, send_set_once

    host = normalize_host(host)
    candidates: tuple[dict[str, Any], ...] = (
        {"restart": 1},
        {"reStart": 1},
        {"deviceRestart": 1},
        {"machineRestart": 1},
        {"reboot": 1},
        {"sysCommand": "reboot"},
    )
    last_err = ""
    for params in candidates:
        try:
            send_set_once(host, timeout=6.0, **params)
            key = next(iter(params))
            return f"WLAN:{key}"
        except Exception as exc:
            last_err = str(exc)
            continue
    if last_err:
        raise RuntimeError(last_err)
    return None


def reboot_printer(
    host: str,
    password: str,
    username: str = "root",
    port: int = 22,
) -> str:
    """
    K2 neu starten (SSH, sonst WebSocket).
    Rueckgabe: Kurztext fuer UI (z. B. 'SSH' oder 'WLAN:restart').
    """
    host = normalize_host(host)
    ssh_err = ""
    with ssh_client(host, password, username, port) as client:
        if _ssh_try_reboot(client):
            return "SSH"
        ssh_err = "SSH-Neustart ohne Reaktion"
    try:
        via_ws = reboot_printer_ws(host)
        if via_ws:
            return via_ws
    except Exception as exc:
        ssh_err = f"{ssh_err}; WLAN: {exc}" if ssh_err else str(exc)
    raise RuntimeError(
        "Neustart am Drucker nicht moeglich. "
        "Bitte am Display neu starten oder Strom kurz trennen."
        + (f" ({ssh_err})" if ssh_err else "")
    )
