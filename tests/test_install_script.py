"""The one-command installer runs in check mode without side effects."""

from __future__ import annotations

import subprocess
import sys
import unittest

from _loader import PACKAGE_DIR


class InstallScriptTests(unittest.TestCase):
    def test_check_mode_reports_without_installing(self):
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                str(PACKAGE_DIR / "install.py"),
                "--check",
                "--no-reexec",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        output = (result.stdout or "") + (result.stderr or "")
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("[install] Python:", result.stdout)
        self.assertIn("[install] ffmpeg:", result.stdout)
        self.assertNotIn("Installing dependencies", result.stdout)


if __name__ == "__main__":
    unittest.main()
