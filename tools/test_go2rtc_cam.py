import subprocess
import time
import urllib.request
from pathlib import Path

host = "192.168.178.136"
cfg = Path(__file__).with_name("go2rtc_test.yaml")
cfg.write_text(
    f"""api:
  listen: 127.0.0.1:1985
rtsp:
  listen: ":8559"
webrtc:
  listen: ":8560"
streams:
  k2: webrtc:http://{host}:8000/call/webrtc_local#format=creality
""",
    encoding="utf-8",
)
exe = Path(__file__).with_name("go2rtc.exe")
proc = subprocess.Popen([str(exe), "-config", str(cfg)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    time.sleep(10)
    for path in (
        "http://127.0.0.1:1985/api/frame.jpeg?src=k2",
        "http://127.0.0.1:1985/api/stream.mjpeg?src=k2",
    ):
        try:
            with urllib.request.urlopen(path, timeout=30) as r:
                d = r.read(100_000)
            print(path, "OK", len(d))
        except Exception as exc:
            print(path, "FAIL", exc)
finally:
    proc.terminate()
