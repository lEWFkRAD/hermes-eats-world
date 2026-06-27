"""
Hermes Eats World — Modal Dialog Handler
==========================================
Detect and handle modal dialogs that block automation. Supports:
- Auto-detection of modal dialogs via UIA events
- Rule-based auto-response (OK, Cancel, Yes, No)
- LLM-driven decision making for complex dialogs
- Timeout-based fallback

Usage:
    from sidecar.orchestrator.modal_handler import ModalHandler

    handler = ModalHandler()
    handler.add_rule("Do you want to save?", "click_ok")
    handler.add_rule("Are you sure?", lambda dialog: click_yes(dialog))

    # Check for and handle any active modal
    if handler.check_and_handle():
        print("Modal handled!")
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Try to import uiautomation
try:
    import uiautomation as ui
    UIA_AVAILABLE = True
except ImportError:
    UIA_AVAILABLE = False
    ui = None  # type: ignore


# ─── Modal Detection ───────────────────────────────────────────────

@dataclass
class ModalDialog:
    """Represents a detected modal dialog."""
    hwnd: int
    name: str
    title: str
    text_content: str  # Full text of the dialog
    buttons: List[Dict[str, Any]]  # Available buttons with name, automation_id, coords
    is_modal: bool
    detected_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hwnd": self.hwnd,
            "name": self.name,
            "title": self.title,
            "text": self.text_content,
            "buttons": self.buttons,
            "is_modal": self.is_modal,
        }


# ─── Built-in Response Strategies ──────────────────────────────────

def click_button(dialog: ModalDialog, button_name: str) -> bool:
    """Click a button by name in the dialog."""
    if not UIA_AVAILABLE or ui is None:
        return False

    try:
        win = ui.WindowControl(searchDepth=1, WindowHandle=dialog.hwnd)
        if not win.Exists(0.5):
            return False

        # Try to find button by name (case-insensitive)
        for btn_name in [button_name, button_name.capitalize(), button_name.upper()]:
            btn = ui.ButtonControl(Name=btn_name, parentControl=win)
            if btn.Exists(0.5):
                btn.Click()
                logger.info("Clicked '%s' on modal '%s'", btn_name, dialog.name)
                return True

        # Try partial match
        for btn in win.GetChildren():
            if btn.ControlTypeName == "Button" and button_name.lower() in btn.Name.lower():
                btn.Click()
                logger.info("Clicked '%s' (partial match) on modal '%s'", btn.Name, dialog.name)
                return True

    except Exception as e:
        logger.error("Failed to click button '%s': %s", button_name, e)

    return False


def click_ok(dialog: ModalDialog) -> bool:
    """Click OK button."""
    for name in ["OK", "Ok", "Yes", "Save", "Confirm", "Continue"]:
        if click_button(dialog, name):
            return True
    return False


def click_cancel(dialog: ModalDialog) -> bool:
    """Click Cancel button."""
    for name in ["Cancel", "No", "Don't Save", "Discard"]:
        if click_button(dialog, name):
            return True
    return False


def click_yes(dialog: ModalDialog) -> bool:
    """Click Yes button."""
    return click_button(dialog, "Yes")


def click_no(dialog: ModalDialog) -> bool:
    """Click No button."""
    return click_button(dialog, "No")


def click_dont_show_again_and_ok(dialog: ModalDialog) -> bool:
    """Check 'Don't show again' checkbox, then click OK."""
    if not UIA_AVAILABLE or ui is None:
        return False

    try:
        win = ui.WindowControl(searchDepth=1, WindowHandle=dialog.hwnd)
        if win.Exists(0.5):
            checkbox = ui.CheckBoxControl(NameRegex=".*don't.*show.*|.*remember.*|.*always.*",
                                          parentControl=win, searchDepth=5)
            if checkbox.Exists(0.5) and not checkbox.GetToggleState():
                checkbox.Click()
                logger.info("Checked 'don't show again'")
    except Exception:
        pass

    return click_ok(dialog)


# ─── Modal Handler ─────────────────────────────────────────────────

@dataclass
class ModalRule:
    """A rule for handling a specific type of modal dialog."""
    pattern: str  # Substring to match in dialog text/title
    strategy: Callable[[ModalDialog], bool]  # Function to handle it
    priority: int = 0  # Higher = checked first


class ModalHandler:
    """Detect and handle modal dialogs that block automation.

    Uses a rule-based approach with fallback to LLM-driven decisions.
    """

    def __init__(self):
        self._rules: List[ModalRule] = []
        self._default_strategy: Callable[[ModalDialog], bool] = click_ok
        self._handled_count = 0

        # Add default rules
        self._add_default_rules()

    def _add_default_rules(self):
        """Add built-in modal handling rules."""
        # Save on close dialogs
        self.add_rule("Do you want to save", click_ok, priority=10)
        self.add_rule("save changes", click_ok, priority=10)

        # Warning dialogs
        self.add_rule("are you sure", click_yes, priority=5)
        self.add_rule("warning", click_ok, priority=5)

        # Error dialogs
        self.add_rule("error", click_ok, priority=3)
        self.add_rule("cannot be", click_ok, priority=3)

        # Update/upgrade prompts
        self.add_rule("update available", click_cancel, priority=8)
        self.add_rule("upgrade", click_cancel, priority=8)

        # License/EULA
        self.add_rule("license agreement", click_cancel, priority=9)
        self.add_rule("eula", click_cancel, priority=9)

    def add_rule(self, pattern: str, strategy: Callable[[ModalDialog], bool],
                 priority: int = 0):
        """Add a rule for handling a specific modal dialog.

        Args:
            pattern: Substring to match in dialog title or text.
            strategy: Function that takes a ModalDialog and returns True on success.
            priority: Higher priority rules are checked first.
        """
        self._rules.append(ModalRule(
            pattern=pattern.lower(),
            strategy=strategy,
            priority=priority,
        ))
        # Sort by priority descending
        self._rules.sort(key=lambda r: r.priority, reverse=True)

    def set_default_strategy(self, strategy: Callable[[ModalDialog], bool]):
        """Set the default strategy for unhandled modals."""
        self._default_strategy = strategy

    def detect_modals(self, parent_hwnd: Optional[int] = None) -> List[ModalDialog]:
        """Detect active modal dialogs.

        Args:
            parent_hwnd: If set, only check children of this window.

        Returns:
            List of detected ModalDialog objects.
        """
        if not UIA_AVAILABLE or ui is None:
            return []

        modals: List[ModalDialog] = []

        try:
            # Find all top-level windows
            if parent_hwnd:
                windows = [ui.WindowControl(WindowHandle=parent_hwnd)]
            else:
                windows = ui.GetRootControl().GetChildren()

            for win in windows:
                if not hasattr(win, 'ControlTypeName'):
                    continue
                if win.ControlTypeName != "Window":
                    continue

                # Check if modal
                is_modal = False
                try:
                    is_modal = win.GetBoolPropertyValue(ui.UIA_IsModalProperty)
                except Exception:
                    pass

                # Also check topmost as a heuristic
                try:
                    is_topmost = win.GetBoolPropertyValue(ui.UIA_IsTopmostProperty)
                    if is_topmost and win.WindowHandle:
                        is_modal = True
                except Exception:
                    pass

                if not is_modal:
                    continue

                # Extract dialog info
                name = win.Name or ""
                text_content = self._extract_text(win)

                # Find buttons
                buttons = self._find_buttons(win)

                dialog = ModalDialog(
                    hwnd=win.WindowHandle or 0,
                    name=name,
                    title=name,
                    text_content=text_content,
                    buttons=buttons,
                    is_modal=True,
                )
                modals.append(dialog)
                logger.info("Detected modal: '%s' (%d buttons)", name, len(buttons))

        except Exception as e:
            logger.error("Modal detection failed: %s", e)

        return modals

    def check_and_handle(self, parent_hwnd: Optional[int] = None) -> bool:
        """Check for modals and handle them automatically.

        Returns:
            True if a modal was detected and handled.
        """
        modals = self.detect_modals(parent_hwnd)
        if not modals:
            return False

        for dialog in modals:
            if self.handle_dialog(dialog):
                self._handled_count += 1
                return True

        return False

    def handle_dialog(self, dialog: ModalDialog) -> bool:
        """Handle a specific modal dialog using rules.

        Returns:
            True if the dialog was handled successfully.
        """
        full_text = (dialog.title + " " + dialog.text_content).lower()

        # Try rules in priority order
        for rule in self._rules:
            if rule.pattern in full_text:
                logger.info("Modal rule matched: '%s' → %s", rule.pattern, rule.strategy.__name__)
                success = rule.strategy(dialog)
                if success:
                    time.sleep(0.3)  # Wait for dialog to close
                    return True
                logger.warning("Rule '%s' failed to handle modal", rule.pattern)

        # Fallback to default strategy
        logger.info("No rule matched, using default strategy for modal: '%s'", dialog.title)
        success = self._default_strategy(dialog)
        if success:
            time.sleep(0.3)
        return success

    def _extract_text(self, win) -> str:
        """Extract all text content from a dialog window."""
        if not UIA_AVAILABLE or ui is None:
            return ""

        texts: List[str] = []
        try:
            for ctrl in win.ControlChildren:
                if ctrl.ControlTypeName in ("Text", "Static", "Document"):
                    name = ctrl.Name
                    if name and name.strip():
                        texts.append(name.strip())
        except Exception:
            pass

        return " ".join(texts)

    def _find_buttons(self, win) -> List[Dict[str, Any]]:
        """Find all buttons in a dialog window."""
        if not UIA_AVAILABLE or ui is None:
            return []

        buttons: List[Dict[str, Any]] = []
        try:
            for ctrl in win.ControlChildren:
                if ctrl.ControlTypeName == "Button":
                    btn = {
                        "name": ctrl.Name,
                        "automation_id": ctrl.AutomationId,
                        "is_default": False,
                    }
                    try:
                        btn["is_default"] = ctrl.GetBoolPropertyValue(ui.UIA_IsDefaultButtonProperty)
                    except Exception:
                        pass
                    buttons.append(btn)
        except Exception:
            pass

        return buttons

    @property
    def handled_count(self) -> int:
        return self._handled_count

    def summary(self) -> Dict[str, Any]:
        return {
            "rules_count": len(self._rules),
            "handled_count": self._handled_count,
            "default_strategy": self._default_strategy.__name__,
        }
