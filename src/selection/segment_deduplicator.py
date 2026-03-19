"""Final Insight selection: ensure max 1 Insight per segment_id."""

from typing import List
from ..models.insight import ScoredPatternCandidate
from .selection_utils import extract_segment_id


def deduplicate_by_segment_id(
    scored_patterns: List[ScoredPatternCandidate]
) -> List[ScoredPatternCandidate]:
    """
    Ensure max 1 Insight per segment_id in final selection.
    
    If multiple patterns share the same segment_id:
    - Keep the one with higher composite_score
    - Skip the lower one
    - Maintain order (first occurrence wins if scores are equal)
    
    Args:
        scored_patterns: List of scored patterns (already ranked and diversity-selected)
        
    Returns:
        List of patterns with max 1 per segment_id, sorted by composite_score (descending)
    """
    if not scored_patterns:
        return scored_patterns
    
    # Group by segment_id and keep the one with highest composite_score
    best_by_segment = {}  # segment_id -> ScoredPatternCandidate
    
    for sp in scored_patterns:
        segment_id = extract_segment_id(sp.candidate)
        
        if segment_id not in best_by_segment:
            # First occurrence of this segment_id
            best_by_segment[segment_id] = sp
        else:
            # Keep the one with higher composite_score
            existing_score = best_by_segment[segment_id].composite_score
            current_score = sp.composite_score
            
            if current_score > existing_score:
                best_by_segment[segment_id] = sp
            # else: keep existing (skip current)
    
    # Convert to list and sort by composite_score (descending) to maintain ranking
    result = list(best_by_segment.values())
    result.sort(key=lambda x: x.composite_score, reverse=True)
    
    return result
