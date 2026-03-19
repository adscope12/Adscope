"""Effect size calculations."""

import numpy as np
import pandas as pd
from typing import Optional
from ..models.candidate import InsightCandidate
from ..candidate_generation.pattern_types import PatternType


def calculate_effect_size(candidate: InsightCandidate) -> float:
    """
    Calculate statistical effect size (0-1 scale).
    
    Handles missing values gracefully.
    """
    pattern_type = candidate.pattern_type
    observed = candidate.observed_value
    baseline = candidate.baseline_value
    
    if pd.isna(observed) or baseline is None or pd.isna(baseline):
        return 0.0
    
    if baseline == 0:
        # Avoid division by zero
        return min(1.0, abs(observed) / (abs(observed) + 1))
    
    if pattern_type in [PatternType.SEGMENT_ABOVE_BASELINE, PatternType.SEGMENT_BELOW_BASELINE]:
        # Relative difference for baseline comparisons
        relative_diff = abs(observed - baseline) / abs(baseline)
        # Normalize to 0-1 (cap at 10x difference = 1.0)
        return min(1.0, relative_diff / 10.0)
    
    elif pattern_type == PatternType.SEGMENT_GAP:
        # Relative gap between segments
        if candidate.comparison_segment:
            comparison_mean = candidate.comparison_segment.get('metrics', {}).get(candidate.metric_name, baseline)
            if comparison_mean == 0:
                return min(1.0, abs(observed) / (abs(observed) + 1))
            relative_gap = abs(observed - comparison_mean) / abs(comparison_mean)
            return min(1.0, relative_gap / 10.0)
        return 0.0
    
    elif pattern_type == PatternType.TEMPORAL_CHANGE:
        # Percent change for temporal
        if baseline == 0:
            return min(1.0, abs(observed) / (abs(observed) + 1))
        pct_change = abs(observed - baseline) / abs(baseline)
        return min(1.0, pct_change / 2.0)  # Cap at 200% change
    
    elif pattern_type == PatternType.METRIC_IMBALANCE:
        # Ratio deviation for metric imbalance
        if baseline == 0:
            return min(1.0, abs(observed) / (abs(observed) + 1))
        ratio_diff = abs(observed - baseline) / abs(baseline)
        return min(1.0, ratio_diff / 5.0)  # Cap at 5x ratio difference
    
    return 0.0
