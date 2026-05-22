"""MyAppVersion in installer/setup.iss aus creality_nfc/config.py (APP_VERSION)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "creality_nfc" / "config.py"
ISS = ROOT / "installer" / "setup.iss"


def main() -> int:
    text = CONFIG.read_text(encoding="utf-8")
    m = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', text)
    if not m:
        print("APP_VERSION nicht gefunden in config.py", file=sys.stderr)
        return 1
    version = m.group(1)
    iss = ISS.read_text(encoding="utf-8")
    new_iss, n = re.subn(
        r'(#define MyAppVersion ")[^"]+(")',
        rf'\g<1>{version}\2',
        iss,
        count=1,
    )
    if n != 1:
        print("MyAppVersion in setup.iss nicht gefunden", file=sys.stderr)
        return 1
    if new_iss != iss:
        ISS.write_text(new_iss, encoding="utf-8")
        print(f"setup.iss -> Version {version}")
    else:
        print(f"setup.iss bereits Version {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
