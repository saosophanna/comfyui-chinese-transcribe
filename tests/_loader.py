"""Load the custom node package the way ComfyUI does, offline.

ComfyUI imports a custom node folder through ``spec_from_file_location`` with
the folder name as the module name, so this helper reproduces that and lets
the tests exercise relative imports and registration exactly as ComfyUI does.

``requests`` is stubbed when it is not installed; FunASR and FFmpeg are never
imported by the import-time code paths.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
import types
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parents[1]
MODULE_NAME = "comfyui_chinese_transcribe"


def _ensure_requests() -> None:
    try:
        importlib.import_module("requests")
        return
    except ModuleNotFoundError:
        pass

    stub = types.ModuleType("requests")

    class RequestException(Exception):
        pass

    class Session:
        def __init__(self):
            self.headers = {}

        def get(self, *args, **kwargs):
            raise RuntimeError("Network access is disabled in the offline tests.")

        def post(self, *args, **kwargs):
            raise RuntimeError("Network access is disabled in the offline tests.")

    def get(*args, **kwargs):
        raise RuntimeError("Network access is disabled in the offline tests.")

    stub.RequestException = RequestException
    stub.Session = Session
    stub.get = get
    stub.Response = type("Response", (), {})
    sys.modules["requests"] = stub


def load_package():
    """Import the package once and return the module."""
    _ensure_requests()
    if MODULE_NAME in sys.modules:
        return sys.modules[MODULE_NAME]

    spec = importlib.util.spec_from_file_location(
        MODULE_NAME,
        PACKAGE_DIR / "__init__.py",
        submodule_search_locations=[str(PACKAGE_DIR)],
    )
    if spec is None or spec.loader is None:  # pragma: no cover
        raise ImportError(f"Cannot load package from {PACKAGE_DIR}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


def load_module(name: str):
    """Import a submodule such as ``transcript`` and return it."""
    load_package()
    return importlib.import_module(f"{MODULE_NAME}.{name}")
