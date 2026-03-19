"""Fixed registry of business insights - core logic only."""

from dataclasses import dataclass
from typing import List, Dict, Callable, Optional, Any
from ..candidate_generation.pattern_types import PatternType


@dataclass
class BusinessInsightDefinition:
    """Definition of a business insight in the registry."""
    id: str
    category: str  # English category name, e.g. "budget_efficiency"
    tier: int  # 1 = single-signal, 2 = composite
    trigger_pattern_type: Optional[PatternType] = None  # None for Tier 2 composite insights
    trigger_metrics: Optional[List[str]] = None  # None for Tier 2 composite insights
    trigger_condition: Optional[Callable] = None  # Optional function to check additional conditions
    priority_metric: str = "composite_score"  # How to rank candidates when multiple match


@dataclass
class BusinessInsight:
    """Business insight output object - pure structured data."""
    id: str
    category: str  # English category name, e.g. "budget_efficiency"
    segment_id: str
    dimension: str
    metric: str
    observed_value: float
    baseline_value: float
    absolute_delta: float
    relative_delta_pct: float
    importance_score: float
    confidence: float
    source_pattern_type: str
    supporting_candidates: List[str] = None  # List of ScoredPatternCandidate IDs or references
    
    def __post_init__(self):
        """Initialize supporting_candidates as empty list if None."""
        if self.supporting_candidates is None:
            self.supporting_candidates = []


# Registry of business insights (23 total - FROZEN)
# Approved insight set - do not add or remove without explicit approval
REGISTRY: List[BusinessInsightDefinition] = [
    # Category: budget_efficiency
    BusinessInsightDefinition(
        id="underfunded_winner",
        category="budget_efficiency",
        tier=2
    ),
    BusinessInsightDefinition(
        id="overfunded_underperformer",
        category="budget_efficiency",
        tier=2
    ),
    BusinessInsightDefinition(
        id="spend_revenue_imbalance",
        category="budget_efficiency",
        tier=1,
        trigger_pattern_type=PatternType.METRIC_IMBALANCE,
        trigger_metrics=["spend/revenue_ratio"]
    ),
    
    # Category: performance_gaps
    BusinessInsightDefinition(
        id="segment_performance_gap",
        category="performance_gaps",
        tier=1,
        trigger_pattern_type=PatternType.SEGMENT_GAP,
        trigger_metrics=["roas", "revenue", "conversions"]
    ),
    BusinessInsightDefinition(
        id="segment_above_baseline",
        category="performance_gaps",
        tier=1,
        trigger_pattern_type=PatternType.SEGMENT_ABOVE_BASELINE,
        trigger_metrics=["roas", "revenue", "conversions"],
        trigger_condition=lambda candidate: (
            candidate.baseline_value is not None and
            candidate.observed_value > candidate.baseline_value and
            abs(candidate.baseline_value) > 1e-9 and
            ((candidate.observed_value - candidate.baseline_value) / abs(candidate.baseline_value)) >= 0.20
        )
    ),
    BusinessInsightDefinition(
        id="segment_below_baseline",
        category="performance_gaps",
        tier=1,
        trigger_pattern_type=PatternType.SEGMENT_BELOW_BASELINE,
        trigger_metrics=["roas", "revenue", "conversions"],
        trigger_condition=lambda candidate: (
            candidate.baseline_value is not None and
            candidate.observed_value < candidate.baseline_value and
            abs(candidate.baseline_value) > 1e-9 and
            ((candidate.observed_value - candidate.baseline_value) / abs(candidate.baseline_value)) <= -0.20
        )
    ),
    BusinessInsightDefinition(
        id="hidden_high_performer",
        category="performance_gaps",
        tier=2
    ),
    BusinessInsightDefinition(
        id="conversion_efficiency_gap",
        category="performance_gaps",
        tier=2
    ),
    
    # Category: temporal_dynamics
    BusinessInsightDefinition(
        id="performance_volatility",
        category="temporal_dynamics",
        tier=2
    ),
    BusinessInsightDefinition(
        id="sustained_decline",
        category="temporal_dynamics",
        tier=2
    ),
    BusinessInsightDefinition(
        id="momentum_shift",
        category="temporal_dynamics",
        tier=2
    ),
    
    # Category: concentration_risk
    BusinessInsightDefinition(
        id="revenue_concentration_risk",
        category="concentration_risk",
        tier=2
    ),
    BusinessInsightDefinition(
        id="platform_dependency_risk",
        category="concentration_risk",
        tier=2
    ),
    
    # Category: value_quality_shift
    BusinessInsightDefinition(
        id="high_volume_low_value",
        category="value_quality_shift",
        tier=2
    ),
    
    # Category: funnel_breakdown
    BusinessInsightDefinition(
        id="leakage_detection",
        category="funnel_breakdown",
        tier=2
    ),
    
    # Category: budget_dynamics
    BusinessInsightDefinition(
        id="budget_saturation_signal",
        category="budget_dynamics",
        tier=2
    ),
    
    # Category: creative_health
    BusinessInsightDefinition(
        id="creative_fatigue_signal",
        category="creative_health",
        tier=2
    ),
    
    # Category: temporal_allocation_mismatch
    BusinessInsightDefinition(
        id="platform_time_mismatch",
        category="temporal_allocation_mismatch",
        tier=2
    ),
    
    # Category: temporal_shift
    BusinessInsightDefinition(
        id="weekend_weekday_roi_shift",
        category="temporal_shift",
        tier=2
    ),
    
    # Category: funnel_structure
    BusinessInsightDefinition(
        id="platform_funnel_role",
        category="funnel_structure",
        tier=2
    ),
    
    # Category: audience_fit
    BusinessInsightDefinition(
        id="audience_platform_fit",
        category="audience_fit",
        tier=2
    ),
    
    # Category: trend_structure
    BusinessInsightDefinition(
        id="month_over_month_narrative",
        category="trend_structure",
        tier=2
    ),
    
    # Category: risk_monitoring
    BusinessInsightDefinition(
        id="risk_flags",
        category="risk_monitoring",
        tier=2
    )
]

# Guard: Validate registry contains exactly the approved 23 insights
_APPROVED_INSIGHT_IDS = {
    "segment_performance_gap",
    "segment_above_baseline",
    "segment_below_baseline",
    "spend_revenue_imbalance",
    "conversion_efficiency_gap",
    "performance_volatility",
    "sustained_decline",
    "momentum_shift",
    "hidden_high_performer",
    "underfunded_winner",
    "overfunded_underperformer",
    "high_volume_low_value",
    "leakage_detection",
    "creative_fatigue_signal",
    "budget_saturation_signal",
    "platform_time_mismatch",
    "weekend_weekday_roi_shift",
    "audience_platform_fit",
    "platform_funnel_role",
    "revenue_concentration_risk",
    "platform_dependency_risk",
    "risk_flags",
    "month_over_month_narrative"
}


def _validate_registry():
    """Validate that registry contains exactly the approved 23 insights."""
    registered_ids = {d.id for d in REGISTRY}
    
    if len(REGISTRY) != 23:
        raise ValueError(
            f"Registry validation failed: Expected exactly 23 insights, found {len(REGISTRY)}. "
            f"Registered IDs: {sorted(registered_ids)}"
        )
    
    missing_ids = _APPROVED_INSIGHT_IDS - registered_ids
    if missing_ids:
        raise ValueError(
            f"Registry validation failed: Missing approved insights: {sorted(missing_ids)}. "
            f"Registered IDs: {sorted(registered_ids)}"
        )
    
    unexpected_ids = registered_ids - _APPROVED_INSIGHT_IDS
    if unexpected_ids:
        raise ValueError(
            f"Registry validation failed: Unexpected insights found: {sorted(unexpected_ids)}. "
            f"Approved IDs: {sorted(_APPROVED_INSIGHT_IDS)}"
        )


# Validate registry on import
_validate_registry()
