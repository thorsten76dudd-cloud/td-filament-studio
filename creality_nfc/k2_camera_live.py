"""Live-Kamera Creality K2 (WebRTC Port 8000 — wie Creality Print / webrtc_local)."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

from creality_nfc.printer_camera import fetch_camera_snapshot, normalize_host, open_url

_SIGNAL_PATH = "/call/webrtc_local"
_GO2RTC_EXE = Path(__file__).resolve().parent.parent / "tools" / "go2rtc.exe"

_VIEWER_HTML = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  html, body { margin: 0; height: 100%; background: #0f1115; color: #9aa3b2; font-family: "Segoe UI", sans-serif; }
  #wrap { display: flex; flex-direction: column; height: 100%; min-height: 0; }
  #status { padding: 8px 12px; font-size: 13px; background: #1a1f28; border-bottom: 1px solid #2a3140; }
  video { flex: 1; width: 100%; height: 100%; min-height: 0; background: #000; object-fit: contain; }
  #status.ok { color: #6ee7a8; }
  #status.err { color: #f87171; }
  #status.warn { color: #f6c177; }
</style>
</head>
<body>
<div id="wrap">
  <div id="status">__I18N_CONNECTING__</div>
  <video id="remoteVideos" playsinline autoplay muted></video>
</div>
<script>
const HOST = "__HOST__";
const STALL_LIMIT_MS = 8000;
const RELOAD_LIMIT_MS = 12000;
const statusEl = document.getElementById("status");
const videoEl = document.getElementById("remoteVideos");
let pc = null;
let watchdogTimer = null;
let lastFrameAt = 0;
let lastVideoTime = -1;
let gotFirstFrame = false;
let reloading = false;

function setStatus(msg, cls) {
  statusEl.textContent = msg;
  statusEl.className = cls || "";
}

function hardReload() {
  if (reloading) return;
  reloading = true;
  setStatus("__I18N_RELOAD__", "warn");
  try { if (pc) pc.close(); } catch (_) {}
  setTimeout(() => { window.location.reload(); }, 250);
}

function markFrame() {
  lastFrameAt = Date.now();
  gotFirstFrame = true;
}

function startWatchdog() {
  if (watchdogTimer) return;
  lastFrameAt = Date.now();
  if (typeof videoEl.requestVideoFrameCallback === "function") {
    const cb = () => {
      markFrame();
      videoEl.requestVideoFrameCallback(cb);
    };
    videoEl.requestVideoFrameCallback(cb);
  }
  watchdogTimer = setInterval(() => {
    if (reloading) return;
    const idle = Date.now() - lastFrameAt;
    if (typeof videoEl.requestVideoFrameCallback !== "function") {
      const t = videoEl.currentTime || 0;
      if (t !== lastVideoTime && t > 0) {
        lastVideoTime = t;
        markFrame();
      }
    }
    if (!gotFirstFrame) {
      if (idle > RELOAD_LIMIT_MS) hardReload();
      else if (idle > STALL_LIMIT_MS) {
        setStatus("__I18N_WAIT_BUSY__", "warn");
      }
      return;
    }
    if (idle > RELOAD_LIMIT_MS) {
      hardReload();
    } else if (idle > STALL_LIMIT_MS) {
      setStatus("__I18N_RECOVERY__", "warn");
    }
  }, 1000);
}

function sendOfferToCall(sdp) {
  const body = btoa(JSON.stringify({ type: "offer", sdp: sdp }));
  fetch("/signal", {
    method: "POST",
    headers: { "Content-Type": "plain/text" },
    body: body
  })
    .then(r => {
      if (!r.ok) throw new Error("Signal " + r.status);
      return r.text();
    })
    .then(t => {
      const res = JSON.parse(atob(t));
      if (res.type === "answer") {
        return pc.setRemoteDescription(new RTCSessionDescription(res));
      }
      throw new Error("__I18N_NO_SDP__");
    })
    .then(() => {
      setStatus("__I18N_WEBRTC_WAIT__", "ok");
      startWatchdog();
    })
    .catch(e => {
      setStatus("__I18N_ERROR__" + e, "err");
      setTimeout(hardReload, 4000);
    });
}

function buildPeer() {
  pc = new RTCPeerConnection({
    iceServers: [{ urls: "stun:stun.l.google.com:19302" }]
  });
  pc.ontrack = (event) => {
    videoEl.srcObject = event.streams[0];
    videoEl.autoplay = true;
    videoEl.muted = true;
    setStatus("__I18N_LIVE__" + HOST, "ok");
    markFrame();
  };
  pc.oniceconnectionstatechange = () => {
    const s = pc.iceConnectionState;
    if (s === "failed") {
      setStatus("__I18N_ICE_FAILED__", "err");
      setTimeout(hardReload, 1500);
    } else if (s === "disconnected") {
      setStatus("__I18N_DISCONNECTED__", "warn");
      setTimeout(() => {
        if (pc && pc.iceConnectionState !== "connected" && pc.iceConnectionState !== "completed") {
          hardReload();
        }
      }, 6000);
    } else if (s === "closed") {
      hardReload();
    }
  };
  pc.onicecandidate = (event) => {
    if (event.candidate === null) {
      sendOfferToCall(pc.localDescription.sdp);
    }
  };
  pc.addTransceiver("video", { direction: "sendrecv" });
  pc.createOffer()
    .then((d) => pc.setLocalDescription(d))
    .catch((e) => setStatus("__I18N_OFFER__" + e, "err"));
}

videoEl.addEventListener("playing", markFrame);
videoEl.addEventListener("timeupdate", markFrame);
window.addEventListener("focus", () => {
  if (gotFirstFrame && Date.now() - lastFrameAt > STALL_LIMIT_MS) {
    hardReload();
  }
});
buildPeer();
</script>
</body>
</html>
"""


@dataclass
class K2CameraFrame:
    data: bytes
    width: int
    height: int


def fix_creality_sdp(value: str) -> str:
    """SDP-Antwort wie go2rtc #1600 (ersten Codec + x-google fmtp entfernen)."""
    lines = value.replace("\r\n", "\n").split("\n")
    skip: str | None = None
    for i, line in enumerate(lines):
        if line.startswith("m=video"):
            parts = line.split()
            if len(parts) < 4:
                return value
            skip = parts[3]
            lines[i] = " ".join(parts[:3] + parts[4:])
            break
    if skip is None:
        return value
    out: list[str] = []
    for line in lines:
        if line.startswith("a=fmtp:") or line.startswith("a=rtpmap:"):
            pt = line.split(":", 1)[1].split()[0]
            if pt == skip or "x-google" in line:
                continue
        out.append(line)
    return "\r\n".join(out) + "\r\n"


def camera_page_url(host: str) -> str:
    return f"http://{normalize_host(host)}:8000/"


def camera_signal_url(host: str) -> str:
    return f"http://{normalize_host(host)}:8000{_SIGNAL_PATH}"


VIEWER_TITLE_PREFIX = "TDFilamentStudio K2 Cam"


def make_viewer_window_id() -> str:
    return uuid.uuid4().hex[:10]


def make_viewer_title(window_id: str) -> str:
    return f"{VIEWER_TITLE_PREFIX} {window_id}"


def isolated_browser_profile_dir() -> Path:
    """Eigenes Edge/Chrome-Profil — nicht den normalen Browser des Nutzers anfassen."""
    root = Path(tempfile.gettempdir()) / "td_filament_studio_edge_cam"
    root.mkdir(parents=True, exist_ok=True)
    return root


def build_isolated_browser_args(exe: Path, url: str) -> list[str]:
    profile = isolated_browser_profile_dir()
    return [
        str(exe),
        f"--user-data-dir={profile}",
        f"--app={url}",
        "--new-window",
        "--no-first-run",
        "--disable-features=Translate",
        "--disable-infobars",
    ]


def _viewer_html_for_host(host: str, title: str) -> str:
    from creality_nfc.i18n import t as _t

    html = _VIEWER_HTML.replace("__HOST__", host).replace("__TITLE__", title)
    return (
        html.replace("__I18N_CONNECTING__", _t("camera.connecting", host=host))
        .replace("__I18N_RELOAD__", _t("camera.reload"))
        .replace("__I18N_WAIT_BUSY__", _t("camera.wait_busy"))
        .replace("__I18N_RECOVERY__", _t("camera.recovery"))
        .replace("__I18N_NO_SDP__", _t("camera.no_sdp"))
        .replace("__I18N_WEBRTC_WAIT__", _t("camera.webrtc_wait"))
        .replace("__I18N_ERROR__", _t("camera.error"))
        .replace("__I18N_LIVE__", _t("camera.live"))
        .replace("__I18N_ICE_FAILED__", _t("camera.ice_failed"))
        .replace("__I18N_DISCONNECTED__", _t("camera.disconnected"))
        .replace("__I18N_OFFER__", _t("camera.offer_error"))
    )


class _CameraProxyHandler(BaseHTTPRequestHandler):
    printer_host: str = ""

    def log_message(self, _fmt: str, *_args: Any) -> None:
        pass

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path in ("/", "/index.html"):
            q = parse_qs(parsed.query)
            win = (q.get("win") or [""])[0].strip()
            title = make_viewer_title(win) if win else f"{VIEWER_TITLE_PREFIX} Viewer"
            html = _viewer_html_for_host(self.printer_host, title)
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/signal":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = self.rfile.read(length)
        upstream = camera_signal_url(self.printer_host)
        req = urllib.request.Request(
            upstream,
            data=payload,
            headers={"Content-Type": "plain/text"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                answer = resp.read()
        except urllib.error.URLError as exc:
            self.send_error(502, f"Drucker nicht erreichbar: {exc}")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(answer)))
        self.end_headers()
        self.wfile.write(answer)


class K2CameraViewerServer:
    """Lokaler Mini-Webserver: Browser-WebRTC + Signaling-Proxy zum Drucker."""

    _lock = threading.Lock()
    _shared: K2CameraViewerServer | None = None

    def __init__(self) -> None:
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._host = "127.0.0.1"
        self._port = 0
        self._printer: str = ""

    @property
    def viewer_url(self) -> str:
        return f"http://{self._host}:{self._port}/"

    def start(self, printer_host: str) -> str:
        printer_host = normalize_host(printer_host)
        with K2CameraViewerServer._lock:
            if K2CameraViewerServer._shared and K2CameraViewerServer._shared._httpd:
                srv = K2CameraViewerServer._shared
                srv._printer = printer_host
                _CameraProxyHandler.printer_host = printer_host
                return srv.viewer_url
            self._printer = printer_host
            _CameraProxyHandler.printer_host = printer_host
            self._httpd = ThreadingHTTPServer((self._host, 0), _CameraProxyHandler)
            self._port = self._httpd.server_address[1]
            self._thread = threading.Thread(
                target=self._httpd.serve_forever,
                name="k2-cam-viewer",
                daemon=True,
            )
            self._thread.start()
            K2CameraViewerServer._shared = self
            return self.viewer_url

    def stop(self) -> None:
        if self._httpd:
            self._httpd.shutdown()
            self._httpd = None
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None


def _edge_chrome_paths() -> list[Path]:
    paths: list[Path] = []
    pf = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    pfx86 = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    for base in (pfx86 / "Microsoft/Edge/Application/msedge.exe", pf / "Microsoft/Edge/Application/msedge.exe"):
        paths.append(base)
    for base in (
        pf / "Google/Chrome/Application/chrome.exe",
        pfx86 / "Google/Chrome/Application/chrome.exe",
        local / "Google/Chrome/Application/chrome.exe",
    ):
        paths.append(base)
    return paths


def open_camera_app_window(host: str) -> bool:
    """Live-Kamera in App-Fenster (Edge/Chrome) — gleiches WebRTC wie Creality Print."""
    host = normalize_host(host)
    if not host:
        return False
    try:
        url = K2CameraViewerServer().start(host)
    except OSError:
        return open_url(camera_page_url(host))
    app_url = url
    win_id = make_viewer_window_id()
    app_url = f"{app_url.rstrip('/')}/?win={win_id}"
    if sys.platform == "win32":
        for exe in _edge_chrome_paths():
            if exe.is_file():
                try:
                    subprocess.Popen(
                        build_isolated_browser_args(exe, app_url),
                        close_fds=True,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                    return True
                except OSError:
                    continue
    return open_url(app_url)


def open_camera_browser(host: str) -> bool:
    return open_camera_app_window(host)


class K2WebRtcCamera:
    """Einzelbild per aiortc (optional; oft scheitert DTLS — Browser bevorzugen)."""

    def __init__(self, host: str) -> None:
        self.host = normalize_host(host)
        self._url = camera_signal_url(self.host)

    async def capture_frame_async(self, timeout: float = 15.0) -> K2CameraFrame | None:
        try:
            import aiohttp
            from aiortc import (
                RTCIceServer,
                RTCPeerConnection,
                RTCSessionDescription,
                RTCConfiguration,
            )
        except ImportError:
            return None

        cfg = RTCConfiguration(iceServers=[RTCIceServer(urls=["stun:stun.l.google.com:19302"])])
        pc = RTCPeerConnection(configuration=cfg)
        pc.addTransceiver("video", direction="sendrecv")
        frame_holder: list[Any] = []
        got = asyncio.Event()

        @pc.on("track")
        def on_track(track: Any) -> None:
            if track.kind != "video":
                return

            async def reader() -> None:
                try:
                    frame_holder.append(await asyncio.wait_for(track.recv(), timeout=timeout))
                finally:
                    got.set()

            asyncio.ensure_future(reader())

        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)
        while pc.iceGatheringState != "complete":
            await asyncio.sleep(0.05)

        payload = base64.b64encode(
            json.dumps({"type": "offer", "sdp": pc.localDescription.sdp}).encode()
        ).decode()
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self._url,
                data=payload,
                headers={"Content-Type": "plain/text"},
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                raw = await resp.text()
        answer = json.loads(base64.b64decode(raw))
        sdp = fix_creality_sdp(answer["sdp"])
        await pc.setRemoteDescription(RTCSessionDescription(sdp=sdp, type=answer["type"]))

        try:
            await asyncio.wait_for(got.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            await pc.close()
            return None

        if not frame_holder:
            await pc.close()
            return None

        vf = frame_holder[0]
        from PIL import Image
        import io

        img = vf.to_image()
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        await pc.close()
        return K2CameraFrame(data=buf.getvalue(), width=img.width, height=img.height)

    def capture_frame(self, timeout: float = 15.0) -> K2CameraFrame | None:
        try:
            return asyncio.run(self.capture_frame_async(timeout=timeout))
        except Exception:
            return None


class Go2RtcK2Camera:
    """go2rtc ≥1.9.10 als Bridge (nur wenn kein anderer Client den Stream nutzt)."""

    def __init__(self, host: str, api_port: int = 1984) -> None:
        self.host = normalize_host(host)
        self.api_port = api_port
        self._proc: subprocess.Popen | None = None
        self._cfg_path: Path | None = None

    def start(self) -> bool:
        if not _GO2RTC_EXE.is_file():
            return False
        self.stop()
        self._cfg_path = _GO2RTC_EXE.parent / f"go2rtc_{self.host.replace('.', '_')}.yaml"
        src = f"webrtc:{camera_signal_url(self.host)}#format=creality"
        self._cfg_path.write_text(
            f"api:\n  listen: 127.0.0.1:{self.api_port}\n"
            f"streams:\n  k2: {src}\n",
            encoding="utf-8",
        )
        self._proc = subprocess.Popen(
            [str(_GO2RTC_EXE), "-config", str(self._cfg_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        time.sleep(4.0)
        return self._proc.poll() is None

    def stop(self) -> None:
        if self._proc:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc = None

    def capture_jpeg(self, timeout: float = 8.0) -> bytes | None:
        if not self._proc or self._proc.poll() is not None:
            if not self.start():
                return None
        url = f"http://127.0.0.1:{self.api_port}/api/frame.jpeg?src=k2"
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                data = resp.read()
            return data if len(data) > 500 else None
        except Exception:
            return None


class K2CameraWorker:
    """Hintergrund: Livebild — standardmäßig HTTP-Snapshot (stabil), sonst WebRTC."""

    def __init__(
        self,
        host: str,
        on_frame: Callable[[bytes], None],
        *,
        interval: float = 0.45,
        prefer_snapshot: bool = True,
        on_status: Callable[[str], None] | None = None,
        on_need_edge: Callable[[], None] | None = None,
        preferred_snapshot_url: str = "",
        on_snapshot_url: Callable[[str], None] | None = None,
    ) -> None:
        self.host = normalize_host(host)
        self.on_frame = on_frame
        self.on_status = on_status
        self.on_need_edge = on_need_edge
        self.on_snapshot_url = on_snapshot_url
        self.interval = interval
        self._prefer_snapshot = prefer_snapshot
        self._preferred_url = (preferred_snapshot_url or "").strip()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._webrtc = K2WebRtcCamera(self.host)
        self._go2rtc = Go2RtcK2Camera(self.host)
        self._mode = "snapshot" if prefer_snapshot else "webrtc"
        self._failures = 0
        self._last_url = ""
        self._got_frame = False
        self._edge_requested = False

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._mode = "snapshot" if self._prefer_snapshot else "webrtc"
        self._failures = 0
        self._last_url = ""
        self._got_frame = False
        self._edge_requested = False
        self._thread = threading.Thread(target=self._loop, name="k2-cam", daemon=True)
        self._thread.start()

    @staticmethod
    def prefetch(
        host: str,
        *,
        preferred_url: str = "",
        timeout: float = 2.0,
    ) -> tuple[bytes, str] | None:
        return fetch_camera_snapshot(
            host,
            timeout=timeout,
            preferred_url=preferred_url,
        )

    def stop(self) -> None:
        self._stop.set()
        self._go2rtc.stop()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._thread = None

    def _status(self, msg: str) -> None:
        if self.on_status:
            try:
                self.on_status(msg)
            except Exception:
                pass

    def _request_edge_fallback(self) -> None:
        if self._edge_requested or not self.on_need_edge:
            return
        self._edge_requested = True
        try:
            self.on_need_edge()
        except Exception:
            pass

    def _loop(self) -> None:
        import sys

        while not self._stop.is_set():
            data: bytes | None = None
            wait = self.interval
            if self._mode == "snapshot":
                if not self._got_frame:
                    self._status("Kamera: verbinde …")
                shot = fetch_camera_snapshot(
                    self.host,
                    timeout=2.0 if self._preferred_url else 2.8,
                    preferred_url=self._preferred_url,
                )
                if shot:
                    data, self._last_url = shot[0], shot[1]
                    self._preferred_url = self._last_url
                    self._failures = 0
                    self._got_frame = True
                    wait = 0.35
                    if self.on_snapshot_url:
                        try:
                            self.on_snapshot_url(self._last_url)
                        except Exception:
                            pass
                    if not self._stop.is_set():
                        self._status("Live")
                else:
                    self._failures += 1
                    if self._failures == 2:
                        self._request_edge_fallback()
                    if self._failures >= 4:
                        if sys.platform == "win32" and self.on_need_edge:
                            self._request_edge_fallback()
                            self._stop.wait(0.5)
                            continue
                        self._status("Snapshot fehlgeschlagen — WebRTC …")
                        self._mode = "webrtc"
                        self._failures = 0
            elif self._mode == "webrtc":
                if sys.platform == "win32" and self.on_need_edge:
                    self._request_edge_fallback()
                    self._mode = "snapshot"
                    self._failures = 0
                    self._stop.wait(0.5)
                    continue
                self._status("Kamera: WebRTC …")
                frame = self._webrtc.capture_frame(timeout=5.0)
                if frame:
                    data = frame.data
                    self._failures = 0
                    self._got_frame = True
                    self._status("Live (WebRTC)")
                    wait = 0.5
                else:
                    self._failures += 1
                    if self._failures >= 1:
                        self._mode = "go2rtc"
                        self._failures = 0
                    self._stop.wait(0.15)
                    continue
            elif self._mode == "go2rtc":
                self._status("Kamera: go2rtc …")
                data = self._go2rtc.capture_jpeg(timeout=5.0)
                if data:
                    self._failures = 0
                    self._got_frame = True
                    self._status("Live (go2rtc)")
                    wait = 0.5
                else:
                    self._failures += 1
                    self._request_edge_fallback()
                    self._mode = "snapshot"
                    self._failures = 0
            if data:
                try:
                    self.on_frame(data)
                except Exception:
                    pass
            self._stop.wait(wait)
