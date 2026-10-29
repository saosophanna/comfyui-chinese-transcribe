#!/usr/bin/env python3
"""One-command installer for the ComfyUI Chinese transcription nodes.

Run from this folder after cloning it into ``ComfyUI/custom_nodes``:

    python install.py

The script re-executes itself with ComfyUI's bundled Python when it can find
``python_embeded``, ``.venv`` or ``venv`` next to ``custom_nodes``. It then
installs ``requirements.txt`` with pip and reports the FFmpeg status. It is
safe to run repeatedly.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REQUIREMENTS = HERE / "requirements.txt"
REEXEC_ENV = "COMFY_TRANSCRIBE_INSTALL_REEXEC"
MIN_PYTHON = (3, 9)


def _log(message: str) -> None:
    print(f"[install] {message}", flush=True)


def _comfy_python_candidates() -> list[Path]:
    """Possible ComfyUI interpreters next to custom_nodes."""
    # HERE = <ComfyUI>/custom_nodes/<this-package>
    comfy_root = HERE.parent.parent
    exe = "python.exe" if os.name == "nt" else "python"
    bin_dir = "Scripts" if os.name == "nt" else "bin"
    candidates = [comfy_root / "python_embeded" / exe]

    # RunPod images use names such as .venv-cu128; desktop builds may use
    # .venv or venv. Accept any versioned variant.
    for pattern in (".venv*", "venv*"):
        for base in sorted(comfy_root.glob(pattern)):
            if base.is_dir():
                candidates.append(base / bin_dir / exe)

    unique: list[Path] = []
    for candidate in candidates:
        if candidate not in unique:
            unique.append(candidate)
    return unique


def _is_comfy_python() -> bool:
    """True when this is ComfyUI's Python or it can import folder_paths."""
    try:
        if importlib.util.find_spec("folder_paths") is not None:
            return True
    except (ImportError, ValueError):
        pass

    current = Path(sys.executable).resolve()
    for candidate in _comfy_python_candidates():
        try:
            if candidate.resolve() == current:
                return True
        except OSError:
            continue
    return False


def _find_comfy_python() -> Path | None:
    """Look for a different Python next to custom_nodes."""
    current = Path(sys.executable).resolve()
    for candidate in _comfy_python_candidates():
        if not candidate.is_file():
            continue
        try:
            if candidate.resolve() == current:
                continue
        except OSError:
            pass
        return candidate
    return None


def _maybe_reexec(argv: list[str]) -> int | None:
    """Run the installer again with ComfyUI's Python, when one is found."""
    if os.environ.get(REEXEC_ENV) == "1" or "--no-reexec" in argv:
        return None
    if _is_comfy_python():
        return None

    python = _find_comfy_python()
    if python is None:
        return None

    _log(f"Found ComfyUI's Python: {python}")
    _log("Restarting the installer with that interpreter...")
    environment = dict(os.environ)
    environment[REEXEC_ENV] = "1"
    command = [str(python), str(Path(__file__).resolve())]
    command += [argument for argument in argv if argument != "--no-reexec"]

    try:
        return subprocess.call(command, env=environment)
    except OSError as exc:
        _log(f"Could not use that Python ({exc}); continuing with the current one.")
        return None


def _resolve_binary(name: str, env_var: str) -> str:
    override = os.environ.get(env_var)
    if override:
        path = Path(override).expanduser()
        if path.is_file():
            return str(path)
    return shutil.which(name) or ""


def _report_environment() -> None:
    _log(f"Python: {sys.version.split()[0]} ({sys.executable})")
    _log(f"Package: {HERE}")
    _log(f"Requirements: {REQUIREMENTS}")

    ffmpeg = _resolve_binary("ffmpeg", "FFMPEG_BINARY")
    ffprobe = _resolve_binary("ffprobe", "FFPROBE_BINARY")
    _log(f"ffmpeg: {ffmpeg or 'NOT FOUND'}")
    _log(f"ffprobe: {ffprobe or 'NOT FOUND'}")

    try:
        from importlib import metadata

        for package in ("funasr", "requests"):
            try:
                version = metadata.version(package)
            except metadata.PackageNotFoundError:
                version = "not installed"
            _log(f"{package}: {version}")
    except Exception:  # metadata is best-effort only
        pass

    if not ffmpeg or not ffprobe:
        _print_ffmpeg_help()


def _print_ffmpeg_help() -> None:
    _log("")
    _log("WARNING: FFmpeg/ffprobe were not found on PATH.")
    _log("Audio extraction and VAD will fail until FFmpeg is installed.")
    _log("  Windows:  winget install Gyan.FFmpeg")
    _log("  macOS:    brew install ffmpeg")
    _log("  Linux:    sudo apt install ffmpeg")
    _log("Or set FFMPEG_BINARY/FFPROBE_BINARY to the executables.")
    _log("Restart ComfyUI after installing FFmpeg.")


def _torch_version() -> str:
    try:
        from importlib import metadata

        return metadata.version("torch")
    except Exception:
        return ""


def _install_requirements() -> int:
    if not REQUIREMENTS.is_file():
        _log(f"ERROR: {REQUIREMENTS} is missing.")
        return 1

    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "--version"],
            stdout=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, OSError):
        _log("ERROR: pip is not available in this Python.")
        _log(f'  "{sys.executable}" -m ensurepip --upgrade')
        return 1

    torch_before = _torch_version()
    _log("Installing dependencies with pip (this can take a few minutes)...")
    command = [
        sys.executable,
        "-m", "pip", "install",
        "-r", str(REQUIREMENTS),
    ]
    try:
        subprocess.check_call(command)
    except subprocess.CalledProcessError as exc:
        _log("")
        _log(f"pip failed with exit code {exc.returncode}.")
        _log("Check the network/proxy, then run it manually to see the full log:")
        _log(f'  "{sys.executable}" -m pip install -r "{REQUIREMENTS}"')
        _log("If pip offers to replace ComfyUI's CUDA torch, keep the GPU build.")
        return exc.returncode or 1
    except OSError as exc:
        _log(f"ERROR: could not run pip: {exc}")
        return 1

    torch_after = _torch_version()
    if torch_before and torch_after and torch_before != torch_after:
        _log("")
        _log(
            f"WARNING: torch changed from {torch_before} to {torch_after}. "
            "If that replaced ComfyUI's CUDA build with a CPU build, "
            "reinstall the matching torch version for your GPU."
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    parser = argparse.ArgumentParser(
        description="Install the Chinese transcription nodes into ComfyUI."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Report the environment and exit without installing anything.",
    )
    parser.add_argument(
        "--no-reexec",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(argv)

    if sys.version_info < MIN_PYTHON:
        _log(
            f"ERROR: Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ is required; "
            f"this is {sys.version.split()[0]}."
        )
        return 1

    reexec_code = _maybe_reexec(argv)
    if reexec_code is not None:
        return reexec_code

    if not _is_comfy_python() and not args.no_reexec:
        _log("")
        _log("WARNING: this does not look like ComfyUI's Python environment")
        _log("(folder_paths was not found and no bundled Python was detected).")
        _log("If ComfyUI uses another Python, run the installer with it, e.g.:")
        _log('  "<ComfyUI>/python_embeded/python.exe" install.py   (Windows)')
        _log('  "<ComfyUI>/.venv/bin/python" install.py            (Linux/macOS)')

    _report_environment()
    if args.check:
        return 0

    code = _install_requirements()
    if code != 0:
        return code

    _log("")
    _report_environment()
    _log("")
    _log("Done. Restart ComfyUI to load the nodes.")
    _log("They appear under Audio -> Transcribe.")
    _log("The first transcription downloads FunASR model weights.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
