#!/usr/bin/env python3
"""
Hermes Eats World — CLI Entry Point
====================================
Command-line interface for the sidecar. Supports:
- Window discovery (--list)
- Window targeting (--target, --process, --class)
- Tree walking with configurable depth
- Screenshot capture
- JSON output to stdout or file

Usage:
    python -m sidecar.service.cli --list
    python -m sidecar.service.cli --target "File Explorer" --depth 5
    python -m sidecar.service.cli --process notepad.exe --screenshot
"""

import argparse
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from ..capture import capture_window
from ..schema import (
    SCHEMA_VERSION,
    Element,
    TierClassification,
    TreeSnapshot,
    TreeSummary,
    make_error,
    serialize_model,
)
from ..target import find_window, list_windows
from .env_check import check_environment, set_dpi_awareness
from .isolation import run_isolated
from .worker import perceive_hwnd

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def run_perceive(args) -> int:
    """Execute the PERCEIVE pipeline: find window → walk tree → classify → output."""
    start = time.time()

    # 1. Find window
    target = find_window(
        title=args.target,
        process_name=args.process,
        class_name=args.cls,
        timeout=5,
    )

    if target is None:
        query = args.target or args.process or args.cls or "unknown"
        err = make_error(
            "window_not_found", f"Could not find window matching '{query}'", target=query
        )
        print(err, file=sys.stderr)
        return 1

    logger.info(
        "Found window: %s (PID %d, class %s)", target.name, target.process_id, target.class_name
    )

    return run_perceive_isolated(args, target, start)


def run_perceive_isolated(args, target, start: float) -> int:
    """Run the blocking perception phase in a disposable worker process."""
    if not target.hwnd:
        print(
            make_error(
                "window_attach_failed",
                "Target has no usable window handle",
                target=target.name,
            ),
            file=sys.stderr,
        )
        return 1

    worker_result = run_isolated(
        perceive_hwnd,
        {
            "hwnd": target.hwnd,
            "class_name": target.class_name,
            "max_depth": min(args.depth, 50),
            "include_raw_values": args.include_raw_values,
            "max_elements": args.max_elements,
            "timeout": args.timeout,
        },
        timeout=args.timeout + 1,
    )
    if worker_result.status != "success":
        code = {
            "timeout": "tree_worker_timeout",
            "crash": "tree_worker_crashed",
            "error": "tree_worker_failed",
        }.get(worker_result.status, "tree_worker_failed")
        print(
            make_error(
                code,
                worker_result.error or "Perception worker failed",
                target=target.name,
                retryable=worker_result.status in {"timeout", "crash"},
                details={"exit_code": worker_result.exit_code},
            ),
            file=sys.stderr,
        )
        return 1

    payload = worker_result.value
    root_elem = Element.model_validate(payload["tree"])
    summary = TreeSummary.model_validate(payload["summary"])
    tier = TierClassification.model_validate(payload["tier"])
    if payload["truncated"]:
        logger.warning("Tree was truncated at depth %d", args.depth)

    screenshot_path = None
    if args.screenshot and target.bounding_box:
        screenshot_path = capture_window(
            target.bounding_box,
            target.hwnd,
            output_dir=str(Path(__file__).parents[2]),
        )

    snapshot = TreeSnapshot(
        schema_version=SCHEMA_VERSION,
        target=target,
        tier=tier,
        summary=summary,
        tree=root_elem,
        screenshot_path=screenshot_path,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    output_json = serialize_model(snapshot)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_json, encoding="utf-8")
        logger.info("Saved snapshot to %s", output_path)
    else:
        print(output_json)

    logger.info(
        "PERCEIVE complete: %d elements, tier=%s (confidence=%.2f), %.1fs",
        summary.total_elements,
        tier.tier,
        tier.confidence,
        time.time() - start,
    )
    return 0


def run_list(args) -> int:
    """List all visible windows."""
    windows = list_windows(min_size=(args.min_size, args.min_size))
    if not windows:
        print("No visible windows found.")
        return 0

    # Table output
    print(f"\n{'Name':<40} {'Class':<25} {'PID':<8} {'Size':<12} {'AutomationId'}")
    print("-" * 100)
    for w in windows:
        size_str = ""
        if w.bounding_box:
            size_str = f"{w.bounding_box.width}x{w.bounding_box.height}"
        name = w.name[:38] if w.name else "(unnamed)"
        cls = w.class_name[:23] if w.class_name else ""
        aid = w.automation_id[:15] if w.automation_id else ""
        print(f"{name:<40} {cls:<25} {w.process_id:<8} {size_str:<12} {aid}")

    print(f"\nTotal: {len(windows)} windows")
    return 0


def main(argv=None):
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Hermes Eats World — Windows UI perception sidecar",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    parser.add_argument("--list", action="store_true", help="List all visible windows")
    parser.add_argument("--target", type=str, help="Window title (substring match)")
    parser.add_argument("--process", type=str, help="Process name (e.g. notepad.exe)")
    parser.add_argument("--class", dest="cls", type=str, help="Window class name")
    parser.add_argument(
        "--depth",
        type=int,
        choices=range(0, 51),
        default=3,
        metavar="0..50",
        help="Tree walk depth (default: 3, max: 50)",
    )
    parser.add_argument(
        "--max-elements",
        type=int,
        default=5000,
        help="Maximum elements per snapshot (default: 5000)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Total tree-walk deadline in seconds (default: 30)",
    )
    parser.add_argument(
        "--include-raw-values",
        action="store_true",
        help="Include sensitive UI values instead of redacting them",
    )
    parser.add_argument("--screenshot", action="store_true", help="Capture window screenshot")
    parser.add_argument("--output", type=str, help="Output file path (default: stdout)")
    parser.add_argument(
        "--min-size", type=int, default=100, help="Minimum window size for --list (default: 100)"
    )

    args = parser.parse_args(argv)
    setup_logging(args.verbose)

    if args.max_elements < 1:
        parser.error("--max-elements must be at least 1")
    if args.timeout <= 0:
        parser.error("--timeout must be greater than 0")

    # Environment check
    set_dpi_awareness()
    env = check_environment()
    print(env.report(), file=sys.stderr)

    if not env.is_ok:
        logger.error("Environment check failed. Cannot proceed.")
        return 1

    # Route to command
    if args.list:
        return run_list(args)

    # PERCEIVE requires a target
    if not any([args.target, args.process, args.cls]):
        parser.error("Specify --list, --target <title>, --process <name>, or --class <class>")
        return 2

    return run_perceive(args)


if __name__ == "__main__":
    sys.exit(main())
