"""
Insight Deduplication Layer - Deterministic deduplication of similar insights.

This module removes duplicate insights that describe the same pattern,
keeping only the strongest candidate (highest composite_score).

Deduplication happens AFTER candidate scoring and BEFORE insight mapping.
"""

from typing import List, Dict, Optional
from ..models.insight import ScoredPatternCandidate
from ..candidate_generation.pattern_types import PatternType


def build_pattern_signature(scored_candidate: ScoredPatternCandidate) -> str:
    """
    Build a deterministic pattern signature for deduplication.
    
    Signature format:
    dimension|segment|insight_category|metric_family|direction
    
    Examples:
    - device|mobile|conversion_efficiency|cvr|negative
    - platform|facebook|cost_efficiency|cpc|negative
    - campaign|campaign_a|roas_strength|roas|positive
    
    Args:
        scored_candidate: ScoredPatternCandidate to build signature for
        
    Returns:
        Pattern signature string
    """
    candidate = scored_candidate.candidate
    
    # Extract dimension (first dimension in dimensions dict, or "unknown")
    dimension = "unknown"
    if candidate.dimensions:
        dimension = list(candidate.dimensions.keys())[0]
    
    # Extract segment value (from primary_segment)
    segment = "unknown"
    if candidate.primary_segment:
        segment_value = candidate.primary_segment.get('value')
        if segment_value is not None:
            # Normalize segment value (convert to string, lowercase for consistency)
            segment = str(segment_value).lower().strip()
    
    # Determine insight category based on metric and pattern type
    insight_category = _determine_insight_category(candidate.metric_name, candidate.pattern_type, candidate.pattern_id)
    
    # Determine metric family
    metric_family = _determine_metric_family(candidate.metric_name)
    
    # Determine direction (positive/negative)
    direction = _determine_direction(candidate.pattern_type, candidate.observed_value, candidate.baseline_value)
    
    # Build signature (use empty string for missing fields, but keep order stable)
    signature_parts = [
        dimension or "",
        segment or "",
        insight_category or "",
        metric_family or "",
        direction or ""
    ]
    
    return "|".join(signature_parts)


def _determine_insight_category(metric_name: str, pattern_type: PatternType, pattern_id: str = "") -> str:
    """
    Determine insight category from metric and pattern type.
    
    Categories:
    - conversion_efficiency: CVR, conversions
    - cost_efficiency: CPC, CPA
    - roas_strength: ROAS, revenue
    - engagement: CTR
    - budget_allocation: spend
    - temporal_trend: temporal patterns
    """
    metric_lower = metric_name.lower()
    
    # Temporal patterns (check pattern_id for weekend/weekday, gradual decline, recovery, spike/drop)
    if (pattern_type == PatternType.TEMPORAL_CHANGE or
        pattern_id.startswith(('WEEKEND_WEEKDAY', 'GRADUAL_DECLINE', 'RECOVERY', 'SPIKE_DROP'))):
        return "temporal_trend"
    
    # Conversion-related
    if metric_lower in ['cvr', 'conversions']:
        return "conversion_efficiency"
    
    # Cost-related
    if metric_lower in ['cpc', 'cpa']:
        return "cost_efficiency"
    
    # Revenue/ROAS-related
    if metric_lower in ['roas', 'revenue', 'aov']:
        return "roas_strength"
    
    # Engagement
    if metric_lower == 'ctr':
        return "engagement"
    
    # Budget
    if metric_lower == 'spend':
        return "budget_allocation"
    
    # Default
    return "general"


def _determine_metric_family(metric_name: str) -> str:
    """
    Group metrics into families for deduplication.
    
    Families:
    - conversion: CVR, conversions
    - cost: CPC, CPA
    - revenue: ROAS, revenue, AOV
    - engagement: CTR
    - spend: spend
    - other: everything else
    """
    metric_lower = metric_name.lower()
    
    if metric_lower in ['cvr', 'conversions']:
        return "conversion"
    
    if metric_lower in ['cpc', 'cpa']:
        return "cost"
    
    if metric_lower in ['roas', 'revenue', 'aov']:
        return "revenue"
    
    if metric_lower == 'ctr':
        return "engagement"
    
    if metric_lower == 'spend':
        return "spend"
    
    return "other"


def _determine_direction(
    pattern_type: PatternType,
    observed_value: float,
    baseline_value: Optional[float]
) -> str:
    """
    Determine direction (positive/negative) based on pattern type and values.
    
    Returns:
        "positive" or "negative"
    """
    if baseline_value is None:
        return "unknown"
    
    if pattern_type == PatternType.SEGMENT_ABOVE_BASELINE:
        return "positive"
    
    if pattern_type == PatternType.SEGMENT_BELOW_BASELINE:
        return "negative"
    
    if pattern_type == PatternType.SEGMENT_GAP:
        # For gap, direction is relative to comparison segment
        # If observed > baseline, it's positive (winner)
        if observed_value > baseline_value:
            return "positive"
        else:
            return "negative"
    
    if pattern_type == PatternType.TEMPORAL_CHANGE:
        # For temporal change, positive = improvement, negative = decline
        if observed_value > baseline_value:
            return "positive"
        else:
            return "negative"
    
    if pattern_type == PatternType.METRIC_IMBALANCE:
        # For metric imbalance, direction depends on metric type
        # This is a simplified heuristic - could be enhanced
        return "negative"  # Imbalance is typically negative
    
    return "unknown"


def deduplicate_insights(
    insight_candidates: List[ScoredPatternCandidate]
) -> List[ScoredPatternCandidate]:
    """
    Deduplicate insight candidates by pattern signature.
    
    Logic:
    1. Group candidates by pattern_signature
    2. Within each group, keep only the candidate with highest composite_score
    3. Return deduplicated list, sorted by composite_score descending
    
    Args:
        insight_candidates: List of scored pattern candidates
        
    Returns:
        Deduplicated list of candidates, sorted by composite_score descending
    """
    if not insight_candidates:
        return []
    
    # Build signatures for all candidates
    signature_groups: Dict[str, List[ScoredPatternCandidate]] = {}
    
    for candidate in insight_candidates:
        signature = build_pattern_signature(candidate)
        
        if signature not in signature_groups:
            signature_groups[signature] = []
        
        signature_groups[signature].append(candidate)
    
    # For each signature group, keep only the highest-scoring candidate
    deduplicated = []
    
    for signature, candidates in signature_groups.items():
        if len(candidates) == 1:
            # No duplicates, keep as-is
            deduplicated.append(candidates[0])
        else:
            # Multiple candidates with same signature - keep highest composite_score
            best_candidate = max(candidates, key=lambda c: c.composite_score)
            deduplicated.append(best_candidate)
    
    # Sort by composite_score descending to preserve ranking
    deduplicated.sort(key=lambda c: c.composite_score, reverse=True)
    
    return deduplicated
