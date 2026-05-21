"""Windows-10+-Toast ohne Zusatzpakete (PowerShell + WinRT)."""

from __future__ import annotations

import subprocess
import sys


def show_windows_toast(title: str, message: str, *, app_id: str = "TD Filament Studio") -> bool:
    """Zeigt eine Desktop-Benachrichtigung. Gibt False zurück, wenn nicht möglich."""
    if sys.platform != "win32":
        return False
    t = _ps_escape(title.strip() or "TD Filament Studio")
    m = _ps_escape(message.strip() or " ")
    aid = _ps_escape(app_id)
    ps = f"""
$ErrorActionPreference = 'Stop'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml(@"
<toast duration="long">
  <visual>
    <binding template="ToastGeneric">
      <text>{t}</text>
      <text>{m}</text>
    </binding>
  </visual>
</toast>
"@)
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{aid}').Show($toast)
"""
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
            capture_output=True,
            timeout=12,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return True
    except (OSError, subprocess.TimeoutExpired):
        return False


def _ps_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
