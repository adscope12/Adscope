"""Diversity-aware selection for scored pattern candidates."""

from typing import List
from ..models.insight import ScoredPatternCandidate
from .selection_utils import extract_segment_id


def select_diverse_patterns(
    ranked_patterns: List[ScoredPatternCandidate],
    target_n: int,
    max_per_metric: int = 1,
    max_per_dimension: int = 1,
    max_per_segment: int = 2,
    max_per_pattern_type: int = 2
) -> List[ScoredPatternCandidate]:
    """
    Select diverse patterns from ranked list with constraints.
    
    Constraints:
    - max_per_metric: Maximum candidates per metric (default 1)
    - max_per_dimension: Maximum candidates per dimension (default 1)
    - max_per_segment: Maximum candidates per segment_id (default 2, never relaxed)
    - max_per_pattern_type: Maximum candidates per pattern_type (default 2)
    
    If target_n cannot be reached, relax constraints in order:
    1. Allow 2 per dimension (max_per_dimension = 2)
    2. Allow 2 per metric (max_per_metric = 2)
    3. Allow 3 per pattern_type (max_per_pattern_type = 3)
    4. Allow unlimited per pattern_type (max_per_pattern_type = None)
    
    Args:
        ranked_patterns: Patterns sorted by composite_score (descending)
        target_n: Target number of patterns to select
        max_per_metric: Initial max per metric (default 1)
        max_per_dimension: Initial max per dimension (default 1)
        max_per_segment: Max per segment (default 2, never relaxed)
        max_per_pattern_type: Initial max per pattern_type (default 2)
    
    Returns:
        List of selected diverse patterns
    """
    if not ranked_patterns:
        return []
    
    # Try with initial constraints (max 2 per pattern_type)
    selected = _select_with_constraints(
        ranked_patterns, target_n,
        max_per_metric, max_per_dimension, max_per_segment, max_per_pattern_type
    )
    
    # If we didn't reach target_n, relax constraints
    if len(selected) < target_n:
        # Relaxation A: Allow 2 per dimension
        selected = _select_with_constraints(
            ranked_patterns, target_n,
            max_per_metric, max_per_dimension=2, max_per_segment=max_per_segment,
            max_per_pattern_type=max_per_pattern_type
        )
    
    if len(selected) < target_n:
        # Relaxation B: Allow 2 per metric
        selected = _select_with_constraints(
            ranked_patterns, target_n,
            max_per_metric=2, max_per_dimension=2, max_per_segment=max_per_segment,
            max_per_pattern_type=max_per_pattern_type
        )
    
    if len(selected) < target_n:
        # Relaxation C: Allow 3 per pattern_type
        selected = _select_with_constraints(
            ranked_patterns, target_n,
            max_per_metric=2, max_per_dimension=2, max_per_segment=max_per_segment,
            max_per_pattern_type=3
        )
    
    if len(selected) < target_n:
        # Relaxation D: Allow unlimited per pattern_type
        selected = _select_with_constraints(
            ranked_patterns, target_n,
            max_per_metric=2, max_per_dimension=2, max_per_segment=max_per_segment,
            max_per_pattern_type=None  # None means unlimited
        )
    
    return selected


def _select_with_constraints(
    ranked_patterns: List[ScoredPatternCandidate],
    target_n: int,
    max_per_metric: int,
    max_per_dimension: int,
    max_per_segment: int,
    max_per_pattern_type: int = None
) -> List[ScoredPatternCandidate]:
    """
    Select patterns with specific constraint values.
    
    Args:
        max_per_pattern_type: Maximum per pattern_type (None means unlimited)
    """
    selected = []
    metric_counts = {}
    dimension_counts = {}
    segment_counts = {}
    pattern_type_counts = {}
    
    for sp in ranked_patterns:
        if len(selected) >= target_n:
            break
        
        candidate = sp.candidate
        metric = candidate.metric_name
        dimension = list(candidate.dimensions.keys())[0] if candidate.dimensions else "unknown"
        segment_id = extract_segment_id(candidate)
        pattern_type = candidate.pattern_type
        
        # Check constraints
        metric_count = metric_counts.get(metric, 0)
        dimension_count = dimension_counts.get(dimension, 0)
        segment_count = segment_counts.get(segment_id, 0)
        pattern_type_count = pattern_type_counts.get(pattern_type, 0)
        
        # Check pattern_type constraint
        pattern_type_ok = True
        if max_per_pattern_type is not None:
            pattern_type_ok = pattern_type_count < max_per_pattern_type
        
        # Check if we can add this pattern
        can_add = (
            metric_count < max_per_metric and
            dimension_count < max_per_dimension and
            segment_count < max_per_segment and
            pattern_type_ok
        )
        
        if can_add:
            selected.append(sp)
            metric_counts[metric] = metric_count + 1
            dimension_counts[dimension] = dimension_count + 1
            segment_counts[segment_id] = segment_count + 1
            pattern_type_counts[pattern_type] = pattern_type_count + 1
    
    return selected
