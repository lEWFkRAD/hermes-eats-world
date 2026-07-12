from sidecar.perception.classifier import classify_tier
from sidecar.schema.models import TreeSummary


def test_rich_tree_is_t1():
    summary = TreeSummary(
        total_elements=100,
        max_depth=4,
        control_types={"ButtonControl": 100},
        control_patterns={"Invoke": 40, "Value": 20, "Toggle": 10, "Scroll": 1},
    )

    result = classify_tier(summary)

    assert result.tier == "T1"
    assert result.evidence["element_count"] == 100


def test_empty_tree_is_t3():
    result = classify_tier(TreeSummary())

    assert result.tier == "T3"
