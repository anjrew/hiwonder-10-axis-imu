"""Live 3D view of the IMU's orientation, served to your browser.

Starts a small local web server that streams orientation to a page which draws
a box turning with the sensor. No GUI toolkit needed - just a browser.
"""

from __future__ import annotations

import json
import math
import queue
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterator

from .reader import DEFAULT_BAUDRATE, ImuReader

WEB_DIR = Path(__file__).parent / "web"


def demo_source() -> Iterator[dict]:
    """Fake but plausible motion, for trying the view without hardware."""
    start = time.monotonic()
    while True:
        t = time.monotonic() - start
        roll = 35.0 * math.sin(t * 0.9)
        pitch = 25.0 * math.sin(t * 0.6 + 1.0)
        yaw = (t * 40.0) % 360.0 - 180.0
        yield {
            "angle": [roll, pitch, yaw],
            "accel": [
                -9.80665 * math.sin(math.radians(pitch)),
                9.80665 * math.sin(math.radians(roll)),
                9.80665 * math.cos(math.radians(roll)) * math.cos(math.radians(pitch)),
            ],
            "gyro": [
                35.0 * 0.9 * math.cos(t * 0.9),
                25.0 * 0.6 * math.cos(t * 0.6 + 1.0),
                40.0,
            ],
            "temp": 24.5,
            "demo": True,
        }
        time.sleep(0.02)


def serial_source(port: str | None, baudrate: int) -> Iterator[dict]:
    with ImuReader(port, baudrate) as imu:
        for sample in imu.samples():
            if sample.angle is None and sample.quaternion is None:
                continue
            yield {
                "angle": list(sample.angle) if sample.angle else None,
                "quaternion": list(sample.quaternion) if sample.quaternion else None,
                "accel": list(sample.accel) if sample.accel else None,
                "gyro": list(sample.gyro) if sample.gyro else None,
                "mag": list(sample.mag) if sample.mag else None,
                "temp": sample.temperature,
                "demo": False,
            }


class _Hub:
    """Fans the newest sample out to every connected browser tab."""

    def __init__(self) -> None:
        self._clients: set[queue.Queue] = set()
        self._lock = threading.Lock()
        self.error: str | None = None

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=4)
        with self._lock:
            self._clients.add(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            self._clients.discard(q)

    def publish(self, payload: dict) -> None:
        with self._lock:
            clients = list(self._clients)
        for q in clients:
            try:
                q.put_nowait(payload)
            except queue.Full:
                pass  # slow tab: drop this one, it only wants the latest anyway

    def pump(self, source: Iterator[dict]) -> None:
        try:
            for payload in source:
                self.publish(payload)
        except Exception as exc:  # surface it in the page instead of dying quietly
            self.error = str(exc)
            self.publish({"error": str(exc)})


def _handler_for(hub: _Hub):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args) -> None:
            pass  # keep the terminal clean

        def do_GET(self) -> None:
            if self.path.startswith("/stream"):
                self._stream()
            elif self.path in ("/", "/index.html"):
                self._file("index.html", "text/html; charset=utf-8")
            else:
                self.send_error(404)

        def _file(self, name: str, content_type: str) -> None:
            body = (WEB_DIR / name).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _stream(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            q = hub.subscribe()
            try:
                while True:
                    try:
                        payload = q.get(timeout=5.0)
                    except queue.Empty:
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
                        continue
                    self.wfile.write(f"data: {json.dumps(payload)}\n\n".encode())
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass  # tab closed
            finally:
                hub.unsubscribe(q)

    return Handler


def serve(
    port: str | None = None,
    baudrate: int = DEFAULT_BAUDRATE,
    http_port: int = 8420,
    demo: bool = False,
    open_browser: bool = True,
) -> None:
    hub = _Hub()
    source = demo_source() if demo else serial_source(port, baudrate)
    threading.Thread(target=hub.pump, args=(source,), daemon=True).start()

    server = ThreadingHTTPServer(("127.0.0.1", http_port), _handler_for(hub))
    url = f"http://127.0.0.1:{http_port}/"
    print(f"3D view at {url}" + ("  (demo data)" if demo else "") + " - ctrl-c to stop")
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
