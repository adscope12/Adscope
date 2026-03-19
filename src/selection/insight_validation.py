"""
Insight Validation Layer - Deterministic validation and ranking of insights.

This layer runs after pattern detection/scoring and before Strategic LLM wording.
It validates and ranks detected patterns to ensure only the most meaningful
3-4 insights reach the final UI.

Validation dimensions:
- business_impact: How much business value does this insight provide?
- deviation_from_baseline: How significant is the deviation?
- persistence_or_strength: How consistent/strong is the signal?
- actionability: Can the user take meaningful action on this?
- confidence_support: How statistically confident are we?

Validation formula:
validation_score = 
    w1 * business_impact +
    w2 * deviation +
    w3 * persistence +
    w4 * actionability +
    w5 * confidence

Where weights are:
- w1 (business_impact): 0.30
- w2 (deviation): 0.25
- w3 (persistence): 0.20
- w4 (actionability): 0.15
- w5 (confidence): 0.10
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from ..models.insight import ScoredPatternCandidate
from ..candidate_generation.pattern_types import PatternType


# Diversity guardrail helpers (used during top-N selection)
def _pattern_family(scored_pattern: ScoredPatternCandidate) -> str:
    candidate = scored_pattern.candidate
    if (
        candidate.pattern_type == PatternType.TEMPORAL_CHANGE
        or candidate.pattern_id.startswith(("GRADUAL_DECLINE", "RECOVERY", "SPIKE_DROP", "WEEKEND_WEEKDAY"))
        or "weekend" in str(candidate.dimensions).lower()
        or "weekday" in str(candidate.dimensions).lower()
        or candidate.time_period is not None
    ):
        return "temporal"

    dim = "unknown"
    if candidate.dimensions:
        dim = list(candidate.dimensions.keys())[0]
    return str(dim).lower() or "other"


def _metric_family(scored_pattern: ScoredPatternCandidate) -> str:
    metric = (scored_pattern.candidate.metric_name or "").lower()
    if metric in ["cvr", "conversions"]:
        return "conversion"
    if metric in ["roas", "revenue", "aov"]:
        return "revenue"
    if metric in ["cpa", "cpc"]:
        return "cost"
    if metric == "ctr":
        return "engagement"
    return "other"


def _business_value_tier(scored_pattern: ScoredPatternCandidate) -> int:
    """
    Higher is better. Used only as a tie-breaker / when scores are close.
    Prefer efficiency/outcome metrics over raw spend-only metrics.
    """
    metric = (scored_pattern.candidate.metric_name or "").lower()
    if metric in ["roas", "cvr", "cpa", "revenue", "conversions"]:
        return 3
    if metric in ["ctr"]:
        return 2
    if metric in ["spend"]:
        # Spend-only is low value unless it's explicitly a budget imbalance pattern.
        if scored_pattern.candidate.pattern_type == PatternType.METRIC_IMBALANCE:
            return 2
        return 0
    return 1


# Validation weights
WEIGHT_BUSINESS_IMPACT = 0.30
WEIGHT_DEVIATION = 0.25
WEIGHT_PERSISTENCE = 0.20
WEIGHT_ACTIONABILITY = 0.15
WEIGHT_CONFIDENCE = 0.10

# Validation thresholds
MIN_VALIDATION_SCORE = 0.40  # Minimum score to keep an insight
MIN_BUSINESS_IMPACT = 0.15  # Minimum business impact to consider
MIN_DEVIATION = 0.10  # Minimum deviation from baseline (normalized)
MIN_STATISTICAL_SUPPORT = 0.50  # Minimum statistical support

# Relaxed thresholds for temporal patterns
MIN_VALIDATION_SCORE_TEMPORAL = 0.30  # Lower threshold for temporal patterns
MIN_BUSINESS_IMPACT_TEMPORAL = 0.10  # Lower threshold for temporal patterns
MIN_STATISTICAL_SUPPORT_TEMPORAL = 0.35  # Lower threshold for temporal patterns


@dataclass
class ValidatedInsight:
    """Insight with validation metadata."""
    
    scored_pattern: ScoredPatternCandidate
    validation_score: float
    keep: bool
    reasons: List[str] = field(default_factory=list)
    rejection_reason: Optional[str] = None
    
    # Component scores for debugging
    business_impact_score: float = 0.0
    deviation_score: float = 0.0
    persistence_score: float = 0.0
    actionability_score: float = 0.0
    confidence_score: float = 0.0


def validate_insight(scored_pattern: ScoredPatternCandidate) -> ValidatedInsight:
    """
    Validate a single scored pattern candidate.
    
    Args:
        scored_pattern: Scored pattern candidate from the engine
        
    Returns:
        ValidatedInsight with validation score, keep/reject decision, and reasons
    """
    candidate = scored_pattern.candidate
    reasons = []
    rejection_reason = None
    
    # 1. Business Impact Score (0-1)
    # Based on existing business_impact score, normalized
    business_impact_score = min(1.0, max(0.0, scored_pattern.business_impact))
    if business_impact_score >= MIN_BUSINESS_IMPACT:
        reasons.append("meaningful business impact")
    else:
        rejection_reason = f"business impact too low ({business_impact_score:.2f} < {MIN_BUSINESS_IMPACT})"
    
    # 2. Deviation from Baseline Score (0-1)
    # Normalize effect_size to 0-1 scale (effect_size typically 0-1, but can be higher)
    # Use effect_size as proxy for deviation strength
    deviation_score = min(1.0, max(0.0, scored_pattern.effect_size / 0.5))  # Normalize: 0.5 effect_size = 1.0 score
    if deviation_score >= MIN_DEVIATION:
        reasons.append("significant deviation from baseline")
    else:
        if not rejection_reason:
            rejection_reason = f"deviation too weak ({deviation_score:.2f} < {MIN_DEVIATION})"
    
    # 3. Persistence/Strength Score (0-1)
    # Based on statistical support and sample size
    # Higher statistical support + larger sample = more persistent signal
    sample_size = candidate.primary_segment.get('sample_size', 0)
    normalized_sample = min(1.0, sample_size / 100.0)  # Normalize: 100 rows = 1.0
    persistence_score = (scored_pattern.statistical_support * 0.7) + (normalized_sample * 0.3)
    persistence_score = min(1.0, max(0.0, persistence_score))
    if persistence_score >= 0.30:
        reasons.append("strong statistical signal")
    else:
        if not rejection_reason:
            rejection_reason = f"weak statistical signal (persistence: {persistence_score:.2f})"
    
    # 4. Actionability Score (0-1)
    # Higher score if:
    # - Pattern involves actionable dimensions (campaign, platform, device, temporal)
    # - Has clear baseline comparison
    # - Involves primary metrics (revenue, spend, ROAS)
    actionability_score = 0.5  # Base score
    
    # Detect temporal patterns
    is_temporal_pattern = (
        candidate.pattern_type == PatternType.TEMPORAL_CHANGE or
        'weekend' in str(candidate.dimensions).lower() or
        'weekday' in str(candidate.dimensions).lower() or
        candidate.pattern_id.startswith(('GRADUAL_DECLINE', 'RECOVERY', 'SPIKE_DROP', 'WEEKEND_WEEKDAY'))
    )
    
    # Boost for actionable dimensions (including temporal)
    dimensions = candidate.dimensions
    if 'campaign' in dimensions or 'platform' in dimensions or 'device' in dimensions:
        actionability_score += 0.2
    
    # Boost for temporal patterns (time-based insights are actionable)
    if is_temporal_pattern:
        actionability_score += 0.2
    
    # Boost for having baseline comparison
    if candidate.baseline_value is not None:
        actionability_score += 0.2
    
    # Boost for primary metrics
    metric_name = candidate.metric_name.lower()
    if metric_name in ['revenue', 'spend', 'roas', 'cpa', 'ctr', 'cvr', 'conversions']:
        actionability_score += 0.1
    
    actionability_score = min(1.0, max(0.0, actionability_score))
    if actionability_score >= 0.50:
        reasons.append("actionable insight")
    else:
        if not rejection_reason:
            rejection_reason = f"low actionability ({actionability_score:.2f})"
    
    # 5. Confidence/Support Score (0-1)
    # Directly use statistical_support
    confidence_score = min(1.0, max(0.0, scored_pattern.statistical_support))
    if confidence_score >= MIN_STATISTICAL_SUPPORT:
        reasons.append("high statistical confidence")
    else:
        if not rejection_reason:
            rejection_reason = f"low statistical confidence ({confidence_score:.2f} < {MIN_STATISTICAL_SUPPORT})"
    
    # Detect temporal patterns for relaxed thresholds
    is_temporal_pattern = (
        candidate.pattern_type == PatternType.TEMPORAL_CHANGE or
        'weekend' in str(candidate.dimensions).lower() or
        'weekday' in str(candidate.dimensions).lower() or
        candidate.pattern_id.startswith(('GRADUAL_DECLINE', 'RECOVERY', 'SPIKE_DROP', 'WEEKEND_WEEKDAY'))
    )
    
    # Calculate composite validation score
    validation_score = (
        WEIGHT_BUSINESS_IMPACT * business_impact_score +
        WEIGHT_DEVIATION * deviation_score +
        WEIGHT_PERSISTENCE * persistence_score +
        WEIGHT_ACTIONABILITY * actionability_score +
        WEIGHT_CONFIDENCE * confidence_score
    )
    
    # Use relaxed thresholds for temporal patterns
    if is_temporal_pattern:
        min_validation_score = MIN_VALIDATION_SCORE_TEMPORAL
        min_business_impact = MIN_BUSINESS_IMPACT_TEMPORAL
        min_statistical_support = MIN_STATISTICAL_SUPPORT_TEMPORAL
    else:
        min_validation_score = MIN_VALIDATION_SCORE
        min_business_impact = MIN_BUSINESS_IMPACT
        min_statistical_support = MIN_STATISTICAL_SUPPORT
    
    # Determine if we should keep this insight
    keep = (
        validation_score >= min_validation_score and
        business_impact_score >= min_business_impact and
        deviation_score >= MIN_DEVIATION and
        confidence_score >= min_statistical_support
    )
    
    # If rejected, ensure we have a reason
    if not keep and not rejection_reason:
        rejection_reason = f"validation score too low ({validation_score:.2f} < {MIN_VALIDATION_SCORE})"
    
    return ValidatedInsight(
        scored_pattern=scored_pattern,
        validation_score=validation_score,
        keep=keep,
        reasons=reasons if keep else [],
        rejection_reason=rejection_reason if not keep else None,
        business_impact_score=business_impact_score,
        deviation_score=deviation_score,
        persistence_score=persistence_score,
        actionability_score=actionability_score,
        confidence_score=confidence_score,
    )


def validate_and_filter_insights(
    scored_patterns: List[ScoredPatternCandidate],
    top_n: int = 4
) -> Tuple[List[ScoredPatternCandidate], Dict[str, Any]]:
    """
    Validate and filter insights, keeping only the strongest top N.
    
    This function:
    1. Validates each scored pattern
    2. Filters out weak/rejected insights
    3. Ranks remaining insights by validation_score
    4. Returns top N strongest insights
    
    Args:
        scored_patterns: List of scored patterns from two-stage ranking
        top_n: Maximum number of insights to return (default: 4)
        
    Returns:
        Tuple of:
        - List of top N validated insights (ScoredPatternCandidate objects)
        - Debug metadata dict with validation details
    """
    if not scored_patterns:
        return [], {
            "total_input": 0,
            "validated": 0,
            "kept": 0,
            "rejected": 0,
            "validation_details": []
        }
    
    # Validate all patterns
    validated_insights = [validate_insight(sp) for sp in scored_patterns]
    
    # Separate kept and rejected
    kept_insights = [vi for vi in validated_insights if vi.keep]
    rejected_insights = [vi for vi in validated_insights if not vi.keep]
    
    # Sort kept insights by validation_score (descending)
    kept_insights.sort(key=lambda x: x.validation_score, reverse=True)
    
    # Take top N with a diversity guardrail:
    # - Avoid returning near-duplicates when scores are close
    # - Cap temporal insights to 2 when top_n >= 3 to prevent crowd-out (e.g., t22)
    top_validated: List[ValidatedInsight] = []
    family_counts: Dict[str, int] = {}
    fam_metric_counts: Dict[str, int] = {}

    score_close_delta = 0.06  # only enforce diversity when scores are close
    best_score = kept_insights[0].validation_score if kept_insights else 0.0
    strong_entity_exists = any(
        (_pattern_family(vi.scored_pattern) in {"campaign", "platform", "device"})
        and ((best_score - vi.validation_score) <= score_close_delta)
        for vi in kept_insights
    )

    for vi in kept_insights:
        if len(top_validated) >= top_n:
            break

        fam = _pattern_family(vi.scored_pattern)
        met = _metric_family(vi.scored_pattern)
        tier = _business_value_tier(vi.scored_pattern)
        fam_count = family_counts.get(fam, 0)
        fam_met_key = f"{fam}:{met}"
        fam_met_count = fam_metric_counts.get(fam_met_key, 0)

        # Business-value preference when scores are close:
        # deprioritize spend-only insights if we already have (or could have) higher-tier metrics.
        if (best_score - vi.validation_score) <= score_close_delta:
            if tier == 0:
                # only allow spend-only if we are short on options
                # (it may get picked in the fill phase)
                continue

        # Prevent temporal crowd-out of strong entity insights:
        # If a strong campaign/platform/device insight exists, do not allow a 3rd temporal.
        if top_n >= 3 and fam == "temporal" and fam_count >= 2 and strong_entity_exists:
            continue

        # Temporal cap (soft): only when candidate isn't much stronger
        if top_n >= 3 and fam == "temporal" and fam_count >= 2:
            if (best_score - vi.validation_score) <= score_close_delta:
                continue

        # Avoid duplicates of the same family+metric when close
        if fam_met_count >= 1 and (best_score - vi.validation_score) <= score_close_delta:
            continue

        top_validated.append(vi)
        family_counts[fam] = fam_count + 1
        fam_metric_counts[fam_met_key] = fam_met_count + 1

    # If we filtered too aggressively, fill remaining slots by score
    if len(top_validated) < min(top_n, len(kept_insights)):
        for vi in kept_insights:
            if len(top_validated) >= top_n:
                break
            if vi in top_validated:
                continue
            top_validated.append(vi)
    
    # Extract ScoredPatternCandidate objects for return
    top_patterns = [vi.scored_pattern for vi in top_validated]
    
    # Build debug metadata
    debug_metadata = {
        "total_input": len(scored_patterns),
        "validated": len(validated_insights),
        "kept": len(kept_insights),
        "rejected": len(rejected_insights),
        "top_n_selected": len(top_patterns),
        "validation_details": [
            {
                "pattern_id": vi.scored_pattern.candidate.pattern_id,
                "validation_score": round(vi.validation_score, 3),
                "keep": vi.keep,
                "reasons": vi.reasons,
                "rejection_reason": vi.rejection_reason,
                "component_scores": {
                    "business_impact": round(vi.business_impact_score, 3),
                    "deviation": round(vi.deviation_score, 3),
                    "persistence": round(vi.persistence_score, 3),
                    "actionability": round(vi.actionability_score, 3),
                    "confidence": round(vi.confidence_score, 3),
                },
                "original_composite_score": round(vi.scored_pattern.composite_score, 3),
            }
            for vi in validated_insights
        ]
    }
    
    return top_patterns, debug_metadata
