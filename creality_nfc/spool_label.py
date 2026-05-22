"""Spulen-Etikett (HTML zum Drucken, optional QR-Code)."""

from __future__ import annotations

import html
from pathlib import Path

from creality_nfc.spool_inventory import Spool


def _qr_data_url(payload: str) -> str | None:
    try:
        import qrcode
        from io import BytesIO
        import base64

        img = qrcode.make(payload, box_size=4, border=2)
        buf = BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.standard_b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/png;base64,{b64}"
    except Exception:
        return None


def build_spool_label_html(spool: Spool) -> str:
    payload = f"TDFS|{spool.id}|{spool.serial}|{spool.filament_id}"
    qr = _qr_data_url(payload)
    qr_img = (
        f'<img src="{qr}" alt="QR" width="120" height="120"/>'
        if qr
        else f'<p class="sn">{html.escape(spool.serial)}</p>'
    )
    rest = f"{spool.remaining_g} g" if spool.remaining_g is not None else "—"
    slot = spool.cfs_slot_label() or "—"
    return f"""<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8"/>
<title>Etikett {html.escape(spool.label)}</title>
<style>
@page {{ size: 62mm 40mm; margin: 4mm; }}
body {{ font-family: Segoe UI, sans-serif; font-size: 11px; margin: 0; }}
.wrap {{ display: flex; gap: 8px; align-items: flex-start; }}
h1 {{ font-size: 14px; margin: 0 0 4px; }}
.meta {{ line-height: 1.35; }}
.sn {{ font-size: 18px; font-weight: bold; letter-spacing: 2px; }}
</style></head><body>
<div class="wrap">
<div>{qr_img}</div>
<div>
<h1>{html.escape(spool.label)}</h1>
<div class="meta">
{html.escape(spool.brand)} {html.escape(spool.material_name)}<br/>
#{html.escape(spool.color_hex)} · {html.escape(spool.weight)}<br/>
Rest: {html.escape(rest)} · CFS {html.escape(slot)}<br/>
SN: {html.escape(spool.serial)} · ID {html.escape(spool.filament_id)}<br/>
UID: {html.escape(spool.tag_uid or "—")}
</div></div></div></body></html>"""


def write_spool_label_html(path: Path, spool: Spool) -> None:
    path.write_text(build_spool_label_html(spool), encoding="utf-8")
