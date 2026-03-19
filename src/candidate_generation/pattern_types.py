"""Pattern type definitions."""

from enum import Enum


class PatternType(Enum):
    """Statistical pattern types."""
    SEGMENT_ABOVE_BASELINE = "SEGMENT_ABOVE_BASELINE"
    SEGMENT_BELOW_BASELINE = "SEGMENT_BELOW_BASELINE"
    SEGMENT_GAP = "SEGMENT_GAP"
    TEMPORAL_CHANGE = "TEMPORAL_CHANGE"
    METRIC_IMBALANCE = "METRIC_IMBALANCE"
