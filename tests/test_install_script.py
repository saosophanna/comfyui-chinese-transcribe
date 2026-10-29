"""The one-command installer runs in check mode without side effects."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _loader import PACKAGE_DIR


def load_installer():
    spec = importlib.util.spec_from_file_location(
        "install_script", PACKAGE_DIR / "install.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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

    def test_detects_versioned_venv_layout(self):
        # RunPod-Slim places ComfyUI's env at .venv-cu128, not .venv.
        installer = load_installer()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "ComfyUI"
            package = root / "custom_nodes" / "comfyui-chinese-transcribe"
            package.mkdir(parents=True)
            venv_bin = root / ".venv-cu128" / (
                "Scripts" if os.name == "nt" else "bin"
            )
            venv_bin.mkdir(parents=True)
            python = venv_bin / ("python.exe" if os.name == "nt" else "python")
            python.write_bytes(b"")

            original = installer.HERE
            installer.HERE = package
            try:
                candidates = installer._comfy_python_candidates()
            finally:
                installer.HERE = original

        self.assertIn(python, candidates)


if __name__ == "__main__":
    unittest.main()
