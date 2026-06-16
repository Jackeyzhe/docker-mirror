import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "docker-mirror" / "scripts" / "patch_daemon_json.py"


class PatchDaemonJsonTest(unittest.TestCase):
    def run_script(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_empty_config_generates_registry_mirrors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            daemon_path = Path(directory) / "daemon.json"
            result = self.run_script(
                "--daemon-json",
                str(daemon_path),
                "--mirror",
                "https://mirror.example.com",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"registry-mirrors"', result.stdout)
        self.assertIn('"https://mirror.example.com"', result.stdout)

    def test_preserves_existing_daemon_fields_when_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            daemon_path = Path(directory) / "daemon.json"
            daemon_path.write_text('{"debug": true}\n', encoding="utf-8")
            result = self.run_script(
                "--daemon-json",
                str(daemon_path),
                "--mirror",
                "https://mirror.example.com",
                "--write",
            )
            written = json.loads(daemon_path.read_text(encoding="utf-8"))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(written["debug"])
        self.assertEqual(written["registry-mirrors"], ["https://mirror.example.com"])

    def test_append_and_replace_modes_deduplicate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            daemon_path = Path(directory) / "daemon.json"
            daemon_path.write_text(
                json.dumps({"registry-mirrors": ["https://old.example.com"]}),
                encoding="utf-8",
            )
            append_result = self.run_script(
                "--daemon-json",
                str(daemon_path),
                "--mirror",
                "https://old.example.com",
                "--mirror",
                "https://new.example.com",
                "--write",
            )
            appended = json.loads(daemon_path.read_text(encoding="utf-8"))
            replace_result = self.run_script(
                "--daemon-json",
                str(daemon_path),
                "--mirror",
                "https://new.example.com",
                "--mirror",
                "https://new.example.com/",
                "--mode",
                "replace",
                "--write",
            )
            replaced = json.loads(daemon_path.read_text(encoding="utf-8"))

        self.assertEqual(append_result.returncode, 0, append_result.stderr)
        self.assertEqual(
            appended["registry-mirrors"],
            ["https://old.example.com", "https://new.example.com"],
        )
        self.assertEqual(replace_result.returncode, 0, replace_result.stderr)
        self.assertEqual(replaced["registry-mirrors"], ["https://new.example.com"])

    def test_invalid_json_errors_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            daemon_path = Path(directory) / "daemon.json"
            daemon_path.write_text("{not-json", encoding="utf-8")
            result = self.run_script(
                "--daemon-json",
                str(daemon_path),
                "--mirror",
                "https://mirror.example.com",
                "--write",
            )
            content = daemon_path.read_text(encoding="utf-8")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid JSON", result.stderr)
        self.assertEqual(content, "{not-json")


if __name__ == "__main__":
    unittest.main()
