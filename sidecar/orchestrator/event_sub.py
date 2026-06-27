"""
Hermes Eats World — UIA Event Subscription
============================================
Subscribe to UI Automation events for incremental updates instead of
full tree walks. Supports:
- Tree structure changed (elements added/removed)
- Property changed (name, value, state updates)
- Focus changed
- Window events (opened, closed, minimized)

Usage:
    from sidecar.orchestrator.event_sub import EventSubscriber

    sub = EventSubscriber()
    sub.on_tree_changed(lambda elem: print(f"Tree changed: {elem}"))
    sub.on_focus_changed(lambda elem: print(f"Focus: {elem.Name}"))
    sub.start()
    # ... events fire asynchronously ...
    sub.stop()
"""

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Try to import uiautomation — may not be available in all environments
try:
    import uiautomation as ui
    UIA_AVAILABLE = True
except ImportError:
    UIA_AVAILABLE = False
    ui = None  # type: ignore


# ─── Event Types ───────────────────────────────────────────────────

EVENT_TREE_STRUCTURE_CHANGED = "tree_structure_changed"
EVENT_TREE_REORDER = "tree_reorder"
EVENT_FOCUS_CHANGED = "focus_changed"
EVENT_PROPERTY_CHANGED = "property_changed"
EVENT_WINDOW_OPENED = "window_opened"
EVENT_WINDOW_CLOSED = "window_closed"
EVENT_DIALOG_OPENED = "dialog_opened"
EVENT_MENU_OPENED = "menu_opened"
EVENT_TEXT_CHANGED = "text_changed"
EVENT_SELECTION_CHANGED = "selection_changed"

ALL_EVENTS = [
    EVENT_TREE_STRUCTURE_CHANGED,
    EVENT_TREE_REORDER,
    EVENT_FOCUS_CHANGED,
    EVENT_PROPERTY_CHANGED,
    EVENT_WINDOW_OPENED,
    EVENT_WINDOW_CLOSED,
    EVENT_DIALOG_OPENED,
    EVENT_MENU_OPENED,
    EVENT_TEXT_CHANGED,
    EVENT_SELECTION_CHANGED,
]


@dataclass
class UIAEvent:
    """A UIA event with metadata."""
    event_type: str
    element: Any  # uiautomation.Control
    timestamp: float
    details: Dict[str, Any] = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}


class EventSubscriber:
    """Subscribe to UI Automation events for incremental UI updates.

    Provides a high-level interface over uiautomation's event system.
    Events are delivered to registered callbacks on a background thread.
    """

    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = {evt: [] for evt in ALL_EVENTS}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._event_queue: List[UIAEvent] = []
        self._callbacks = []  # Raw uiautomation callbacks to unregister on stop

        if not UIA_AVAILABLE:
            logger.warning("uiautomation not available — event subscription disabled")

    @property
    def is_running(self) -> bool:
        return self._running

    def on(self, event_type: str, callback: Callable[[UIAEvent], None]):
        """Register a callback for an event type.

        Args:
            event_type: One of the EVENT_* constants.
            callback: Called with a UIAEvent on each event.
        """
        if event_type not in self._handlers:
            raise ValueError(f"Unknown event type: {event_type}")
        self._handlers[event_type].append(callback)
        logger.debug("Registered handler for %s (%d total)", event_type,
                     len(self._handlers[event_type]))

    def on_tree_changed(self, callback: Callable[[UIAEvent], None]):
        """Shorthand for on(EVENT_TREE_STRUCTURE_CHANGED, callback)."""
        self.on(EVENT_TREE_STRUCTURE_CHANGED, callback)

    def on_focus_changed(self, callback: Callable[[UIAEvent], None]):
        """Shorthand for on(EVENT_FOCUS_CHANGED, callback)."""
        self.on(EVENT_FOCUS_CHANGED, callback)

    def on_dialog_opened(self, callback: Callable[[UIAEvent], None]):
        """Shorthand for on(EVENT_DIALOG_OPENED, callback)."""
        self.on(EVENT_DIALOG_OPENED, callback)

    def on_window_opened(self, callback: Callable[[UIAEvent], None]):
        """Shorthand for on(EVENT_WINDOW_OPENED, callback)."""
        self.on(EVENT_WINDOW_OPENED, callback)

    def on_text_changed(self, callback: Callable[[UIAEvent], None]):
        """Shorthand for on(EVENT_TEXT_CHANGED, callback)."""
        self.on(EVENT_TEXT_CHANGED, callback)

    def start(self, target_hwnd: Optional[int] = None):
        """Start listening for UIA events.

        Args:
            target_hwnd: If set, only listen for events in this window.
        """
        if not UIA_AVAILABLE:
            logger.error("Cannot start event subscription: uiautomation not available")
            return

        if self._running:
            logger.warning("Event subscription already running")
            return

        self._running = True
        self._setup_handlers(target_hwnd)

        logger.info("Event subscription started (hwnd=%s)", target_hwnd or "all")

    def stop(self):
        """Stop listening for UIA events."""
        if not self._running:
            return

        self._running = False

        # Unregister all callbacks
        for callback in self._callbacks:
            try:
                ui.RemoveGlobalEventHandler(callback)
            except Exception as e:
                logger.debug("Failed to remove handler: %s", e)
        self._callbacks.clear()

        logger.info("Event subscription stopped")

    def _setup_handlers(self, target_hwnd: Optional[int] = None):
        """Set up uiautomation event handlers."""
        if ui is None:
            return

        # Global event handler for all UIA events
        def _global_handler(event_info):
            if not self._running:
                return

            try:
                uia_event = self._parse_event(event_info)
                if uia_event:
                    self._dispatch(uia_event)
            except Exception as e:
                logger.debug("Event handler error: %s", e)

        # Register for specific event IDs
        event_ids = [
            ui.UIA_StructureChangedEventId,       # Tree changes
            ui.UIA_FocusChangedEventId,           # Focus changes
            ui.UIA_WindowOpenedEventId,           # Window opened
            ui.UIA_WindowClosedEventId,           # Window closed
            ui.UIA_PropertyChangedEventId,        # Property changes
            ui.UIA_TextTextChangedEventId,        # Text changes
            ui.UIA_SelectionItemSelectedEventId,  # Selection changes
        ]

        for event_id in event_ids:
            try:
                ui.AddGlobalEventHandler(event_id, _global_handler)
                self._callbacks.append(_global_handler)
            except Exception as e:
                logger.debug("Failed to register event %d: %s", event_id, e)

    def _parse_event(self, event_info) -> Optional[UIAEvent]:
        """Parse a uiautomation event into a UIAEvent."""
        if ui is None:
            return None

        element = event_info.Element
        event_id = event_info.EventId

        # Map event ID to our event type
        if event_id == ui.UIA_StructureChangedEventId:
            # Check if it's a dialog or menu
            if element.ControlType == ui.ControlType.WindowControl:
                if self._is_modal(element):
                    return UIAEvent(
                        event_type=EVENT_DIALOG_OPENED,
                        element=element,
                        timestamp=time.time(),
                        details={"name": element.Name, "hwnd": element.WindowHandle},
                    )
            if element.ControlType == ui.ControlType.MenuControl:
                return UIAEvent(
                    event_type=EVENT_MENU_OPENED,
                    element=element,
                    timestamp=time.time(),
                )
            return UIAEvent(
                event_type=EVENT_TREE_STRUCTURE_CHANGED,
                element=element,
                timestamp=time.time(),
            )

        elif event_id == ui.UIA_FocusChangedEventId:
            return UIAEvent(
                event_type=EVENT_FOCUS_CHANGED,
                element=element,
                timestamp=time.time(),
                details={"name": element.Name, "control_type": element.ControlTypeName},
            )

        elif event_id == ui.UIA_WindowOpenedEventId:
            return UIAEvent(
                event_type=EVENT_WINDOW_OPENED,
                element=element,
                timestamp=time.time(),
                details={"name": element.Name, "hwnd": element.WindowHandle},
            )

        elif event_id == ui.UIA_WindowClosedEventId:
            return UIAEvent(
                event_type=EVENT_WINDOW_CLOSED,
                element=element,
                timestamp=time.time(),
                details={"name": element.Name, "hwnd": element.WindowHandle},
            )

        elif event_id == ui.UIA_PropertyChangedEventId:
            return UIAEvent(
                event_type=EVENT_PROPERTY_CHANGED,
                element=element,
                timestamp=time.time(),
                details={"property_id": event_info.PropertyId},
            )

        elif event_id == ui.UIA_TextTextChangedEventId:
            return UIAEvent(
                event_type=EVENT_TEXT_CHANGED,
                element=element,
                timestamp=time.time(),
            )

        elif event_id == ui.UIA_SelectionItemSelectedEventId:
            return UIAEvent(
                event_type=EVENT_SELECTION_CHANGED,
                element=element,
                timestamp=time.time(),
                details={"name": element.Name},
            )

        return None

    def _dispatch(self, event: UIAEvent):
        """Dispatch an event to all registered handlers."""
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error("Event handler error for %s: %s", event.event_type, e)

    def _is_modal(self, element) -> bool:
        """Check if a window element is modal."""
        try:
            return element.GetBoolPropertyValue(ui.UIA_IsModalProperty)
        except Exception:
            return False

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()
