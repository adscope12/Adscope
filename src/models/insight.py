"""Scored and ranked insight data structures."""

from dataclasses import dataclass
from typing import Optional, Any
from .candidate import InsightCandidate

# Import PatternType
try:
    from ..candidate_generation.pattern_types import PatternType
except ImportError:
    PatternType = None


@dataclass
class ScoredPatternCandidate:
    """Scored pattern candidate - Phase 1 output."""
    
    candidate: InsightCandidate
    effect_size: float
    business_impact: float
    statistical_support: float
    composite_score: float
    final_score: float = 0.0  # Pattern-type normalized ranking score


@dataclass
class RankedInsight:
    """Final ranked insight output - human-readable summary derived from pattern."""
    
    pattern_type: Any  # PatternType from candidate_generation.pattern_types
    involved_dimension: str  # platform/campaign/device/time
    metric: str
    observed_value: float
    baseline_value: Optional[float]
    effect_size: float
    impact_weight: float
    statistical_support: float
    composite_score: float
    what_happened: str  # Human-readable: what happened
    evidence: str  # Evidence supporting the insight
