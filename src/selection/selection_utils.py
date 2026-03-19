"""Shared utility functions for selection layer."""

from ..candidate_generation.pattern_types import PatternType


def extract_segment_id(candidate) -> str:
    """
    Extract segment_id (or group) from candidate.
    
    Args:
        candidate: InsightCandidate object
        
    Returns:
        Segment identifier string
    """
    # For SEGMENT_GAP, combine both segments
    if candidate.pattern_type == PatternType.SEGMENT_GAP and candidate.comparison_segment:
        primary_val = candidate.primary_segment.get('value', 'unknown')
        comparison_val = candidate.comparison_segment.get('value', 'unknown')
        return f"{primary_val}_vs_{comparison_val}"
    
    # For temporal patterns, use time period
    if candidate.time_period:
        start = candidate.time_period.get('start', 'unknown')
        end = candidate.time_period.get('end', 'unknown')
        return f"{start}_to_{end}"
    
    # For other patterns, use primary segment value
    if candidate.primary_segment:
        segment_value = candidate.primary_segment.get('value')
        if segment_value is not None:
            return str(segment_value)
    
    # Fallback to dimensions
    if candidate.dimensions:
        return str(list(candidate.dimensions.values())[0])
    
    return "unknown"
