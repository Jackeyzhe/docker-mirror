import json
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "docker-mirror" / "scripts" / "probe_mirrors.py"


class FakeRegistryHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.respond()

    def do_HEAD(self) -> None:
        self.respond()

    def respond(self) -> None:
        if self.path == "/v2/":
            self.send_response(200)
        elif self.path == "/v2/library/hello-world/manifests/latest":
            self.send_response(200)
        else:
            self.send_response(404)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return


class ProbeMirrorsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeRegistryHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.thread.join(timeout=5)

    def run_script(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_fake_registry_returns_success(self) -> None:
        result = self.run_script(
            "--candidate",
            self.base_url,
            "--allow-http",
            "--output",
            "json",
        )
        payload = json.loads(result.stdout)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(payload[0]["ok"])
        self.assertEqual(payload[0]["v2_status"], 200)
        self.assertEqual(payload[0]["manifest_status"], 200)

    def test_404_candidate_is_marked_failed(self) -> None:
        result = self.run_script(
            "--candidate",
            f"{self.base_url}/missing",
            "--allow-http",
            "--output",
            "json",
        )
        payload = json.loads(result.stdout)

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(payload[0]["ok"])
        self.assertEqual(payload[0]["v2_status"], 404)

    def test_invalid_url_is_skipped_and_all_fail_exit_nonzero(self) -> None:
        result = self.run_script("--candidate", "ftp://example.com", "--output", "json")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsupported URL scheme", result.stderr)
        self.assertIn("No valid candidates", result.stderr)

    def test_one_success_makes_exit_zero(self) -> None:
        result = self.run_script(
            "--candidate",
            "ftp://example.com",
            "--candidate",
            self.base_url,
            "--allow-http",
            "--output",
            "json",
        )
        payload = json.loads(result.stdout)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(any(item["ok"] for item in payload))


if __name__ == "__main__":
    unittest.main()
