"""
Hermes Eats World — Perception Tier Classifier
===============================================
Classify a window into a perception tier based on its UIA tree characteristics.
Returns a TierClassification with tier, label, confidence, and supporting evidence.
"""

import logging
from typing import Any, Dict

from ..schema.models import TierClassification, TreeSummary

logger = logging.getLogger(__name__)

# Thresholds — to be calibrated against real apps in P1-5.
# Current values are the spike's empirically tested defaults.
TIER_THRESHOLDS = {
    "min_elements_t1": 50,       # >= this → T1 candidate
    "min_patterns_t1": 4,       # >= unique pattern types → T1 candidate
    "min_elements_t1t2": 10,    # >= this → T1/T2 hybrid
}


def classify_tier(summary: TreeSummary) -> TierClassification:
    """Classify a tree into a perception tier.
    
    T1 (Rich):   Large element count, high pattern diversity — full UIA automation.
    T1/T2 (Partial): Moderate tree, some automation possible, vision helps.
    T2 (Sparse):   Few elements/patterns — vision fallback is primary.
    T3 (Opaque):   Essentially nothing — pure vision or not targetable.
    
    Returns a structured dict with tier, label, confidence (0-1), and evidence.
    """
    elem_count = summary.total_elements
    unique_types = len(summary.control_types)
    unique_patterns = len(summary.control_patterns)
    max_depth = summary.max_depth

    evidence = {
        "element_count": elem_count,
        "unique_control_types": unique_types,
        "unique_pattern_types": unique_patterns,
        "max_depth": max_depth,
    }

    # T1: Rich tree
    if elem_count >= TIER_THRESHOLDS["min_elements_t1"] and unique_patterns >= TIER_THRESHOLDS["min_patterns_t1"]:
        confidence = _clamp(
            0.5
            + 0.2 * min(elem_count / 200, 1.0)
            + 0.3 * min(unique_patterns / 8, 1.0),
            0.0,
            1.0,
        )
        return TierClassification(
            tier="T1",
            label="Rich accessibility tree",
            confidence=round(confidence, 2),
            evidence=evidence,
        )

    # T1/T2: Partial tree
    if elem_count >= TIER_THRESHOLDS["min_elements_t1t2"] and unique_patterns >= 2:
        confidence = _clamp(
            0.3
            + 0.2 * min(elem_count / 100, 1.0)
            + 0.2 * min(unique_patterns / 4, 1.0),
            0.0,
            1.0,
        )
        return TierClassification(
            tier="T1/T2",
            label="Partial accessibility tree",
            confidence=round(confidence, 2),
            evidence=evidence,
        )

    # T2: Sparse tree
    if elem_count >= 2 and unique_patterns >= 1:
        confidence = _clamp(
            0.2
            + 0.1 * min(elem_count / 20, 1.0),
            0.0,
            1.0,
        )
        return TierClassification(
            tier="T2",
            label="Sparse tree — vision fallback",
            confidence=round(confidence, 2),
            evidence=evidence,
        )

    # T3: Essentially nothing
    return TierClassification(
        tier="T3",
        label="Opaque — vision only",
        confidence=round(min(elem_count / 10, 0.3), 2),
        evidence=evidence,
    )


def _clamp(value: float, lo: float, hi: float) -> float:
    """Clamp a float to [lo, hi]."""
    return max(lo, min(hi, value))
