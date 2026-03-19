"""
Narrative Tags - Allowed narrative language for grounded LLM phrasing.

This module defines allowed narrative tags per pattern type to constrain
LLM output to only use approved business language.
"""

from typing import List, Dict
from ..candidate_generation.pattern_types import PatternType


# Narrative tags by pattern type and direction
NARRATIVE_TAGS: Dict[str, List[str]] = {
    "winning_segment": [
        "outperforming segment",
        "stronger efficiency",
        "better return on spend",
        "budget reallocation opportunity",
        "high-performing segment"
    ],
    "underperforming_segment": [
        "efficiency drag",
        "weaker conversion economics",
        "underperforming segment",
        "optimization needed",
        "performance gap"
    ],
    "temporal_spike": [
        "sudden disruption",
        "unusual movement",
        "requires investigation",
        "short-term volatility",
        "anomaly detected"
    ],
    "temporal_drop": [
        "performance decline",
        "weakening trend",
        "requires attention",
        "deteriorating efficiency"
    ],
    "gradual_decline": [
        "weakening over time",
        "deteriorating efficiency",
        "trend worth addressing early",
        "sustained decline"
    ],
    "recovery_pattern": [
        "signs of recovery",
        "improving efficiency",
        "regained momentum",
        "positive trend"
    ],
    "weekend_gap": [
        "day-of-week performance gap",
        "weaker weekend efficiency",
        "scheduling opportunity",
        "weekend performance difference"
    ],
    "performance_gap": [
        "significant performance difference",
        "optimization opportunity",
        "clear performance gap",
        "segment comparison"
    ],
    "budget_imbalance": [
        "budget allocation imbalance",
        "spend efficiency gap",
        "allocation review needed",
        "budget optimization opportunity"
    ]
}


def get_narrative_tags_for_pattern(
    pattern_type: PatternType,
    direction: str,
    pattern_id: str = ""
) -> List[str]:
    """
    Get allowed narrative tags for a specific pattern.
    
    Args:
        pattern_type: PatternType enum
        direction: "positive" or "negative"
        pattern_id: Optional pattern ID for temporal pattern detection
        
    Returns:
        List of allowed narrative tags
    """
    tags = []
    
    # Detect temporal patterns by pattern_id
    is_temporal = (
        pattern_type == PatternType.TEMPORAL_CHANGE or
        pattern_id.startswith(('WEEKEND_WEEKDAY', 'GRADUAL_DECLINE', 'RECOVERY', 'SPIKE_DROP'))
    )
    
    if is_temporal:
        if pattern_id.startswith('WEEKEND_WEEKDAY'):
            tags.extend(NARRATIVE_TAGS.get("weekend_gap", []))
        elif pattern_id.startswith('GRADUAL_DECLINE'):
            tags.extend(NARRATIVE_TAGS.get("gradual_decline", []))
        elif pattern_id.startswith('RECOVERY'):
            tags.extend(NARRATIVE_TAGS.get("recovery_pattern", []))
        elif pattern_id.startswith('SPIKE_DROP'):
            if direction == "positive":
                tags.extend(NARRATIVE_TAGS.get("temporal_spike", []))
            else:
                tags.extend(NARRATIVE_TAGS.get("temporal_drop", []))
        else:
            # Generic temporal change
            if direction == "positive":
                tags.extend(NARRATIVE_TAGS.get("recovery_pattern", []))
            else:
                tags.extend(NARRATIVE_TAGS.get("gradual_decline", []))
    
    elif pattern_type == PatternType.SEGMENT_ABOVE_BASELINE:
        if direction == "positive":
            tags.extend(NARRATIVE_TAGS.get("winning_segment", []))
    
    elif pattern_type == PatternType.SEGMENT_BELOW_BASELINE:
        if direction == "negative":
            tags.extend(NARRATIVE_TAGS.get("underperforming_segment", []))
    
    elif pattern_type == PatternType.SEGMENT_GAP:
        tags.extend(NARRATIVE_TAGS.get("performance_gap", []))
    
    elif pattern_type == PatternType.METRIC_IMBALANCE:
        tags.extend(NARRATIVE_TAGS.get("budget_imbalance", []))
    
    # Always add some generic tags if none found
    if not tags:
        tags.extend(["performance pattern", "optimization opportunity"])
    
    return tags
