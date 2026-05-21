"""Lokaler Mini-Server: Three.js STL-Vorschau für eingebetteten Edge/Chrome."""

from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

VIEWER_TITLE_PREFIX = "TDFilamentStudio STL Preview"


def make_viewer_window_id() -> str:
    import uuid

    return uuid.uuid4().hex[:10]


def make_viewer_title(window_id: str) -> str:
    return f"{VIEWER_TITLE_PREFIX} {window_id}"


def stl_browser_profile_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", "")) / "TD Filament Studio" / "stl_preview_browser"
    base.mkdir(parents=True, exist_ok=True)
    return base


def build_stl_browser_args(exe: Path, url: str, *, width: int = 900, height: int = 600) -> list[str]:
    w = max(320, int(width))
    h = max(240, int(height))
    return [
        str(exe),
        f"--user-data-dir={stl_browser_profile_dir()}",
        f"--app={url}",
        f"--window-size={w},{h}",
        "--window-position=0,0",
        "--new-window",
        "--no-first-run",
        "--disable-features=Translate",
        "--disable-infobars",
    ]


_VIEWER_HTML = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  html, body { margin: 0; height: 100%; overflow: hidden; background: #3a3d44; }
  #c { width: 100%; height: 100%; display: block; }
  #msg {
    position: absolute; left: 8px; right: 8px; bottom: 8px;
    padding: 6px 10px; font: 12px "Segoe UI", sans-serif;
    color: #c4c8ce; background: rgba(15,17,21,0.75); border-radius: 4px;
    pointer-events: none;
  }
</style>
</head>
<body>
<canvas id="c"></canvas>
<div id="msg">Lade Modell …</div>
<script type="importmap">
{
  "imports": {
    "three": "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js",
    "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"
  }
}
</script>
<script type="module">
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';

const msg = document.getElementById('msg');
const canvas = document.getElementById('c');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.setClearColor(0x4a4e57, 1);

const scene = new THREE.Scene();
scene.add(new THREE.AmbientLight(0xffffff, 0.55));
const key = new THREE.DirectionalLight(0xffffff, 0.85);
key.position.set(1.2, 1.4, 1.0);
scene.add(key);
const fill = new THREE.DirectionalLight(0xb8c0cc, 0.35);
fill.position.set(-1, 0.3, -0.8);
scene.add(fill);

const camera = new THREE.PerspectiveCamera(45, 1, 0.01, 5000);
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;
controls.dampingFactor = 0.08;

let mesh = null;
let lastRev = -1;
const loader = new STLLoader();

function fitMesh(geometry) {
  geometry.computeBoundingBox();
  geometry.center();
  const size = new THREE.Vector3();
  geometry.boundingBox.getSize(size);
  const maxDim = Math.max(size.x, size.y, size.z, 1e-6);
  const dist = maxDim * 1.8;
  camera.position.set(dist * 0.85, dist * 0.65, dist * 0.9);
  camera.lookAt(0, 0, 0);
  controls.target.set(0, 0, 0);
  controls.update();
}

function showMesh(geometry, name) {
  if (mesh) {
    scene.remove(mesh);
    mesh.geometry.dispose();
    mesh.material.dispose();
  }
  const mat = new THREE.MeshStandardMaterial({
    color: 0xb8bec8,
    metalness: 0.12,
    roughness: 0.55,
  });
  mesh = new THREE.Mesh(geometry, mat);
  scene.add(mesh);
  fitMesh(geometry);
  msg.textContent = name || 'STL';
}

async function poll() {
  try {
    const r = await fetch('/meta.json');
    const meta = await r.json();
    if (!meta.ready) {
      msg.textContent = 'Kein Modell';
      return;
    }
    if (meta.rev === lastRev) return;
    lastRev = meta.rev;
    msg.textContent = 'Lade ' + (meta.name || 'STL') + ' …';
    loader.load('/mesh.stl?rev=' + meta.rev, (geo) => showMesh(geo, meta.name), undefined, (err) => {
      msg.textContent = 'Fehler: ' + err;
    });
  } catch (e) {
    msg.textContent = 'Vorschau: ' + e;
  }
}

function resize() {
  const w = canvas.clientWidth;
  const h = canvas.clientHeight;
  if (w < 2 || h < 2) return;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}
window.addEventListener('resize', resize);
new ResizeObserver(resize).observe(canvas);

function tick() {
  requestAnimationFrame(tick);
  controls.update();
  renderer.render(scene, camera);
}
tick();
poll();
setInterval(poll, 400);
</script>
</body>
</html>
"""


class _PreviewState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.path: Path | None = None
        self.name = ""
        self.rev = 0

    def set_file(self, path: Path | None) -> None:
        with self.lock:
            if path and path.is_file():
                self.path = path.resolve()
                self.name = path.name
                self.rev += 1
            else:
                self.path = None
                self.name = ""
                self.rev += 1

    def snapshot(self) -> tuple[int, str, bool]:
        with self.lock:
            return self.rev, self.name, self.path is not None and self.path.is_file()

    def read_mesh(self) -> bytes | None:
        with self.lock:
            p = self.path
        if not p or not p.is_file():
            return None
        try:
            return p.read_bytes()
        except OSError:
            return None


class _StlPreviewHandler(BaseHTTPRequestHandler):
    state: _PreviewState = _PreviewState()

    def log_message(self, _fmt: str, *_args) -> None:
        pass

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path in ("/", "/index.html"):
            q = parse_qs(parsed.query)
            win = (q.get("win") or [""])[0].strip()
            title = make_viewer_title(win) if win else f"{VIEWER_TITLE_PREFIX}"
            body = _VIEWER_HTML.replace("__TITLE__", title).encode("utf-8")
            self._send_bytes(200, "text/html; charset=utf-8", body)
            return
        if path == "/meta.json":
            rev, name, ready = self.state.snapshot()
            payload = json.dumps({"rev": rev, "name": name, "ready": ready}, ensure_ascii=False)
            self._send_bytes(200, "application/json; charset=utf-8", payload.encode("utf-8"))
            return
        if path == "/mesh.stl":
            data = self.state.read_mesh()
            if not data:
                self.send_error(404)
                return
            self._send_bytes(200, "model/stl", data)
            return
        self.send_error(404)

    def _send_bytes(self, code: int, content_type: str, data: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)


class StlPreviewServer:
    _lock = threading.Lock()
    _shared: StlPreviewServer | None = None

    def __init__(self) -> None:
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._host = "127.0.0.1"
        self._port = 0

    @property
    def base_url(self) -> str:
        return f"http://{self._host}:{self._port}/"

    @classmethod
    def state(cls) -> _PreviewState:
        return _StlPreviewHandler.state

    def start(self) -> str:
        with StlPreviewServer._lock:
            if StlPreviewServer._shared and StlPreviewServer._shared._httpd:
                return StlPreviewServer._shared.base_url
            self._httpd = ThreadingHTTPServer((self._host, 0), _StlPreviewHandler)
            self._port = self._httpd.server_address[1]
            self._thread = threading.Thread(
                target=self._httpd.serve_forever,
                name="stl-preview",
                daemon=True,
            )
            self._thread.start()
            StlPreviewServer._shared = self
            return self.base_url

    def stop(self) -> None:
        if self._httpd:
            self._httpd.shutdown()
            self._httpd = None
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
