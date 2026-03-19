"""Composite scoring using hybrid multiplicative-additive model."""

from typing import Optional
from ..models.candidate import InsightCandidate
from ..models.insight import ScoredPatternCandidate
from .effect_size import calculate_effect_size
from .business_impact import calculate_business_impact
from .statistical_support import calculate_statistical_support


# Pre-ranking filter thresholds
MIN_EFFECT_SIZE = 0.02
MIN_ABSOLUTE_DELTA = {
    "revenue": 100,
    "spend": 100,
    "ctr": 0.001,
    "cvr": 0.001,
    "roas": 0.1,
    "cpc": 0.1,
    "cpa": 0.1,
    "aov": 0.1,
    "conversions": 1.0  # Add conversions threshold
}

EPSILON = 0.001  # Minimal meaningful signal floor


def score_candidate(candidate: InsightCandidate) -> Optional[ScoredPatternCandidate]:
    """
    Score a candidate using hybrid multiplicative-additive model.
    
    Applies hard pre-ranking filters:
    1. effect_size must be >= MIN_EFFECT_SIZE (0.02)
    2. absolute_delta must be >= MIN_ABSOLUTE_DELTA for the metric
    
    Formula:
    base_score = (effect_size * 0.6) + (business_impact * 0.4)
    composite_score = base_score * statistical_support
    
    Patterns below epsilon are effectively ranked at zero.
    Returns None if candidate fails pre-ranking filters.
    """
    # Calculate effect_size first (needed for filter)
    effect_size = calculate_effect_size(candidate)
    
    # Pre-ranking filter 1: effect_size threshold
    if effect_size < MIN_EFFECT_SIZE:
        return None
    
    # Pre-ranking filter 2: absolute_delta threshold
    if candidate.baseline_value is not None:
        absolute_delta = abs(candidate.observed_value - candidate.baseline_value)
        metric_name = candidate.metric_name.lower()
        
        # Get threshold for this metric (default to 0 if not specified)
        min_delta = MIN_ABSOLUTE_DELTA.get(metric_name, 0)
        
        if absolute_delta < min_delta:
            return None
    
    # Both filters passed - continue with full scoring
    business_impact = calculate_business_impact(candidate)
    statistical_support = calculate_statistical_support(candidate)
    
    # Base score (additive)
    base_score = (effect_size * 0.6) + (business_impact * 0.4)
    
    # Composite score (multiplicative)
    composite_score = base_score * statistical_support
    
    # Apply epsilon floor (patterns below epsilon effectively rank at zero)
    if composite_score < EPSILON:
        composite_score = 0.0
    
    return ScoredPatternCandidate(
        candidate=candidate,
        effect_size=effect_size,
        business_impact=business_impact,
        statistical_support=statistical_support,
        composite_score=composite_score
    )
