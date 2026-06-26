#!/usr/bin/env python3
"""
Hermes Eats World - Phase 0 Spike: Perception
=============================================

Attach to a window, walk the UIA tree, dump structured state as JSON,
capture a frame. Prove we can see app state as data.

Usage:
    python spike.py                          # list all top-level windows
    python spike.py --target "Notepad"       # attach to Notepad
    python spike.py --target "Notepad" --depth 5  # walk tree to depth 5
    python spike.py --target "Notepad" --full   # full tree walk
    python spike.py --target "Notepad" --screenshot  # capture frame
    python spike.py --target "Notepad" --output state.json  # save JSON
"""

import argparse
import hashlib
import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import uiautomation as auto
import mss

# --- Logging setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("hermes-eats-world")

# --- Constants ---
SCHEMA_VERSION = "0.1.0"
MAX_TREE_DEPTH = 500  # Safety cap (Python default recursion ~1000)
SPIKE_DIR = os.path.dirname(os.path.abspath(__file__))


def get_control_patterns(element):
    """Extract available control patterns and their current state."""
    patterns = {}
    failed = []
    
    pattern_defs = [
        ("invoke", "GetInvokePattern", lambda p: {"supported": True}),
        ("value", "GetValuePattern", lambda p: {"supported": True, "value": _truncate(str(p.Value), 500), "readonly": p.IsReadOnly}),
        ("toggle", "GetTogglePattern", lambda p: {"supported": True, "state": p.ToggleState}),
        ("selection", "GetSelectionPattern", lambda p: {"supported": True}),
        ("expand_collapse", "GetExpandCollapsePattern", lambda p: {"supported": True, "state": p.ExpandCollapseState}),
        ("scroll", "GetScrollPattern", lambda p: {"supported": True, "horizontally_scrollable": p.HorizontallyScrollable, "vertically_scrollable": p.VerticallyScrollable}),
        ("transform", "GetTransformPattern", lambda p: {"supported": True, "can_move": p.CanMove, "can_resize": p.CanResize, "can_rotate": p.CanRotate}),
        ("window", "GetWindowPattern", lambda p: {"supported": True, "can_maximize": p.CanMaximize, "can_minimize": p.CanMinimize, "is_modal": p.IsModal, "is_topmost": p.IsTopmost, "window_state": p.WindowVisualState}),
        ("selection_item", "GetSelectionItemPattern", lambda p: {"supported": True, "is_selected": p.IsSelected}),
        ("grid", "GetGridPattern", lambda p: {"supported": True, "row_count": p.RowCount, "column_count": p.ColumnCount}),
        ("text", "GetTextPattern", lambda p: {"supported": True}),
        ("scroll_item", "GetScrollItemPattern", lambda p: {"supported": True}),
        ("dock", "GetDockPattern", lambda p: {"supported": True, "dock": p.Dock}),
    ]
    
    for pattern_name, getter, extract_fn in pattern_defs:
        try:
            p = getattr(element, getter)()
            if p:
                patterns[pattern_name] = extract_fn(p)
        except Exception as e:
            failed.append(pattern_name)
    
    if failed:
        logger.debug("Pattern probe failed for %s on element '%s': %s",
                      failed, _element_label(element), ", ".join(failed))
    
    return patterns


def _element_label(element):
    """Get a short human-readable label for an element."""
    name = (element.Name or "")[:50]
    auto_id = element.AutomationId or ""
    if name and auto_id:
        return f"{name} [{auto_id}]"
    return name or auto_id or "(unnamed)"


def _truncate(text: str, max_len: int) -> str:
    """Truncate text and add '...' indicator if truncated."""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def make_element_id(element) -> str:
    """Generate a stable element ID for cross-snapshot correlation.
    
    Uses a composite of AutomationId, ClassName, Name hash, and bounding rect.
    Falls back to NativeWindowHandle when available.
    """
    parts = []
    
    # Primary: NativeWindowHandle if available (most stable)
    try:
        hwnd = element.NativeWindowHandle
        if hwnd:
            return f"hwnd:{hwnd:x}"
    except Exception:
        pass
    
    # Secondary: AutomationId (often stable but frequently empty)
    auto_id = element.AutomationId or ""
    if auto_id:
        parts.append(f"aid:{auto_id}")
    
    # Tertiary: ClassName
    class_name = element.ClassName or ""
    if class_name:
        parts.append(f"class:{class_name}")
    
    # Quaternary: Name hash (names change, but hashing gives stability)
    name = element.Name or ""
    if name:
        name_hash = hashlib.md5(name.encode("utf-8", errors="replace")).hexdigest()[:8]
        parts.append(f"name:{name_hash}")
    
    # Final fallback: bounding rect (less stable but unique)
    try:
        bbox = element.BoundingRectangle
        if bbox:
            parts.append(f"rect:{int(bbox.left)}x{int(bbox.top)}")
    except Exception:
        pass
    
    if parts:
        return "|".join(parts)
    
    return f"unknown:{id(element)}"


def element_to_dict(element, depth=0, max_depth=MAX_TREE_DEPTH):
    """Convert a UIA element and its subtree to a structured dict."""
    if depth > max_depth:
        return None
    
    # Get bounding rect
    bbox = element.BoundingRectangle
    if bbox is None:
        bbox_dict = None
    else:
        try:
            bbox_dict = {
                "left": int(bbox.left),
                "top": int(bbox.top),
                "width": int(bbox.width()),
                "height": int(bbox.height()),
            }
        except Exception:
            bbox_dict = None
    
    control_type = element.ControlTypeName
    
    elem_dict = {
        "id": make_element_id(element),
        "control_type": control_type,
        "localized_type": element.LocalizedControlType,
        "name": _truncate(element.Name or "", 200),
        "automation_id": element.AutomationId or "",
        "class_name": element.ClassName or "",
        "is_enabled": element.IsEnabled,
        "is_offscreen": element.IsOffscreen,
        "bounding_box": bbox_dict,
        "depth": depth,
        "patterns": get_control_patterns(element),
    }
    
    if depth < max_depth:
        try:
            children = []
            for child in element.GetChildren():
                child_dict = element_to_dict(child, depth + 1, max_depth)
                if child_dict:
                    children.append(child_dict)
            if children:
                elem_dict["children"] = children
        except Exception as e:
            logger.debug("Failed to enumerate children of '%s': %s", _element_label(element), e)
            elem_dict["children"] = []
    
    return elem_dict


def summarize_tree(tree):
    """Produce a summary of the UIA tree in a single pass."""
    total_elements = 0
    max_depth = 0
    control_types: Dict[str, int] = {}
    pattern_counts: Dict[str, int] = {}
    
    def walk(node):
        nonlocal total_elements, max_depth
        total_elements += 1
        max_depth = max(max_depth, node.get("depth", 0))
        
        ct = node.get("control_type", "unknown")
        control_types[ct] = control_types.get(ct, 0) + 1
        
        for pattern_name in node.get("patterns", {}):
            pattern_counts[pattern_name] = pattern_counts.get(pattern_name, 0) + 1
        
        for child in node.get("children", []):
            walk(child)
    
    walk(tree)
    
    return {
        "total_elements": total_elements,
        "max_depth": max_depth,
        "control_types": dict(sorted(control_types.items(), key=lambda x: -x[1])),
        "control_patterns": dict(sorted(pattern_counts.items(), key=lambda x: -x[1])),
    }


def classify_tier(tree):
    """Classify the perception tier based on tree richness.
    
    Returns a structured dict with tier label, numeric confidence (0.0-1.0),
    and supporting evidence for programmatic reasoning.
    """
    summary = summarize_tree(tree)
    total = summary["total_elements"]
    patterns = summary["control_patterns"]
    num_pattern_types = len(patterns)
    
    # Confidence factors (each 0.0-1.0, combined via weighted average)
    # Element richness: 50+ elements = high confidence in T1
    element_score = min(total / 50, 1.0)
    
    # Pattern diversity: 4+ unique pattern types = rich interactivity
    pattern_score = min(num_pattern_types / 4, 1.0)
    
    # Combined confidence
    confidence = round(0.5 * element_score + 0.5 * pattern_score, 2)
    
    if total > 50 and num_pattern_types > 3:
        tier = "T1"
        label = "Rich accessibility tree"
    elif total > 10 and num_pattern_types > 0:
        tier = "T1/T2"
        label = "Partial accessibility tree, may need vision fallback"
    elif total > 5:
        tier = "T2"
        label = "Sparse accessibility tree, vision primary"
    else:
        tier = "T2"
        label = "Minimal accessibility, vision required"
    
    return {
        "tier": tier,
        "label": label,
        "confidence": confidence,
        "evidence": {
            "element_count": total,
            "unique_pattern_types": num_pattern_types,
            "pattern_details": patterns,
        },
    }


def find_window(title=None, process_name=None, class_name=None):
    """Find a window by title (substring match), process name (via PID lookup), or class name."""
    import ctypes
    from ctypes import wintypes

    if title:
        try:
            win = auto.WindowControl(SearchDepth=1, SubName=title)
            if win.Exists(0, 2):
                return win
        except Exception as e:
            logger.debug("Title search failed for '%s': %s", title, e)
    
    if class_name:
        try:
            win = auto.WindowControl(SearchDepth=1, ClassName=class_name)
            if win.Exists(0, 2):
                return win
        except Exception as e:
            logger.debug("Class search failed for '%s': %s", class_name, e)
    
    if process_name:
        try:
            # Enumerate desktop windows and filter by process executable name
            desktop = auto.GetRootControl()
            matching_windows = []
            
            for child in desktop.GetChildren():
                if child.ControlTypeName != "WindowControl":
                    continue
                try:
                    pid = child.ProcessId
                    if pid:
                        # Get process executable name via ctypes (no psutil needed)
                        h_process = ctypes.windll.kernel32.OpenProcess(0x0400 | 0x0010, False, pid)  # PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
                        if h_process:
                            try:
                                exe_name = ctypes.create_unicode_buffer(512)
                                ctypes.windll.psapi.GetModuleFileNameExW(h_process, None, exe_name, 512)
                                exe_basename = os.path.basename(exe_name.value).lower()
                                if process_name.lower() in exe_basename:
                                    matching_windows.append(child)
                            finally:
                                ctypes.windll.kernel32.CloseHandle(h_process)
                except Exception:
                    continue
            
            if matching_windows:
                logger.info("Found %d window(s) from process '%s'", len(matching_windows), process_name)
                return matching_windows[0]
            else:
                logger.warning("No running process matches '%s'", process_name)
        except Exception as e:
            logger.debug("Process search failed for '%s': %s", process_name, e)
    
    return None


def list_windows():
    """List all top-level visible windows."""
    windows = []
    desktop = auto.GetRootControl()
    
    for child in desktop.GetChildren():
        if child.ControlTypeName != "WindowControl":
            continue
        try:
            bbox = child.BoundingRectangle
            if bbox is None:
                continue
            
            w, h = int(bbox.width()), int(bbox.height())
            if w < 100 and h < 100:
                continue
            
            windows.append({
                "name": child.Name or "(untitled)",
                "class_name": child.ClassName or "",
                "automation_id": child.AutomationId or "",
                "process_id": child.ProcessId,
                "bounding_rect": {
                    "left": int(bbox.left),
                    "top": int(bbox.top),
                    "width": w,
                    "height": h,
                },
                "is_enabled": child.IsEnabled,
            })
        except Exception:
            continue
    
    windows.sort(key=lambda w: w["name"].lower())
    return windows


def capture_frame(element, output_path=None):
    """Capture a screenshot of the element's bounding rectangle."""
    try:
        bbox = element.BoundingRectangle
        if bbox is None:
            logger.error("No bounding rectangle for element")
            return None
        
        with mss.MSS() as sct:
            monitor = {
                "left": int(bbox.left),
                "top": int(bbox.top),
                "width": int(bbox.width()),
                "height": int(bbox.height()),
            }
            
            if monitor["width"] <= 0 or monitor["height"] <= 0:
                logger.error("Invalid dimensions for capture: %dx%d", monitor["width"], monitor["height"])
                return None
            
            screenshot = sct.grab(monitor)
            
            if output_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = os.path.join(SPIKE_DIR, f"hermes_spike_{timestamp}.png")
            
            # Convert BGRA to RGB properly
            from PIL import Image as PilImage
            img = PilImage.frombytes("RGBA", screenshot.size, screenshot.bgra, "raw", "BGRA")
            img = img.convert("RGB")
            img.save(output_path)
            
            logger.info("Screenshot saved to: %s", output_path)
            print(f"Screenshot saved to: {output_path}")
            return output_path
    
    except Exception as e:
        logger.error("Screenshot failed: %s", e)
        print(f"ERROR: Screenshot failed: {e}", file=sys.stderr)
        return None


def main():
    parser = argparse.ArgumentParser(description="Hermes Eats World - Phase 0 Perception Spike")
    parser.add_argument("--list", action="store_true", help="List all top-level windows")
    parser.add_argument("--target", type=str, help="Window title (substring match) to target")
    parser.add_argument("--process", type=str, dest="process_name", help="Process/executable name to target (e.g. 'notepad.exe')")
    parser.add_argument("--class", type=str, dest="class_name", help="Window class name to target")
    parser.add_argument("--depth", type=int, default=3, help="Max depth for tree walk (default: 3, max: 500)")
    parser.add_argument("--full", action="store_true", help="Walk full tree (capped at 500)")
    parser.add_argument("--screenshot", action="store_true", help="Capture a screenshot")
    parser.add_argument("--output", type=str, help="Output JSON file path")
    parser.add_argument("--summary-only", action="store_true", help="Only output tree summary")
    
    args = parser.parse_args()
    
    if args.list:
        print("Listing top-level windows...")
        print("=" * 70)
        windows = list_windows()
        if not windows:
            print("No windows found.", file=sys.stderr)
            sys.exit(1)
        
        for i, win in enumerate(windows):
            bbox = win["bounding_rect"]
            print(f"\n[{i+1}] {win['name']}")
            print(f"    Class: {win['class_name']}")
            print(f"    PID: {win['process_id']}")
            print(f"    Rect: ({bbox['left']}, {bbox['top']}) {bbox['width']}x{bbox['height']}")
            print(f"    Enabled: {win['is_enabled']}")
        
        print(f"\nTotal: {len(windows)} windows")
        print("\nUsage: python spike.py --target '<window name>'")
        print("       Or:  python spike.py --process '<exe name>'  OR  python spike.py --class '<class>'")
        return
    
    if not args.target and not args.process_name and not args.class_name:
        print("Usage: python spike.py --list  OR  python spike.py --target '<window name>'")
        print("       Or:  python spike.py --process '<exe name>'  OR  python spike.py --class '<class>'")
        sys.exit(1)
    
    search_label = args.target or args.process_name or args.class_name
    print(f"Searching for window: '{search_label}'")
    target = find_window(title=args.target, process_name=args.process_name, class_name=args.class_name)
    
    if not target:
        print(f"ERROR: Window '{search_label}' not found.", file=sys.stderr)
        print("Try --list to see available windows.", file=sys.stderr)
        sys.exit(1)
    
    print(f"Found: {target.Name} (PID: {target.ProcessId})")
    print(f"Class: {target.ClassName}")
    bbox = target.BoundingRectangle
    if bbox:
        print(f"Rect: ({int(bbox.left)}, {int(bbox.top)}) {int(bbox.width())}x{int(bbox.height())}")
    
    max_depth = min(MAX_TREE_DEPTH, MAX_TREE_DEPTH if args.full else args.depth)
    print(f"\nWalking UIA tree (max depth: {max_depth})...")
    if args.full:
        logger.warning("Full tree walk requested — capped at depth %d for safety", MAX_TREE_DEPTH)
        print(f"WARNING: Full tree walk capped at depth {MAX_TREE_DEPTH} to prevent stack overflow")
    start_time = time.time()
    
    tree = element_to_dict(target, depth=0, max_depth=max_depth)
    
    elapsed = time.time() - start_time
    print(f"Tree walk completed in {elapsed:.2f}s")
    
    summary = summarize_tree(tree)
    tier_info = classify_tier(tree)
    
    print(f"\n{'='*60}")
    print(f"PERCEPTION SPIKE RESULTS")
    print(f"{'='*60}")
    print(f"Target: {target.Name}")
    print(f"Class: {target.ClassName}")
    print(f"Process ID: {target.ProcessId}")
    print(f"\nTree Statistics:")
    print(f"  Total elements: {summary['total_elements']}")
    print(f"  Max depth: {summary['max_depth']}")
    print(f"  Walk time: {elapsed:.2f}s")
    print(f"\nTier Classification: {tier_info['tier']} ({tier_info['label']})")
    print(f"  Confidence: {tier_info['confidence']}")
    print(f"\nControl Types (top 10):")
    for ct, count in list(summary['control_types'].items())[:10]:
        print(f"  {ct}: {count}")
    
    if summary['control_patterns']:
        print(f"\nControl Patterns found:")
        for pattern, count in summary['control_patterns'].items():
            print(f"  {pattern}: {count}")
    
    if args.screenshot:
        print(f"\nCapturing frame...")
        capture_frame(target)
    
    output = {
        "schema_version": SCHEMA_VERSION,
        "timestamp": datetime.now().isoformat(),
        "target": {
            "name": target.Name,
            "class_name": target.ClassName,
            "process_id": target.ProcessId,
            "bounding_rect": {
                "left": int(bbox.left) if bbox else None,
                "top": int(bbox.top) if bbox else None,
                "width": int(bbox.width()) if bbox else None,
                "height": int(bbox.height()) if bbox else None,
            },
        },
        "tier": tier_info,
        "summary": summary,
        "tree": tree,
    }
    
    json_str = json.dumps(output, indent=2, default=str)
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(json_str)
        print(f"\nJSON output saved to: {args.output}")
    elif not args.summary_only:
        print(f"\n{'='*60}")
        print(f"STRUCTURED STATE (JSON):")
        print(f"{'='*60}")
        if len(json_str) > 80000:
            print(json_str[:80000])
            print(f"\n... [truncated, total {len(json_str)} chars. Use --output to save full JSON]")
        else:
            print(json_str)
    
    print(f"\n{'='*60}")
    print(f"SPIKE RESULT: Perception working!")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
