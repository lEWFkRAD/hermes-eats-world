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

from ..capture import capture_window, capture_window_base64
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
from ..target import find_window, list_windows, is_frame_window, drill_frame, WindowTarget
from .env_check import check_environment, set_dpi_awareness
from .logging import setup_console_logging, setup_structured_logging

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False, json_logs: bool = False):
    """Configure logging.

    Args:
        verbose: Use DEBUG level.
        json_logs: Use structured JSON output.
    """
    if json_logs:
        setup_structured_logging(level="DEBUG" if verbose else "INFO", console=True)
    else:
        setup_console_logging(verbose=verbose)


def run_serve(args) -> int:
    """Start the WebSocket server."""
    from .websocket_server import WebSocketServer

    server = WebSocketServer(
        host="127.0.0.1",
        port=args.ws_port,
        token=args.ws_token,
    )

    print(f"Starting WebSocket server on ws://127.0.0.1:{args.ws_port}")
    if args.ws_token:
        print("Auth token: ENABLED")

    try:
        server.run_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    return 0


def run_perceive(args) -> int:
    """Execute the PERCEIVE pipeline: find window → walk tree → classify → output."""
    start = time.time()

    # 1. Find window — returns WindowTarget with metadata + live control
    target_result = find_window(
        title=args.target,
        process_name=args.process,
        class_name=args.cls,
        timeout=5,
        hwnd=args.hwnd,
    )

    if target_result is None:
        query = args.target or args.process or args.cls or "unknown"
        err = make_error("window_not_found", f"Could not find window matching '{query}'", target=query)
        print(err, file=sys.stderr)
        return 1

    target: WindowTarget = target_result
    target_info = target.info
    win = target.control

    logger.info(
        "Found window via %s: %s (PID %d, class %s)",
        target.search_method, target_info.name, target_info.process_id, target_info.class_name,
    )

    # 2. UWP frame drilling (if needed)
    if is_frame_window(target_info.class_name):
        logger.info("Detected ApplicationFrameWindow — drilling for content")
        content = drill_frame(win)
        if content:
            win = content
            logger.info("Drilled to content window: %s", content.ClassName)
        else:
            logger.warning("Frame drilling failed — using frame window")

    # Get patterns at root level
    patterns = get_control_patterns(win)

    # 3. Walk tree
    max_depth = min(args.depth if args.depth is not None else 3, 500)
    root_elem, truncated = element_to_dict(win, depth=0, max_depth=max_depth, from_patterns=patterns)

    if truncated:
        logger.warning("Tree was truncated at depth %d", max_depth)

    # 4. Summarize and classify (operate on Element model, not raw Control)
    summary = summarize_tree(root_elem)
    tier = classify_tier(summary)

    elapsed = time.time() - start

    # 5. Screenshot
    screenshot_path = None
    if args.screenshot and target_info.bounding_box:
        screenshot_path = capture_window(
            target_info.bounding_box,
            target_info.hwnd,
            output_dir=str(Path(__file__).parents[2]),
        )

    # 6. Build snapshot
    snapshot = TreeSnapshot(
        schema_version=SCHEMA_VERSION,
        target=target_info,
        tier=tier,
        summary=summary,
        tree=root_elem,
        screenshot_path=screenshot_path,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    # 7. Output
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

    # Machine-readable output for programmatic consumers (e.g. the desktop app's
    # window picker). Pure JSON on stdout — the env report was routed to stderr.
    if getattr(args, "json", False):
        payload = [
            {
                "name": w.name or "",
                "class_name": w.class_name or "",
                "automation_id": w.automation_id or "",
                "pid": w.process_id,
                "hwnd": w.hwnd,
                "bounding_box": (
                    {
                        "left": w.bounding_box.left,
                        "top": w.bounding_box.top,
                        "width": w.bounding_box.width,
                        "height": w.bounding_box.height,
                    }
                    if w.bounding_box
                    else None
                ),
                "is_enabled": w.is_enabled,
            }
            for w in windows
        ]
        print(json.dumps({"windows": payload}))
        return 0

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


def run_capture(args) -> int:
    """Capture the target window as a base64 PNG and print JSON.

    Powers the desktop live-preview panel, which polls this. Captures the target
    window's full bounding box (the visible app, no UWP drilling) downscaled to
    --capture-width.
    """
    target_result = find_window(
        title=args.target, process_name=args.process, class_name=args.cls, timeout=5,
        hwnd=args.hwnd,
    )
    if target_result is None:
        query = args.target or args.process or args.cls or "unknown"
        print(make_error("window_not_found", f"Could not find window matching '{query}'", target=query),
              file=sys.stderr)
        return 1

    info = target_result.info
    if not info.bounding_box:
        print(make_error("no_bounds", "Target window has no bounding box"), file=sys.stderr)
        return 1

    data_url = capture_window_base64(info.bounding_box, info.hwnd, max_width=args.capture_width)
    if not data_url:
        print(make_error("capture_failed", "Screenshot capture failed"), file=sys.stderr)
        return 1

    print(json.dumps({
        "image": data_url,
        "target": {"name": info.name, "class_name": info.class_name, "pid": info.process_id},
    }))
    return 0


def run_move(args) -> int:
    """Reposition the target window to absolute device pixels (desktop dock mode).

    Used by the desktop to tile the selected app beside the docked Hermes panel.
    """
    import ctypes

    try:
        left, top, width, height = (int(x) for x in args.move.split(","))
    except (ValueError, AttributeError):
        print(make_error("bad_move", "--move expects 'left,top,width,height' integers"), file=sys.stderr)
        return 2

    target_result = find_window(
        title=args.target, process_name=args.process, class_name=args.cls, timeout=5,
        hwnd=args.hwnd,
    )
    if target_result is None:
        query = args.target or args.process or args.cls or "unknown"
        print(make_error("window_not_found", f"Could not find window matching '{query}'", target=query),
              file=sys.stderr)
        return 1

    hwnd = target_result.info.hwnd
    if not hwnd:
        print(make_error("no_hwnd", "Target window has no native handle"), file=sys.stderr)
        return 1

    user32 = ctypes.windll.user32
    SW_RESTORE = 9
    SWP_NOZORDER = 0x0004
    SWP_NOACTIVATE = 0x0010
    user32.ShowWindow(hwnd, SW_RESTORE)
    ok = user32.SetWindowPos(hwnd, 0, left, top, width, height, SWP_NOZORDER | SWP_NOACTIVATE)
    if not ok:
        print(make_error("move_failed", "SetWindowPos failed"), file=sys.stderr)
        return 1

    print(json.dumps({
        "moved": True,
        "rect": {"left": left, "top": top, "width": width, "height": height},
        "target": {"name": target_result.info.name, "pid": target_result.info.process_id},
    }))
    return 0


def run_goal(args) -> int:
    """Execute the orchestrator: PERCEIVE → PLAN → ACT → VERIFY loop."""
    from ..orchestrator import Orchestrator, OrchestratorConfig

    config_kwargs = dict(
        max_steps=args.max_steps,
        max_wait_seconds=args.timeout,
        step_timeout=args.step_timeout,
        retry_count=args.retries,
        retry_delay=args.retry_delay,
        require_verification=not args.no_verify,
    )
    # Only override the orchestrator's perception depth when --depth is given;
    # otherwise use its default (deeper, tuned for nested UWP apps).
    if args.depth is not None:
        config_kwargs["perception_depth"] = args.depth
    config = OrchestratorConfig(**config_kwargs)

    orchestrator = Orchestrator(config=config)

    logger.info("GOAL: %s", args.goal)
    logger.info("Target: title=%s, process=%s, class=%s", args.target, args.process, args.cls)

    result = orchestrator.run(
        goal=args.goal,
        target_title=args.target,
        target_process=args.process,
        target_class=args.cls,
        target_hwnd=args.hwnd,
    )

    # Print results
    print(f"\n{'='*60}")
    print(f"ORCHESTRATOR RESULT")
    print(f"{'='*60}")
    print(f"Goal:        {result.goal}")
    print(f"Status:      {result.status.value}")
    print(f"Steps:       {result.steps_completed}/{result.steps_total}")
    print(f"Elapsed:     {result.elapsed:.1f}s")

    if result.step_results:
        print(f"\nStep Details:")
        print(f"{'-'*60}")
        for sr in result.step_results:
            status_icon = "✓" if sr.status == StepStatus.SUCCESS else "✗"
            print(f"  {status_icon} Step {sr.id}: {sr.description}")
            print(f"    Status: {sr.status.value} ({sr.duration:.1f}s)")
            if sr.error:
                print(f"    Error: {sr.error}")

    if result.error:
        print(f"\nError: {result.error}")

    print(f"{'='*60}\n")

    return 0 if result.status == ExecutionStatus.SUCCESS else 1


# Import enums for run_goal
from ..orchestrator import ExecutionStatus, StepStatus


def _force_utf8_stdio():
    """Ensure stdout/stderr can emit non-ASCII glyphs (⚠ ✓ ✗ ✅) even when
    redirected. On Windows, a piped stdout defaults to cp1252, which raises
    UnicodeEncodeError on these characters (e.g. under subprocess capture)."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def main(argv=None):
    """Main CLI entry point."""
    _force_utf8_stdio()
    parser = argparse.ArgumentParser(
        description="Hermes Eats World — Windows UI perception sidecar",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    parser.add_argument("--json-logs", action="store_true", help="Structured JSON log output")
    parser.add_argument("--list", action="store_true", help="List all visible windows")
    parser.add_argument("--json", action="store_true",
                        help="Emit machine-readable JSON on stdout (env report goes to stderr)")
    parser.add_argument("--target", type=str, help="Window title (substring match)")
    parser.add_argument("--process", type=str, help="Process name (e.g. notepad.exe)")
    parser.add_argument("--class", dest="cls", type=str, help="Window class name")
    parser.add_argument("--hwnd", type=int, default=None,
                        help="Exact native window handle (precise, unambiguous target). "
                             "Preferred over --target when known (avoids wrong-window matches).")
    parser.add_argument("--depth", type=int, default=None,
                        help="Tree walk depth (max: 500). Default: 3 for --target perceive, "
                             "5 for --run-goal (deep enough for nested UWP apps).")
    parser.add_argument("--screenshot", action="store_true", help="Capture window screenshot")
    parser.add_argument("--capture", action="store_true",
                        help="Capture the target window as a base64 PNG and print JSON "
                             "(for the desktop live-preview panel). Use with --target/--process.")
    parser.add_argument("--capture-width", type=int, default=480,
                        help="Max width (px) for --capture output (default: 480)")
    parser.add_argument("--move", type=str, default=None, metavar="L,T,W,H",
                        help="Reposition the target window to absolute device pixels "
                             "left,top,width,height (for desktop dock mode). Restores it first if minimized.")
    parser.add_argument("--output", type=str, help="Output file path (default: stdout)")
    parser.add_argument("--min-size", type=int, default=100, help="Minimum window size for --list (default: 100)")

    # Orchestrator options
    parser.add_argument("--run-goal", type=str, dest="goal",
                        help="Run orchestrator with a goal (e.g. 'click the Save button')")
    parser.add_argument("--max-steps", type=int, default=20,
                        help="Max steps for orchestrator (default: 20)")
    parser.add_argument("--timeout", type=float, default=300.0,
                        help="Total timeout for orchestrator in seconds (default: 300)")
    parser.add_argument("--step-timeout", type=float, default=15.0,
                        help="Timeout per step in seconds (default: 15)")
    parser.add_argument("--retries", type=int, default=2,
                        help="Retries per failed step (default: 2)")
    parser.add_argument("--retry-delay", type=float, default=1.0,
                        help="Delay between retries in seconds (default: 1.0)")
    parser.add_argument("--no-verify", action="store_true",
                        help="Skip verification after each step")

    # WebSocket server options
    parser.add_argument("--serve", action="store_true",
                        help="Start WebSocket server")
    parser.add_argument("--ws-port", type=int, default=8765,
                        help="WebSocket server port (default: 8765)")
    parser.add_argument("--ws-token", type=str, default=None,
                        help="WebSocket auth token")

    args = parser.parse_args(argv)
    setup_logging(args.verbose, json_logs=args.json_logs)

    # Environment check. In --json mode the env report must not pollute stdout
    # (which carries the machine-readable payload), so route it to stderr.
    set_dpi_awareness()
    env = check_environment()
    print(env.report(), file=sys.stderr if args.json else sys.stdout)

    if not env.is_ok:
        logger.error("Environment check failed. Cannot proceed.")
        return 1

    # Route to command
    if args.serve:
        return run_serve(args)

    if args.list:
        return run_list(args)

    if args.capture:
        if not any([args.target, args.process, args.cls, args.hwnd]):
            parser.error("--capture requires --target, --process, or --class")
            return 2
        return run_capture(args)

    if args.move:
        if not any([args.target, args.process, args.cls, args.hwnd]):
            parser.error("--move requires --target, --process, or --class")
            return 2
        return run_move(args)

    if args.goal:
        # Orchestrator mode
        if not any([args.target, args.process, args.cls, args.hwnd]):
            parser.error("--run-goal requires --target, --process, or --class")
            return 2
        return run_goal(args)

    # PERCEIVE requires a target
    if not any([args.target, args.process, args.cls, args.hwnd]):
        parser.error("Specify --list, --target <title>, --hwnd <handle>, --process <name>, --class <class>, or --run-goal")
        return 2

    return run_perceive(args)


if __name__ == "__main__":
    sys.exit(main())
