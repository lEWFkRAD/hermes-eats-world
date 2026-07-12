import time

import pytest

from sidecar.perception.tree_walker import element_to_dict, make_element_id, summarize_tree
from sidecar.schema.models import Element


def element(element_id, control_type, depth, patterns=None, children=None):
    return Element(
        id=element_id,
        control_type=control_type,
        localized_type=control_type,
        depth=depth,
        patterns=patterns or {},
        children=children or [],
    )


def test_summarize_tree_counts_elements_depth_types_and_patterns():
    root = element(
        "root",
        "WindowControl",
        0,
        {"Window": {"supported": True}},
        [
            element("save", "ButtonControl", 1, {"Invoke": {"supported": True}}),
            element("name", "EditControl", 1, {"Value": {"supported": True}}),
        ],
    )

    result = summarize_tree(root)

    assert result.total_elements == 3
    assert result.max_depth == 1
    assert result.control_types == {
        "ButtonControl": 1,
        "EditControl": 1,
        "WindowControl": 1,
    }
    assert result.control_patterns == {"Value": 1, "Invoke": 1, "Window": 1}


class Rect:
    left = 1
    top = 2

    def width(self):
        return 3

    def height(self):
        return 4


class FakeControl:
    Name = "Save"
    ControlTypeName = "ButtonControl"
    LocalizedControlType = "button"
    AutomationId = "save"
    ClassName = "Button"
    NativeWindowHandle = 1
    IsEnabled = True
    IsOffscreen = False
    BoundingRectangle = Rect()

    def __init__(self, children=None):
        self.children = children or []

    def GetChildren(self):
        return self.children


def test_element_id_does_not_change_when_bounds_change():
    control = FakeControl()
    original = make_element_id(control, "0.1")
    control.BoundingRectangle.left = 999

    assert make_element_id(control, "0.1") == original


def test_element_id_does_not_change_when_visible_name_changes():
    control = FakeControl()
    original = make_element_id(control, "0.1")
    control.Name = "Saved"

    assert make_element_id(control, "0.1") == original


def test_tree_walk_enforces_element_limit():
    root = FakeControl([FakeControl(), FakeControl()])

    with pytest.raises(RuntimeError, match="exceeded 2 elements"):
        element_to_dict(
            root,
            max_depth=2,
            from_patterns={},
            max_elements=2,
            deadline=time.monotonic() + 1,
        )
