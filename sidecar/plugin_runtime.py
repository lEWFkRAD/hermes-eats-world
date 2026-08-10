"""Profile-owned runtime setup and subprocess transport for the Hermes plugin."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

PLUGIN_VERSION = "1.1.0"
PLUGIN_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_REQUIREMENTS = Path(__file__).with_name("runtime-requirements.txt")


def hermes_home() -> Path:
    configured = os.environ.get("HERMES_HOME")
    return Path(configured).expanduser() if configured else Path.home() / ".hermes"


def runtime_dir() -> Path:
    override = os.environ.get("HEAW_RUNTIME_DIR")
    if override:
        return Path(override).expanduser()
    return hermes_home() / "plugin-runtimes" / "hermes-eats-world" / PLUGIN_VERSION


def runtime_python(path: Path | None = None) -> Path:
    root = path or runtime_dir()
    return root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def runtime_available() -> bool:
    return sys.platform == "win32" and runtime_python().is_file()


def _run_checked(command: list[str], *, timeout: int = 300) -> None:
    completed = subprocess.run(
        command,
        cwd=PLUGIN_ROOT,
        stdin=subprocess.DEVNULL,
        text=True,
        timeout=timeout,
    )
    if completed.returncode:
        raise RuntimeError(f"Command failed with exit code {completed.returncode}: {command[0]}")


def setup_runtime(*, force: bool = False) -> Path:
    """Build a versioned runtime without installing dependencies into Hermes itself."""
    if sys.platform != "win32":
        raise RuntimeError("Hermes Eats World requires native Windows.")

    target = runtime_dir()
    if runtime_python(target).is_file() and not force:
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    # Keep transient names short. Hermes profile roots are already deep on
    # Windows, and venv/ensurepip can otherwise cross the legacy MAX_PATH
    # boundary while unpacking bundled wheels.
    staging = target.parent / f".stg-{uuid.uuid4().hex[:8]}"
    backup = target.parent / f".bak-{uuid.uuid4().hex[:8]}"
    try:
        _run_checked([sys.executable, "-m", "venv", str(staging)])
        staged_python = runtime_python(staging)
        _run_checked(
            [
                str(staged_python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-input",
                "--upgrade",
                "pip",
            ]
        )
        _run_checked(
            [
                str(staged_python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-input",
                "--requirement",
                str(RUNTIME_REQUIREMENTS),
            ]
        )
        _run_checked(
            [
                str(staged_python),
                "-c",
                "import sidecar, uiautomation; print('Hermes Eats World runtime ready')",
            ],
            timeout=60,
        )

        if target.exists():
            target.replace(backup)
        staging.replace(target)
        if backup.exists():
            shutil.rmtree(backup)
        return target
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        if backup.exists() and not target.exists():
            backup.replace(target)
        raise


def run_runtime_worker(request: dict[str, Any], *, timeout: float) -> dict[str, Any]:
    """Run a single JSON request in the killable, profile-owned runtime."""
    python = runtime_python()
    if not python.is_file():
        return {
            "error": "runtime_unavailable",
            "message": "The isolated UIA runtime is not installed.",
            "retryable": False,
        }

    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    process = subprocess.Popen(
        [str(python), "-m", "sidecar.plugin_worker"],
        cwd=PLUGIN_ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=creationflags,
    )
    try:
        stdout, _stderr = process.communicate(json.dumps(request), timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        return {
            "error": "tree_worker_timeout",
            "message": "The isolated UIA worker exceeded its deadline and was terminated.",
            "retryable": True,
        }

    if process.returncode:
        return {
            "error": "tree_worker_failed",
            "message": "The isolated UIA worker failed without returning a safe result.",
            "retryable": True,
        }
    try:
        result = json.loads(stdout)
    except (TypeError, json.JSONDecodeError):
        return {
            "error": "tree_worker_invalid_output",
            "message": "The isolated UIA worker returned invalid JSON.",
            "retryable": True,
        }
    if not isinstance(result, dict):
        return {
            "error": "tree_worker_invalid_output",
            "message": "The isolated UIA worker returned an invalid result shape.",
            "retryable": True,
        }
    return result


def configure_cli(parser: argparse.ArgumentParser) -> None:
    subcommands = parser.add_subparsers(dest="heaw_command", required=True)
    setup = subcommands.add_parser("setup", help="Create the isolated UIA runtime")
    setup.add_argument("--force", action="store_true", help="Rebuild this version's runtime")
    subcommands.add_parser("status", help="Show the active profile runtime status")


def handle_cli(args: argparse.Namespace) -> int:
    if args.heaw_command == "status":
        state = "ready" if runtime_available() else "not installed"
        print(f"Hermes Eats World {PLUGIN_VERSION}: {state}")
        print(f"Runtime: {runtime_dir()}")
        return 0 if runtime_available() else 1

    try:
        target = setup_runtime(force=bool(args.force))
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"Setup failed: {exc}", file=sys.stderr)
        return 1
    print(f"Hermes Eats World {PLUGIN_VERSION} runtime ready: {target}")
    print("Restart this profile's gateway before using uia_perceive_window.")
    return 0
