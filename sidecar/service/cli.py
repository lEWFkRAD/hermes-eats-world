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
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from ..capture import capture_window
from ..perception import classify_tier, element_to_dict, get_control_patterns, summarize_tree
from ..schema import (
    SCHEMA_VERSION,
    Element as ElementModel,
    ErrorResponse,
    make_error,
    serialize_model,
    TreeSnapshot,
    TreeSummary,
    TierClassification,
    WindowInfo,
)
from ..target import find_window, list_windows, is_frame_window, drill_frame
from .env_check import check_environment, set_dpi_awareness

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
        err = make_error("window_not_found", f"Could not find window matching '{query}'", target=query)
        print(err, file=sys.stderr)
        return 1

    logger.info("Found window: %s (PID %d, class %s)", target.name, target.process_id, target.class_name)

    # 2. Attach and walk tree
    import uiautomation

    win = uiautomation.WindowControl(
        searchDepth=1,
        SubName=target.name,
    )
    if not win.Exists(0, 3):
        err = make_error("window_attach_failed", f"Could not attach to window '{target.name}'", target=target.name)
        print(err, file=sys.stderr)
        return 1

    # UWP frame drilling
    if is_frame_window(target.class_name):
        logger.info("Detected ApplicationFrameWindow — drilling for content")
        content = drill_frame(win)
        if content:
            win = content
            logger.info("Drilled to content window: %s", content.ClassName)
        else:
            logger.warning("Frame drilling failed — using frame window")

    # Get patterns at root level
    patterns = get_control_patterns(win)

    # Walk tree
    max_depth = min(args.depth, 500)
    root_elem, truncated = element_to_dict(win, depth=0, max_depth=max_depth, from_patterns=patterns)

    if truncated:
        logger.warning("Tree was truncated at depth %d", max_depth)

    # 3. Summarize and classify
    summary = summarize_tree(win)
    tier = classify_tier(summary)

    elapsed = time.time() - start

    # 4. Screenshot
    screenshot_path = None
    if args.screenshot and target.bounding_box:
        screenshot_path = capture_window(
            target.bounding_box,
            target.hwnd,
            output_dir=str(Path(__file__).parents[2]),
        )

    # 5. Build snapshot
    snapshot = TreeSnapshot(
        schema_version=SCHEMA_VERSION,
        target=target,
        tier=tier,
        summary=summary,
        tree=root_elem,
        screenshot_path=screenshot_path,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    # 6. Output
    output_json = serialize_model(snapshot)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(output_json)
        logger.info("Saved snapshot to %s", output_path)
    else:
        # Truncate stdout output for readability
        if len(output_json) > 80000:
            print(output_json[:80000])
            print("... [output truncated, use --output for full JSON]")
        else:
            print(output_json)

    logger.info(
        "PERCEIVE complete: %d elements, tier=%s (confidence=%.2f), %.1fs",
        summary.total_elements, tier.tier, tier.confidence, elapsed,
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
    parser.add_argument("--depth", type=int, default=3, help="Tree walk depth (default: 3, max: 500)")
    parser.add_argument("--screenshot", action="store_true", help="Capture window screenshot")
    parser.add_argument("--output", type=str, help="Output file path (default: stdout)")
    parser.add_argument("--min-size", type=int, default=100, help="Minimum window size for --list (default: 100)")

    args = parser.parse_args(argv)
    setup_logging(args.verbose)

    # Environment check
    set_dpi_awareness()
    env = check_environment()
    print(env.report())

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
