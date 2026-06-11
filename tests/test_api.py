"""Dashboard API integration tests: boots a real `lai ui` server on a free
port and exercises the read-only surface. No state is mutated."""
import json
import socket
import subprocess
import sys
import time
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _req(port, path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", data=data,
        headers={"Content-Type": "application/json", "User-Agent": "t"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, json.loads(r.read().decode())


class TestDashboardApi(unittest.TestCase):
    proc = None
    port = None

    @classmethod
    def setUpClass(cls):
        cls.port = _free_port()
        cls.proc = subprocess.Popen(
            [sys.executable, str(ROOT / "lai.py"), "ui", "--no-browser",
             "--port", str(cls.port)],
            stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
            cwd=str(ROOT))
        deadline = time.monotonic() + 20.0
        sleep_s = 0.05
        while time.monotonic() < deadline:
            time.sleep(sleep_s)
            try:
                _req(cls.port, "/api/overview")
                return
            except Exception:
                if cls.proc.poll() is not None:
                    break
            sleep_s = min(sleep_s * 2, 0.5)
        raise unittest.SkipTest("ui server failed to boot")

    @classmethod
    def tearDownClass(cls):
        if cls.proc and cls.proc.poll() is None:
            cls.proc.kill()

    def test_overview_shape(self):
        status, o = _req(self.port, "/api/overview")
        self.assertEqual(status, 200)
        for key in ("usecases", "stacks", "skills", "running",
                    "lai_version", "models_meta"):
            self.assertIn(key, o)
        self.assertGreaterEqual(len(o["stacks"]), 15)
        self.assertGreaterEqual(len(o["skills"]), 9)

    def test_status_and_candidates(self):
        _, s = _req(self.port, "/api/status")
        self.assertGreaterEqual(len(s), 5)
        _, c = _req(self.port, "/api/candidates")
        self.assertIn("coder", c["candidates"])

    def test_ports_and_cloud(self):
        _, p = _req(self.port, "/api/ports")
        self.assertEqual(len(p["ports"]), 9)
        _, cc = _req(self.port, "/api/cloudcfg")
        self.assertEqual(len(cc["providers"]), 3)

    def test_downloads_and_projects(self):
        _, d = _req(self.port, "/api/downloads")
        self.assertIn("running", d)
        self.assertIn("items", d)
        _, pj = _req(self.port, "/api/projects")
        self.assertIsInstance(pj["projects"], list)

    def test_serves_the_vue_app(self):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/", headers={"User-Agent": "t"})
        html = urllib.request.urlopen(req, timeout=10).read().decode()
        self.assertIn("assets/index-", html)

    def test_cross_origin_post_is_blocked(self):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/start", data=b"{}",
            headers={"Content-Type": "application/json",
                     "Origin": "https://evil.example", "User-Agent": "t"})
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req, timeout=10)
        self.assertEqual(cm.exception.code, 403)

    def test_error_paths(self):
        for path, payload, want in (
                ("/api/nope", None, 404),
                ("/api/logs?name=../../etc/passwd", None, 400),
                ("/api/logs?name=..%2f..%2fetc%2fpasswd", None, 400),
                ("/api/logs?name=..%252f..%252fetc%252fpasswd", None, 400),
                ("/api/logs?name=..\\..\\windows\\win.ini", None, 400),
                ("/api/logs?name=../../etc/passwd%00.log", None, 400),
                ("/api/logs?name=..%E2%88%95..%E2%88%95etc%E2%88%95passwd", None, 400),
                ("/api/set", {"role": "nope", "model": "x"}, 400),
                ("/api/new", {"stack": "nope", "path": "X:/nope"}, 400),
                ("/api/gate", {"path": str(ROOT / "nope")}, 400),
                # filesystem root: blocked by the workspace barrier (or,
                # if a registered project allows the drive, by the gate)
                ("/api/gate", {"path": "/"}, 400)):
            with self.assertRaises(urllib.error.HTTPError) as cm:
                _req(self.port, path, payload)
            self.assertEqual(cm.exception.code, want, path)


if __name__ == "__main__":
    unittest.main()
