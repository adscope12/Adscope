"""Map PatternCandidates to BusinessInsights using fixed registry."""

from typing import List, Dict, Tuple, Optional, Any
import pandas as pd
from ..models.insight import ScoredPatternCandidate
from .registry import (
    REGISTRY, BusinessInsightDefinition, BusinessInsight
)
from ..selection.selection_utils import extract_segment_id
from ..scoring.composite_scorer import MIN_EFFECT_SIZE
from ..candidate_generation.pattern_types import PatternType


# Quality gate thresholds (same as selection)
MIN_COMPOSITE_SCORE = 0.15
MIN_SUPPORT = 0.35
# MIN_EFFECT_SIZE imported from composite_scorer (0.02)

# Suppression map: Tier 2 insights that suppress Tier 1 insights
# Format: {tier2_insight_id: [list of tier1_insight_ids to suppress]}
# Suppression applies when:
# - Same segment_id (or overlapping segments)
# - Same metric (or related metrics)
# - Tier 2 insight is triggered
SUPPRESSION_MAP: Dict[str, List[str]] = {
    # Budget efficiency Tier 2 insights suppress related Tier 1 insights
    "underfunded_winner": ["segment_above_baseline"],  # If underfunded_winner triggers, suppress segment_above_baseline for same segment (ROAS)
    "overfunded_underperformer": ["segment_below_baseline"],  # If overfunded_underperformer triggers, suppress segment_below_baseline for same segment (ROAS)
    
    # Performance gaps Tier 2 insights
    "hidden_high_performer": ["segment_above_baseline"],  # If hidden_high_performer triggers, suppress segment_above_baseline for same segment (ROAS)
    "conversion_efficiency_gap": ["segment_above_baseline", "segment_below_baseline"],  # Suppresses CTR above/below and CVR below/above for same segment
    
    # Value quality shift
    "high_volume_low_value": ["segment_above_baseline", "segment_below_baseline"],  # Suppresses conversions above and revenue below for same segment
    
    # Funnel breakdown
    "leakage_detection": ["segment_above_baseline", "segment_below_baseline"],  # Suppresses CTR above and CVR below for same segment
    
    # Budget dynamics
    "budget_saturation_signal": ["segment_above_baseline"],  # Suppresses spend above baseline for same segment
    
    # Creative health
    "creative_fatigue_signal": ["segment_below_baseline"],  # Suppresses CTR below baseline for same segment
    
    # Note: Meta insights (risk_flags) do not suppress other insights, they are appended separately
}

# Meta insights that should be appended last and not consume diversity slots
META_INSIGHTS = {"risk_flags"}


def map_candidates_to_business_insights(
    candidates: List[ScoredPatternCandidate],
    top_n: int = 4,
    debug: bool = False,
    dataframe: Optional[pd.DataFrame] = None,
    analysis_mode: str = "full"
) -> Tuple[List[BusinessInsight], Dict]:
    """
    Map PatternCandidates to BusinessInsights using fixed registry.
    
    Process:
    1. For each definition in registry, find matching candidates (Tier 1) or compute from dataframe (Tier 2)
    2. Apply quality gates (composite_score, support, effect_size)
    3. Select best candidate per definition (by composite_score)
    4. Apply diversity constraints (max 1 per segment_id, max 1 per insight type)
    5. Return top_n business insights
    
    Args:
        candidates: List of scored pattern candidates
        top_n: Target number of business insights (default 4)
        debug: If True, return debug metadata
        dataframe: Original dataframe for Tier 2 share calculations (optional)
        
    Returns:
        Tuple of (business_insights, debug_metadata)
    """
    if not candidates:
        return [], {"definitions_triggered": {}, "candidates_matched": {}}
    
    # Step 1: Match candidates to definitions
    matches_by_definition: Dict[str, List[ScoredPatternCandidate]] = {}
    tier2_insights: Dict[str, BusinessInsight] = {}
    
    for definition in REGISTRY:
        # Skip revenue/ROAS insights in PERFORMANCE mode
        if analysis_mode == "performance":
            # Check if this definition requires revenue/ROAS
            if definition.trigger_metrics:
                revenue_metrics = ['revenue', 'roas', 'aov', 'spend/revenue_ratio']
                if any(metric in revenue_metrics for metric in definition.trigger_metrics):
                    continue
            # Check Tier 2 insights that require revenue
            if definition.id in ["underfunded_winner", "overfunded_underperformer", 
                                 "revenue_concentration_risk", "weekend_weekday_roi_shift",
                                 "high_volume_low_value"]:
                continue
        
        if definition.tier == 1:
            # Tier 1: Match from candidates
            if definition.trigger_pattern_type is None or definition.trigger_metrics is None:
                continue
            
            matching_candidates = []
            
            for sp in candidates:
                candidate = sp.candidate
                
                # Check pattern type
                if candidate.pattern_type != definition.trigger_pattern_type:
                    continue
                
                # Check metric
                if candidate.metric_name not in definition.trigger_metrics:
                    continue
                
                # Check quality gates
                if not _passes_quality_gates(sp):
                    continue
                
                # Check additional trigger condition if defined
                if definition.trigger_condition:
                    if not definition.trigger_condition(candidate):
                        continue
                
                matching_candidates.append(sp)
            
            if matching_candidates:
                matches_by_definition[definition.id] = matching_candidates
        
        elif definition.tier == 2:
            # Tier 2: Compute from dataframe and candidates
            # Some Tier 2 insights need dataframe, others work with candidates only
            needs_dataframe = definition.id in ["underfunded_winner", "overfunded_underperformer", 
                                                 "revenue_concentration_risk", "platform_dependency_risk",
                                                 "platform_time_mismatch", "weekend_weekday_roi_shift",
                                                 "platform_funnel_role", "audience_platform_fit",
                                                 "month_over_month_narrative"]
            if not needs_dataframe or dataframe is not None:
                tier2_insight = _compute_tier2_insight(definition, candidates, dataframe, debug)
                if tier2_insight:
                    tier2_insights[definition.id] = tier2_insight
    
    # Step 2: Select best candidate per definition (by composite_score) for Tier 1
    best_candidates: Dict[str, ScoredPatternCandidate] = {}
    
    for definition_id, matching_candidates in matches_by_definition.items():
        # Sort by composite_score (descending) and take best
        sorted_candidates = sorted(
            matching_candidates,
            key=lambda x: x.composite_score,
            reverse=True
        )
        best_candidates[definition_id] = sorted_candidates[0]
    
    # Step 3: Combine Tier 1 and Tier 2 insights, then apply suppression
    all_insights: List[Tuple[str, BusinessInsight, float]] = []  # (id, insight, score)
    
    # Add Tier 1 insights
    tier1_insights_dict: Dict[str, BusinessInsight] = {}
    for definition_id, sp in best_candidates.items():
        definition = next(d for d in REGISTRY if d.id == definition_id)
        business_insight = _build_business_insight(definition, sp)
        tier1_insights_dict[definition_id] = business_insight
        all_insights.append((definition_id, business_insight, sp.composite_score))
    
    # Add Tier 2 insights (non-meta)
    tier2_insights_dict: Dict[str, BusinessInsight] = {}
    for definition_id, business_insight in tier2_insights.items():
        if definition_id not in META_INSIGHTS:
            tier2_insights_dict[definition_id] = business_insight
            all_insights.append((definition_id, business_insight, business_insight.importance_score))
    
    # Compute risk_flags (Meta insight) after other Tier 2 insights are collected
    meta_insights_dict: Dict[str, BusinessInsight] = {}
    risk_flags_insight = _compute_risk_flags(candidates, tier2_insights, debug)
    if risk_flags_insight:
        tier2_insights["risk_flags"] = risk_flags_insight
        meta_insights_dict["risk_flags"] = risk_flags_insight
    
    # Step 4: Apply suppression - Tier 2 insights suppress related Tier 1 insights
    suppressed_insights: Dict[str, str] = {}  # {suppressed_insight_id: suppressed_by_insight_id}
    
    for tier2_id, tier2_insight in tier2_insights_dict.items():
        if tier2_id in SUPPRESSION_MAP:
            suppressed_tier1_ids = SUPPRESSION_MAP[tier2_id]
            tier2_segment_id = tier2_insight.segment_id
            tier2_metric = tier2_insight.metric
            
            for tier1_id in suppressed_tier1_ids:
                if tier1_id in tier1_insights_dict:
                    tier1_insight = tier1_insights_dict[tier1_id]
                    tier1_segment_id = tier1_insight.segment_id
                    tier1_metric = tier1_insight.metric
                    
                    # Suppress if same segment (or overlapping) and related metric
                    should_suppress = False
                    
                    # Check segment overlap (exact match or one contains the other)
                    if tier1_segment_id == tier2_segment_id:
                        should_suppress = True
                    elif "_vs_" in tier1_segment_id and tier2_segment_id in tier1_segment_id:
                        should_suppress = True
                    elif "_vs_" in tier2_segment_id and tier1_segment_id in tier2_segment_id:
                        should_suppress = True
                    
                    # For specific suppressions, check metric relevance
                    if should_suppress:
                        # conversion_efficiency_gap suppresses CTR/CVR insights
                        if tier2_id == "conversion_efficiency_gap":
                            if tier1_metric in ["ctr", "cvr"]:
                                suppressed_insights[tier1_id] = tier2_id
                        # leakage_detection suppresses CTR/CVR insights
                        elif tier2_id == "leakage_detection":
                            if tier1_metric in ["ctr", "cvr"]:
                                suppressed_insights[tier1_id] = tier2_id
                        # high_volume_low_value suppresses conversions/revenue insights
                        elif tier2_id == "high_volume_low_value":
                            if tier1_metric in ["conversions", "revenue"]:
                                suppressed_insights[tier1_id] = tier2_id
                        # budget_saturation_signal suppresses spend insights
                        elif tier2_id == "budget_saturation_signal":
                            if tier1_metric == "spend":
                                suppressed_insights[tier1_id] = tier2_id
                        # creative_fatigue_signal suppresses CTR insights
                        elif tier2_id == "creative_fatigue_signal":
                            if tier1_metric == "ctr":
                                suppressed_insights[tier1_id] = tier2_id
                        # ROAS-related suppressions (underfunded_winner, overfunded_underperformer, hidden_high_performer)
                        elif tier2_id in ["underfunded_winner", "overfunded_underperformer", "hidden_high_performer"]:
                            if tier1_metric == "roas":
                                suppressed_insights[tier1_id] = tier2_id
    
    # Remove suppressed Tier 1 insights from all_insights
    filtered_insights = [
        (insight_id, insight, score)
        for insight_id, insight, score in all_insights
        if insight_id not in suppressed_insights
    ]
    
    # Step 5: Split into Tier 1, Tier 2, and meta insights
    # Get tier for each insight from registry
    tier1_primary = []
    tier2_primary = []
    meta_insights_list = []
    
    for insight_id, insight, score in filtered_insights:
        if insight_id in META_INSIGHTS:
            meta_insights_list.append((insight_id, insight, score))
        else:
            # Determine tier from registry
            definition = next((d for d in REGISTRY if d.id == insight_id), None)
            if definition:
                if definition.tier == 1:
                    tier1_primary.append((insight_id, insight, score))
                elif definition.tier == 2:
                    tier2_primary.append((insight_id, insight, score))
    
    # Also add meta insights from meta_insights_dict (computed separately)
    for meta_id, meta_insight in meta_insights_dict.items():
        meta_insights_list.append((meta_id, meta_insight, meta_insight.importance_score))
    
    # Sort Tier 2 by importance_score (descending)
    tier2_primary.sort(key=lambda x: x[2], reverse=True)
    # Sort Tier 1 by importance_score (descending)
    tier1_primary.sort(key=lambda x: x[2], reverse=True)
    
    # Step 6: Select Tier 2 insights first (up to max_primary), then fill with Tier 1
    selected_primary = []
    used_segment_ids = set()
    max_primary = top_n  # Primary insights limited to top_n (default 4)
    
    tier2_selected_count = 0
    tier1_selected_count = 0
    
    # First pass: Select Tier 2 insights (highest composite_score first)
    for definition_id, business_insight, score in tier2_primary:
        if len(selected_primary) >= max_primary:
            break
        
        segment_id = business_insight.segment_id
        
        # Enforce segment uniqueness
        if segment_id in used_segment_ids:
            continue
        
        selected_primary.append(business_insight)
        used_segment_ids.add(segment_id)
        tier2_selected_count += 1
    
    # Second pass: Fill remaining slots with Tier 1 insights (if any slots remain)
    fill_required = len(selected_primary) < max_primary
    for definition_id, business_insight, score in tier1_primary:
        if len(selected_primary) >= max_primary:
            break
        
        segment_id = business_insight.segment_id
        
        # Enforce segment uniqueness
        if segment_id in used_segment_ids:
            continue
        
        selected_primary.append(business_insight)
        used_segment_ids.add(segment_id)
        tier1_selected_count += 1
    
    fewer_than_4 = len(selected_primary) < max_primary
    
    # Step 7: Meta insights are appended separately (no diversity constraints, no truncation)
    selected_meta = [insight for _, insight, _ in meta_insights_list]
    
    # Combine: primary first, then meta
    selected_insights = selected_primary + selected_meta
    
    # Build debug metadata
    debug_meta = {}
    if debug:
        tier1_counts = {
            def_id: len(candidates_list)
            for def_id, candidates_list in matches_by_definition.items()
        }
        tier2_counts = {
            def_id: 1 if def_id in tier2_insights else 0
            for def_id in [d.id for d in REGISTRY if d.tier == 2]
        }
        debug_meta = {
            "definitions_triggered": {**tier1_counts, **tier2_counts},
            "candidates_matched": tier1_counts,
            "tier2_insights": {def_id: insight.supporting_candidates for def_id, insight in tier2_insights.items()},
            "suppressed_insights": suppressed_insights,  # {suppressed_id: suppressed_by_id}
            "meta_insights": list(meta_insights_dict.keys()),
            "primary_selected": len(selected_primary),
            "meta_appended": len(selected_meta),
            "tier2_selected": tier2_selected_count,
            "tier1_selected": tier1_selected_count,
            "fill_required": fill_required,
            "fewer_than_4": fewer_than_4
        }
    
    return selected_insights, debug_meta


def _passes_quality_gates(scored_pattern: ScoredPatternCandidate) -> bool:
    """Check if candidate passes quality gates."""
    return (
        scored_pattern.composite_score >= MIN_COMPOSITE_SCORE and
        scored_pattern.statistical_support >= MIN_SUPPORT and
        scored_pattern.effect_size >= MIN_EFFECT_SIZE
    )


def _build_business_insight(
    definition: BusinessInsightDefinition,
    scored_candidate: ScoredPatternCandidate
) -> BusinessInsight:
    """Build BusinessInsight object from definition and candidate - pure structured data."""
    candidate = scored_candidate.candidate
    
    # Extract fields
    segment_id = extract_segment_id(candidate)
    dimension = list(candidate.dimensions.keys())[0] if candidate.dimensions else "unknown"
    
    # Compute deltas
    baseline_value = candidate.baseline_value if candidate.baseline_value is not None else 0.0
    absolute_delta = candidate.observed_value - baseline_value
    relative_delta_pct = (absolute_delta / (abs(baseline_value) + 1e-9)) * 100
    
    return BusinessInsight(
        id=definition.id,
        category=definition.category,
        segment_id=segment_id,
        dimension=dimension,
        metric=candidate.metric_name,
        observed_value=candidate.observed_value,
        baseline_value=baseline_value,
        absolute_delta=absolute_delta,
        relative_delta_pct=relative_delta_pct,
        importance_score=scored_candidate.composite_score,
        confidence=scored_candidate.statistical_support,
        source_pattern_type=candidate.pattern_type.value,
        supporting_candidates=[scored_candidate.candidate.pattern_id]  # Store pattern ID for reference
    )


def _compute_tier2_insight(
    definition: BusinessInsightDefinition,
    candidates: List[ScoredPatternCandidate],
    dataframe: Optional[pd.DataFrame],
    debug: bool
) -> Optional[BusinessInsight]:
    """Compute Tier 2 insight from dataframe and candidates."""
    
    if definition.id == "underfunded_winner":
        return _compute_underfunded_winner(definition, candidates, dataframe, debug)
    elif definition.id == "overfunded_underperformer":
        return _compute_overfunded_underperformer(definition, candidates, dataframe, debug)
    elif definition.id == "revenue_concentration_risk":
        return _compute_revenue_concentration_risk(definition, dataframe, debug)
    elif definition.id == "platform_dependency_risk":
        return _compute_platform_dependency_risk(definition, dataframe, debug)
    elif definition.id == "high_volume_low_value":
        return _compute_high_volume_low_value(definition, candidates, debug)
    elif definition.id == "leakage_detection":
        return _compute_leakage_detection(definition, candidates, debug)
    elif definition.id == "budget_saturation_signal":
        return _compute_budget_saturation_signal(definition, candidates, debug)
    elif definition.id == "creative_fatigue_signal":
        return _compute_creative_fatigue_signal(definition, candidates, debug)
    elif definition.id == "platform_time_mismatch":
        return _compute_platform_time_mismatch(definition, candidates, dataframe, debug)
    elif definition.id == "weekend_weekday_roi_shift":
        return _compute_weekend_weekday_roi_shift(definition, candidates, dataframe, debug)
    elif definition.id == "platform_funnel_role":
        return _compute_platform_funnel_role(definition, candidates, dataframe, debug)
    elif definition.id == "audience_platform_fit":
        return _compute_audience_platform_fit(definition, candidates, dataframe, debug)
    elif definition.id == "month_over_month_narrative":
        return _compute_month_over_month_narrative(definition, candidates, dataframe, debug)
    elif definition.id == "risk_flags":
        # risk_flags is computed separately after all Tier 2 insights are collected
        return None
    
    return None


def _compute_underfunded_winner(
    definition: BusinessInsightDefinition,
    candidates: List[ScoredPatternCandidate],
    dataframe: pd.DataFrame,
    debug: bool
) -> Optional[BusinessInsight]:
    """Compute underfunded_winner: ROAS above baseline AND spend_share < 0.30."""
    
    if 'spend' not in dataframe.columns or 'roas' not in dataframe.columns:
        return None
    
    # Find segments with ROAS above baseline
    # Check SEGMENT_ABOVE_BASELINE and winner side of SEGMENT_GAP
    roas_candidates = []
    for sp in candidates:
        candidate = sp.candidate
        if candidate.metric_name != 'roas' or not _passes_quality_gates(sp):
            continue
        
        if candidate.pattern_type == PatternType.SEGMENT_ABOVE_BASELINE:
            if candidate.baseline_value is not None and candidate.observed_value > candidate.baseline_value:
                roas_candidates.append(sp)
        elif candidate.pattern_type == PatternType.SEGMENT_GAP:
            # Check if this is the winner (top) side of the gap
            if candidate.baseline_value is not None and candidate.observed_value > candidate.baseline_value:
                roas_candidates.append(sp)
    
    if not roas_candidates:
        return None
    
    # For each dimension, compute spend_share and check threshold
    for sp in sorted(roas_candidates, key=lambda x: x.composite_score, reverse=True):
        candidate = sp.candidate
        dimension = list(candidate.dimensions.keys())[0] if candidate.dimensions else None
        segment_value = candidate.primary_segment.get('value') if candidate.primary_segment else None
        
        if dimension is None or segment_value is None:
            continue
        
        if dimension not in dataframe.columns:
            continue
        
        # Compute spend_share for this segment
        segment_df = dataframe[dataframe[dimension] == segment_value]
        total_spend = dataframe['spend'].sum()
        segment_spend = segment_df['spend'].sum()
        
        if total_spend == 0:
            continue
        
        spend_share = segment_spend / total_spend
        
        if spend_share < 0.30:
            # Found underfunded winner
            baseline_value = candidate.baseline_value if candidate.baseline_value is not None else 0.0
            absolute_delta = candidate.observed_value - baseline_value
            relative_delta_pct = (absolute_delta / (abs(baseline_value) + 1e-9)) * 100
            
            supporting_info = {
                'pattern_id': candidate.pattern_id,
                'spend_share': spend_share,
                'segment_spend': segment_spend,
                'total_spend': total_spend
            }
            
            return BusinessInsight(
                id=definition.id,
                category=definition.category,
                segment_id=extract_segment_id(candidate),
                dimension=dimension,
                metric='roas',
                observed_value=candidate.observed_value,
                baseline_value=baseline_value,
                absolute_delta=absolute_delta,
                relative_delta_pct=relative_delta_pct,
                importance_score=sp.composite_score,
                confidence=sp.statistical_support,
                source_pattern_type=candidate.pattern_type.value,
                supporting_candidates=[str(supporting_info)] if debug else [candidate.pattern_id]
            )
    
    return None


def _compute_overfunded_underperformer(
    definition: BusinessInsightDefinition,
    candidates: List[ScoredPatternCandidate],
    dataframe: pd.DataFrame,
    debug: bool
) -> Optional[BusinessInsight]:
    """Compute overfunded_underperformer: ROAS below baseline AND spend_share > 0.40."""
    
    if 'spend' not in dataframe.columns or 'roas' not in dataframe.columns:
        return None
    
    # Find segments with ROAS below baseline
    roas_candidates = [
        sp for sp in candidates
        if sp.candidate.pattern_type == PatternType.SEGMENT_BELOW_BASELINE
        and sp.candidate.metric_name == 'roas'
        and _passes_quality_gates(sp)
        and sp.candidate.baseline_value is not None
        and sp.candidate.observed_value < sp.candidate.baseline_value
    ]
    
    if not roas_candidates:
        return None
    
    # For each dimension, compute spend_share and check threshold
    for sp in sorted(roas_candidates, key=lambda x: x.composite_score, reverse=True):
        candidate = sp.candidate
        dimension = list(candidate.dimensions.keys())[0] if candidate.dimensions else None
        segment_value = candidate.primary_segment.get('value') if candidate.primary_segment else None
        
        if dimension is None or segment_value is None:
            continue
        
        if dimension not in dataframe.columns:
            continue
        
        # Compute spend_share for this segment
        segment_df = dataframe[dataframe[dimension] == segment_value]
        total_spend = dataframe['spend'].sum()
        segment_spend = segment_df['spend'].sum()
        
        if total_spend == 0:
            continue
        
        spend_share = segment_spend / total_spend
        
        if spend_share > 0.40:
            # Found overfunded underperformer
            baseline_value = candidate.baseline_value if candidate.baseline_value is not None else 0.0
            absolute_delta = candidate.observed_value - baseline_value
            relative_delta_pct = (absolute_delta / (abs(baseline_value) + 1e-9)) * 100
            
            supporting_info = {
                'pattern_id': candidate.pattern_id,
                'spend_share': spend_share,
                'segment_spend': segment_spend,
                'total_spend': total_spend
            }
            
            return BusinessInsight(
                id=definition.id,
                category=definition.category,
                segment_id=extract_segment_id(candidate),
                dimension=dimension,
                metric='roas',
                observed_value=candidate.observed_value,
                baseline_value=baseline_value,
                absolute_delta=absolute_delta,
                relative_delta_pct=relative_delta_pct,
                importance_score=sp.composite_score,
                confidence=sp.statistical_support,
                source_pattern_type=candidate.pattern_type.value,
                supporting_candidates=[str(supporting_info)] if debug else [candidate.pattern_id]
            )
    
    return None


def _compute_revenue_concentration_risk(
    definition: BusinessInsightDefinition,
    dataframe: pd.DataFrame,
    debug: bool
) -> Optional[BusinessInsight]:
    """Compute revenue_concentration_risk: revenue_share >= 0.60 for a single segment."""
    
    if 'revenue' not in dataframe.columns:
        return None
    
    total_revenue = dataframe['revenue'].sum()
    if total_revenue == 0:
        return None
    
    # Check each dimension
    dimensions = [col for col in dataframe.columns if col not in ['spend', 'revenue', 'roas', 'cpc', 'cpa', 'ctr', 'cvr', 'conversions', 'clicks', 'impressions', 'date', 'week', 'month']]
    
    for dimension in dimensions:
        if dimension not in dataframe.columns:
            continue
        
        # Compute revenue_share per segment
        segment_revenues = dataframe.groupby(dimension)['revenue'].sum()
        
        for segment_value, segment_revenue in segment_revenues.items():
            revenue_share = segment_revenue / total_revenue
            
            if revenue_share >= 0.60:
                # Found concentration risk
                segment_df = dataframe[dataframe[dimension] == segment_value]
                observed_value = segment_df['revenue'].mean()
                baseline_value = dataframe['revenue'].mean()
                absolute_delta = observed_value - baseline_value
                relative_delta_pct = (absolute_delta / (abs(baseline_value) + 1e-9)) * 100
                
                supporting_info = {
                    'revenue_share': revenue_share,
                    'segment_revenue': segment_revenue,
                    'total_revenue': total_revenue
                }
                
                return BusinessInsight(
                    id=definition.id,
                    category=definition.category,
                    segment_id=str(segment_value),
                    dimension=dimension,
                    metric='revenue',
                    observed_value=observed_value,
                    baseline_value=baseline_value,
                    absolute_delta=absolute_delta,
                    relative_delta_pct=relative_delta_pct,
                    importance_score=0.5,  # Default score for Tier 2
                    confidence=0.8,  # Default confidence for Tier 2
                    source_pattern_type='CONCENTRATION_RISK',
                    supporting_candidates=[str(supporting_info)] if debug else []
                )
    
    return None


def _compute_platform_dependency_risk(
    definition: BusinessInsightDefinition,
    dataframe: pd.DataFrame,
    debug: bool
) -> Optional[BusinessInsight]:
    """Compute platform_dependency_risk: spend_share >= 0.70 OR revenue_share >= 0.70 for one platform."""
    
    if 'platform' not in dataframe.columns:
        return None
    
    if 'spend' not in dataframe.columns:
        return None
    
    has_revenue = 'revenue' in dataframe.columns
    total_spend = dataframe['spend'].sum()
    total_revenue = dataframe['revenue'].sum() if has_revenue else 0
    
    if total_spend == 0:
        return None
    
    # Compute shares per platform
    if has_revenue:
        platform_stats = dataframe.groupby('platform').agg({
            'spend': 'sum',
            'revenue': 'sum'
        })
    else:
        platform_stats = dataframe.groupby('platform').agg({
            'spend': 'sum'
        })
    
    for platform_value, stats in platform_stats.iterrows():
        spend_share = stats['spend'] / total_spend if total_spend > 0 else 0.0
        revenue_share = stats['revenue'] / total_revenue if has_revenue and total_revenue > 0 else 0.0
        
        if spend_share >= 0.70 or (has_revenue and revenue_share >= 0.70):
            # Found platform dependency risk
            platform_df = dataframe[dataframe['platform'] == platform_value]
            if has_revenue and revenue_share >= 0.70:
                observed_value = platform_df['revenue'].mean()
                baseline_value = dataframe['revenue'].mean()
                metric = 'revenue'
            else:
                observed_value = platform_df['spend'].mean()
                baseline_value = dataframe['spend'].mean()
                metric = 'spend'
            absolute_delta = observed_value - baseline_value
            relative_delta_pct = (absolute_delta / (abs(baseline_value) + 1e-9)) * 100
            
            supporting_info = {
                'spend_share': spend_share,
                'revenue_share': revenue_share if has_revenue else None,
                'platform_spend': stats['spend'],
                'platform_revenue': stats.get('revenue', None) if has_revenue else None,
                'total_spend': total_spend,
                'total_revenue': total_revenue if has_revenue else None
            }
            
            return BusinessInsight(
                id=definition.id,
                category=definition.category,
                segment_id=str(platform_value),
                dimension='platform',
                metric=metric,
                observed_value=observed_value,
                baseline_value=baseline_value,
                absolute_delta=absolute_delta,
                relative_delta_pct=relative_delta_pct,
                importance_score=0.5,  # Default score for Tier 2
                confidence=0.8,  # Default confidence for Tier 2
                source_pattern_type='PLATFORM_DEPENDENCY_RISK',
                supporting_candidates=[str(supporting_info)] if debug else []
            )
    
    return None


def _compute_high_volume_low_value(
    definition: BusinessInsightDefinition,
    candidates: List[ScoredPatternCandidate],
    debug: bool
) -> Optional[BusinessInsight]:
    """Compute high_volume_low_value: conversions increased but revenue_per_conversion decreased."""
    
    # Find segments with conversions above baseline
    conversions_candidates = [
        sp for sp in candidates
        if sp.candidate.pattern_type == PatternType.SEGMENT_ABOVE_BASELINE
        and sp.candidate.metric_name == 'conversions'
        and sp.statistical_support >= 0.5
        and sp.candidate.baseline_value is not None
        and sp.candidate.observed_value > sp.candidate.baseline_value
    ]
    
    if not conversions_candidates:
        return None
    
    # For each segment with high conversions, check if revenue_per_conversion decreased
    for sp_conversions in sorted(conversions_candidates, key=lambda x: x.composite_score, reverse=True):
        candidate_conversions = sp_conversions.candidate
        segment_id = extract_segment_id(candidate_conversions)
        dimension = list(candidate_conversions.dimensions.keys())[0] if candidate_conversions.dimensions else None
        
        if dimension is None:
            continue
        
        # Compute conversions delta
        baseline_conversions = candidate_conversions.baseline_value
        observed_conversions = candidate_conversions.observed_value
        conversions_delta = (observed_conversions - baseline_conversions) / (abs(baseline_conversions) + 1e-9)
        
        if conversions_delta < 0.25:
            continue
        
        # Find revenue candidate for same segment (below baseline indicates RPC decrease)
        revenue_candidate = None
        for sp in candidates:
            candidate = sp.candidate
            if (candidate.pattern_type == PatternType.SEGMENT_BELOW_BASELINE and
                candidate.metric_name == 'revenue' and
                extract_segment_id(candidate) == segment_id and
                sp.statistical_support >= 0.5):
                revenue_candidate = sp
                break
        
        if revenue_candidate is None:
            continue
        
        # Compute revenue_per_conversion deltas
        baseline_revenue = revenue_candidate.candidate.baseline_value
        observed_revenue = revenue_candidate.candidate.observed_value
        
        if baseline_revenue is None or baseline_conversions is None:
            continue
        
        baseline_rpc = baseline_revenue / (baseline_conversions + 1e-9)
        observed_rpc = observed_revenue / (observed_conversions + 1e-9)
        
        if abs(baseline_rpc) < 1e-9:
            continue
        
        rpc_delta = (observed_rpc - baseline_rpc) / abs(baseline_rpc)
        
        if rpc_delta > -0.15:  # Not decreased enough
            continue
        
        # Found high volume low value
        confidence = min(sp_conversions.statistical_support, revenue_candidate.statistical_support)
        importance_score = (sp_conversions.composite_score + revenue_candidate.composite_score) / 2
        
        supporting_info = {
            'conversions_delta': conversions_delta,
            'revenue_per_conversion_delta': rpc_delta,
            'conversions_pattern_id': candidate_conversions.pattern_id,
            'revenue_pattern_id': revenue_candidate.candidate.pattern_id
        }
        
        return BusinessInsight(
            id=definition.id,
            category=definition.category,
            segment_id=segment_id,
            dimension=dimension,
            metric='revenue_per_conversion',
            observed_value=observed_rpc,
            baseline_value=baseline_rpc,
            absolute_delta=observed_rpc - baseline_rpc,
            relative_delta_pct=rpc_delta * 100,
            importance_score=importance_score,
            confidence=confidence,
            source_pattern_type='COMPOSITE',
            supporting_candidates=[str(supporting_info)] if debug else [candidate_conversions.pattern_id, revenue_candidate.candidate.pattern_id]
        )
    
    return None


def _compute_leakage_detection(
    definition: BusinessInsightDefinition,
    candidates: List[ScoredPatternCandidate],
    debug: bool
) -> Optional[BusinessInsight]:
    """Compute leakage_detection: CTR above baseline but CVR below baseline."""
    
    # Find segments with CTR above baseline
    ctr_candidates = [
        sp for sp in candidates
        if sp.candidate.pattern_type == PatternType.SEGMENT_ABOVE_BASELINE
        and sp.candidate.metric_name == 'ctr'
        and sp.statistical_support >= 0.5
        and sp.candidate.baseline_value is not None
        and sp.candidate.observed_value > sp.candidate.baseline_value
    ]
    
    if not ctr_candidates:
        return None
    
    # For each segment with high CTR, check if CVR decreased
    for sp_ctr in sorted(ctr_candidates, key=lambda x: x.composite_score, reverse=True):
        candidate_ctr = sp_ctr.candidate
        segment_id = extract_segment_id(candidate_ctr)
        dimension = list(candidate_ctr.dimensions.keys())[0] if candidate_ctr.dimensions else None
        
        if dimension is None:
            continue
        
        # Compute CTR delta
        baseline_ctr = candidate_ctr.baseline_value
        observed_ctr = candidate_ctr.observed_value
        ctr_delta = (observed_ctr - baseline_ctr) / (abs(baseline_ctr) + 1e-9)
        
        if ctr_delta < 0.15:
            continue
        
        # Find CVR candidate for same segment with below baseline
        cvr_candidate = None
        for sp in candidates:
            candidate = sp.candidate
            if (candidate.pattern_type == PatternType.SEGMENT_BELOW_BASELINE and
                candidate.metric_name == 'cvr' and
                extract_segment_id(candidate) == segment_id and
                sp.statistical_support >= 0.5):
                cvr_candidate = sp
                break
        
        if cvr_candidate is None:
            continue
        
        # Compute CVR delta
        baseline_cvr = cvr_candidate.candidate.baseline_value
        observed_cvr = cvr_candidate.candidate.observed_value
        
        if baseline_cvr is None:
            continue
        
        cvr_delta = (observed_cvr - baseline_cvr) / (abs(baseline_cvr) + 1e-9)
        
        if cvr_delta > -0.15:  # Not decreased enough
            continue
        
        # Found leakage
        confidence = min(sp_ctr.statistical_support, cvr_candidate.statistical_support)
        importance_score = (sp_ctr.composite_score + cvr_candidate.composite_score) / 2
        
        supporting_info = {
            'ctr_delta': ctr_delta,
            'cvr_delta': cvr_delta,
            'ctr_pattern_id': candidate_ctr.pattern_id,
            'cvr_pattern_id': cvr_candidate.candidate.pattern_id
        }
        
        return BusinessInsight(
            id=definition.id,
            category=definition.category,
            segment_id=segment_id,
            dimension=dimension,
            metric='cvr',
            observed_value=observed_cvr,
            baseline_value=baseline_cvr,
            absolute_delta=observed_cvr - baseline_cvr,
            relative_delta_pct=cvr_delta * 100,
            importance_score=importance_score,
            confidence=confidence,
            source_pattern_type='COMPOSITE',
            supporting_candidates=[str(supporting_info)] if debug else [candidate_ctr.pattern_id, cvr_candidate.candidate.pattern_id]
        )
    
    return None


def _compute_budget_saturation_signal(
    definition: BusinessInsightDefinition,
    candidates: List[ScoredPatternCandidate],
    debug: bool
) -> Optional[BusinessInsight]:
    """Compute budget_saturation_signal: spend increases but ROAS/CVR doesn't improve proportionally."""
    
    # Find segments with spend increases (ABOVE_BASELINE or TEMPORAL_CHANGE)
    spend_candidates = []
    for sp in candidates:
        candidate = sp.candidate
        if (candidate.metric_name == 'spend' and
            sp.effect_size > 0.05 and
            candidate.pattern_type in [PatternType.SEGMENT_ABOVE_BASELINE, PatternType.TEMPORAL_CHANGE] and
            _passes_quality_gates(sp) and
            candidate.baseline_value is not None and
            candidate.observed_value > candidate.baseline_value):
            spend_candidates.append(sp)
    
    if not spend_candidates:
        return None
    
    # For each spend increase, check if ROAS or CVR improved proportionally
    for sp_spend in sorted(spend_candidates, key=lambda x: x.composite_score, reverse=True):
        candidate_spend = sp_spend.candidate
        segment_id = extract_segment_id(candidate_spend)
        dimension = list(candidate_spend.dimensions.keys())[0] if candidate_spend.dimensions else None
        
        if dimension is None:
            continue
        
        # Compute spend delta
        baseline_spend = candidate_spend.baseline_value
        observed_spend = candidate_spend.observed_value
        spend_delta = (observed_spend - baseline_spend) / (abs(baseline_spend) + 1e-9)
        
        # Check ROAS or CVR for same segment/dimension
        efficiency_candidate = None
        efficiency_metric = None
        
        # Try ROAS first
        for sp in candidates:
            candidate = sp.candidate
            if (candidate.metric_name == 'roas' and
                extract_segment_id(candidate) == segment_id and
                _passes_quality_gates(sp)):
                efficiency_candidate = sp
                efficiency_metric = 'roas'
                break
        
        # If no ROAS, try CVR
        if efficiency_candidate is None:
            for sp in candidates:
                candidate = sp.candidate
                if (candidate.metric_name == 'cvr' and
                    extract_segment_id(candidate) == segment_id and
                    _passes_quality_gates(sp)):
                    efficiency_candidate = sp
                    efficiency_metric = 'cvr'
                    break
        
        if efficiency_candidate is None:
            continue
        
        # Check if efficiency improved proportionally
        efficiency_effect_size = efficiency_candidate.effect_size
        
        # If effect_size < 0.02 or negative, efficiency didn't improve proportionally
        if efficiency_effect_size >= 0.02:
            continue  # Efficiency improved, not saturation
        
        # Found budget saturation signal
        baseline_efficiency = efficiency_candidate.candidate.baseline_value
        observed_efficiency = efficiency_candidate.candidate.observed_value
        
        if baseline_efficiency is None:
            continue
        
        efficiency_delta = (observed_efficiency - baseline_efficiency) / (abs(baseline_efficiency) + 1e-9)
        
        confidence = min(sp_spend.statistical_support, efficiency_candidate.statistical_support)
        importance_score = sp_spend.composite_score
        
        supporting_info = {
            'spend_delta': spend_delta,
            'efficiency_delta': efficiency_delta,
            'efficiency_metric': efficiency_metric,
            'spend_pattern_id': candidate_spend.pattern_id,
            'efficiency_pattern_id': efficiency_candidate.candidate.pattern_id,
            'spend_effect_size': sp_spend.effect_size,
            'efficiency_effect_size': efficiency_effect_size
        }
        
        return BusinessInsight(
            id=definition.id,
            category=definition.category,
            segment_id=segment_id,
            dimension=dimension,
            metric=efficiency_metric,
            observed_value=observed_efficiency,
            baseline_value=baseline_efficiency,
            absolute_delta=observed_efficiency - baseline_efficiency,
            relative_delta_pct=efficiency_delta * 100,
            importance_score=importance_score,
            confidence=confidence,
            source_pattern_type=candidate_spend.pattern_type.value,
            supporting_candidates=[str(supporting_info)] if debug else [candidate_spend.pattern_id, efficiency_candidate.candidate.pattern_id]
        )
    
    return None


def _compute_creative_fatigue_signal(
    definition: BusinessInsightDefinition,
    candidates: List[ScoredPatternCandidate],
    debug: bool
) -> Optional[BusinessInsight]:
    """Compute creative_fatigue_signal: CTR declines while CPC increases or spend stays stable."""
    
    # Find segments with CTR declines (BELOW_BASELINE or TEMPORAL_CHANGE)
    ctr_candidates = []
    for sp in candidates:
        candidate = sp.candidate
        if (candidate.metric_name == 'ctr' and
            sp.effect_size > 0.03 and
            candidate.pattern_type in [PatternType.SEGMENT_BELOW_BASELINE, PatternType.TEMPORAL_CHANGE] and
            _passes_quality_gates(sp) and
            candidate.baseline_value is not None and
            candidate.observed_value < candidate.baseline_value):
            ctr_candidates.append(sp)
    
    if not ctr_candidates:
        return None
    
    # For each CTR decline, check CPC or spend
    for sp_ctr in sorted(ctr_candidates, key=lambda x: x.composite_score, reverse=True):
        candidate_ctr = sp_ctr.candidate
        segment_id = extract_segment_id(candidate_ctr)
        dimension = list(candidate_ctr.dimensions.keys())[0] if candidate_ctr.dimensions else None
        
        if dimension is None:
            continue
        
        # Compute CTR delta
        baseline_ctr = candidate_ctr.baseline_value
        observed_ctr = candidate_ctr.observed_value
        ctr_delta = (observed_ctr - baseline_ctr) / (abs(baseline_ctr) + 1e-9)
        
        # Check CPC for same segment (prefer CPC increase)
        cpc_candidate = None
        for sp in candidates:
            candidate = sp.candidate
            if (candidate.metric_name == 'cpc' and
                extract_segment_id(candidate) == segment_id and
                _passes_quality_gates(sp) and
                candidate.baseline_value is not None and
                candidate.observed_value >= candidate.baseline_value):  # CPC increased or stable
                cpc_candidate = sp
                break
        
        # If no CPC increase, check if spend stayed stable (not decreased significantly)
        spend_candidate = None
        if cpc_candidate is None:
            for sp in candidates:
                candidate = sp.candidate
                if (candidate.metric_name == 'spend' and
                    extract_segment_id(candidate) == segment_id and
                    _passes_quality_gates(sp) and
                    candidate.baseline_value is not None):
                    spend_delta = (candidate.observed_value - candidate.baseline_value) / (abs(candidate.baseline_value) + 1e-9)
                    # Spend stable (not decreased by more than 10%)
                    if spend_delta >= -0.10:
                        spend_candidate = sp
                        break
        
        if cpc_candidate is None and spend_candidate is None:
            continue
        
        # Found creative fatigue signal
        if cpc_candidate:
            baseline_cpc = cpc_candidate.candidate.baseline_value
            observed_cpc = cpc_candidate.candidate.observed_value
            cpc_delta = (observed_cpc - baseline_cpc) / (abs(baseline_cpc) + 1e-9) if baseline_cpc else 0.0
            confidence = min(sp_ctr.statistical_support, cpc_candidate.statistical_support)
            importance_score = (sp_ctr.composite_score + cpc_candidate.composite_score) / 2
            metric_value = observed_cpc
            baseline_value = baseline_cpc
            metric_name = 'cpc'
            supporting_pattern_ids = [candidate_ctr.pattern_id, cpc_candidate.candidate.pattern_id]
        else:
            baseline_spend = spend_candidate.candidate.baseline_value
            observed_spend = spend_candidate.candidate.observed_value
            cpc_delta = None  # No CPC data
            confidence = min(sp_ctr.statistical_support, spend_candidate.statistical_support)
            importance_score = (sp_ctr.composite_score + spend_candidate.composite_score) / 2
            metric_value = observed_spend
            baseline_value = baseline_spend
            metric_name = 'spend'
            supporting_pattern_ids = [candidate_ctr.pattern_id, spend_candidate.candidate.pattern_id]
        
        supporting_info = {
            'ctr_delta': ctr_delta,
            'cpc_delta': cpc_delta,
            'ctr_pattern_id': candidate_ctr.pattern_id,
            'secondary_pattern_id': supporting_pattern_ids[1] if len(supporting_pattern_ids) > 1 else None,
            'ctr_effect_size': sp_ctr.effect_size
        }
        
        return BusinessInsight(
            id=definition.id,
            category=definition.category,
            segment_id=segment_id,
            dimension=dimension,
            metric=metric_name,
            observed_value=metric_value,
            baseline_value=baseline_value,
            absolute_delta=metric_value - baseline_value if baseline_value else 0.0,
            relative_delta_pct=ctr_delta * 100,
            importance_score=importance_score,
            confidence=confidence,
            source_pattern_type=candidate_ctr.pattern_type.value,
            supporting_candidates=[str(supporting_info)] if debug else supporting_pattern_ids
        )
    
    return None


def _compute_platform_time_mismatch(
    definition: BusinessInsightDefinition,
    candidates: List[ScoredPatternCandidate],
    dataframe: Optional[pd.DataFrame],
    debug: bool
) -> Optional[BusinessInsight]:
    """Compute platform_time_mismatch: platforms perform differently at same time window."""
    
    if dataframe is None or 'platform' not in dataframe.columns:
        return None
    
    # Need date or time dimension
    time_dim = None
    for col in ['date', 'day', 'hour']:
        if col in dataframe.columns:
            time_dim = col
            break
    
    if time_dim is None:
        return None
    
    # Group by platform and time, compute performance metrics
    platforms = dataframe['platform'].unique()
    if len(platforms) < 2:
        return None
    
    # Check each time segment for platform mismatch
    time_segments = dataframe[time_dim].unique()
    
    for time_seg in time_segments:
        time_df = dataframe[dataframe[time_dim] == time_seg]
        
        platform_performance = {}
        for platform in platforms:
            platform_df = time_df[time_df['platform'] == platform]
            if len(platform_df) == 0:
                continue
            
            # Check ROAS or CVR
            metric_value = None
            metric_name = None
            
            if 'roas' in platform_df.columns:
                metric_value = platform_df['roas'].mean()
                metric_name = 'roas'
            elif 'cvr' in platform_df.columns:
                metric_value = platform_df['cvr'].mean()
                metric_name = 'cvr'
            
            if metric_value is not None:
                # Find corresponding candidate for effect_size
                effect_size = 0.0
                candidate_match = None
                for sp in candidates:
                    candidate = sp.candidate
                    if (candidate.metric_name == metric_name and
                        candidate.primary_segment and
                        candidate.primary_segment.get('value') == platform and
                        candidate.time_period and
                        str(time_seg) in str(candidate.time_period)):
                        effect_size = sp.effect_size
                        candidate_match = sp
                        break
                
                platform_performance[platform] = {
                    'value': metric_value,
                    'metric': metric_name,
                    'effect_size': effect_size,
                    'candidate': candidate_match
                }
        
        if len(platform_performance) < 2:
            continue
        
        # Find strong and weak platforms
        strong_platform = None
        weak_platform = None
        
        for platform, perf in platform_performance.items():
            if perf['effect_size'] > 0.05:
                if strong_platform is None or perf['effect_size'] > platform_performance[strong_platform]['effect_size']:
                    strong_platform = platform
            elif perf['effect_size'] < 0.02:
                if weak_platform is None or perf['effect_size'] < platform_performance[weak_platform]['effect_size']:
                    weak_platform = platform
        
        if strong_platform is None or weak_platform is None:
            continue
        
        # Check budget distribution (should be relatively similar, no extreme bias)
        total_spend = time_df['spend'].sum() if 'spend' in time_df.columns else 0
        if total_spend == 0:
            continue
        
        strong_spend = time_df[time_df['platform'] == strong_platform]['spend'].sum()
        weak_spend = time_df[time_df['platform'] == weak_platform]['spend'].sum()
        
        strong_spend_share = strong_spend / total_spend
        weak_spend_share = weak_spend / total_spend
        
        # Budget should be relatively similar (neither < 0.20 nor > 0.80)
        if strong_spend_share < 0.20 or strong_spend_share > 0.80:
            continue
        if weak_spend_share < 0.20 or weak_spend_share > 0.80:
            continue
        
        # Found platform time mismatch
        strong_perf = platform_performance[strong_platform]
        weak_perf = platform_performance[weak_platform]
        
        metric_name = strong_perf['metric']
        strong_value = strong_perf['value']
        weak_value = weak_perf['value']
        
        performance_delta = strong_value - weak_value
        relative_delta = performance_delta / (abs(weak_value) + 1e-9)
        
        strong_candidate = strong_perf['candidate']
        if strong_candidate:
            importance_score = strong_candidate.composite_score
            confidence = strong_candidate.statistical_support
        else:
            importance_score = 0.3
            confidence = 0.5
        
        supporting_info = {
            'strong_platform': strong_platform,
            'weak_platform': weak_platform,
            'time_segment': str(time_seg),
            'metric': metric_name,
            'strong_performance': strong_value,
            'weak_performance': weak_value,
            'performance_delta': performance_delta,
            'strong_spend_share': strong_spend_share,
            'weak_spend_share': weak_spend_share
        }
        
        return BusinessInsight(
            id=definition.id,
            category=definition.category,
            segment_id=f"{strong_platform}_vs_{weak_platform}_{time_seg}",
            dimension='platform',
            metric=metric_name,
            observed_value=strong_value,
            baseline_value=weak_value,
            absolute_delta=performance_delta,
            relative_delta_pct=relative_delta * 100,
            importance_score=importance_score,
            confidence=confidence,
            source_pattern_type='COMPOSITE',
            supporting_candidates=[str(supporting_info)] if debug else [f"{strong_platform}_{time_seg}", f"{weak_platform}_{time_seg}"]
        )
    
    return None


def _compute_weekend_weekday_roi_shift(
    definition: BusinessInsightDefinition,
    candidates: List[ScoredPatternCandidate],
    dataframe: Optional[pd.DataFrame],
    debug: bool
) -> Optional[BusinessInsight]:
    """Compute weekend_weekday_roi_shift: ROAS differs between weekends and weekdays."""
    
    if dataframe is None:
        return None
    
    # Need date column to determine weekday/weekend
    if 'date' not in dataframe.columns or 'roas' not in dataframe.columns:
        return None
    
    # Convert date to weekday (0=Monday, 6=Sunday)
    try:
        dataframe['weekday'] = pd.to_datetime(dataframe['date']).dt.dayofweek
    except:
        return None
    
    # Group into weekday (0-4) and weekend (5-6)
    weekday_df = dataframe[dataframe['weekday'] < 5]
    weekend_df = dataframe[dataframe['weekday'] >= 5]
    
    if len(weekday_df) == 0 or len(weekend_df) == 0:
        return None
    
    weekday_roas = weekday_df['roas'].mean()
    weekend_roas = weekend_df['roas'].mean()
    
    if pd.isna(weekday_roas) or pd.isna(weekend_roas):
        return None
    
    # Compute effect size (relative difference)
    if abs(weekday_roas) < 1e-9:
        return None
    
    roas_delta = weekend_roas - weekday_roas
    relative_delta = roas_delta / abs(weekday_roas)
    
    if abs(relative_delta) < 0.05:
        return None
    
    # Find matching temporal candidates for confidence
    best_candidate = None
    best_support = 0.0
    
    for sp in candidates:
        candidate = sp.candidate
        if (candidate.pattern_type == PatternType.TEMPORAL_CHANGE and
            candidate.metric_name == 'roas' and
            sp.statistical_support > best_support):
            best_support = sp.statistical_support
            best_candidate = sp
    
    if best_candidate:
        confidence = best_candidate.statistical_support
        importance_score = best_candidate.composite_score
    else:
        confidence = 0.5
        importance_score = 0.3
    
    supporting_info = {
        'weekend_roas': weekend_roas,
        'weekday_roas': weekday_roas,
        'absolute_delta': roas_delta,
        'relative_delta': relative_delta,
        'weekday_count': len(weekday_df),
        'weekend_count': len(weekend_df)
    }
    
    return BusinessInsight(
        id=definition.id,
        category=definition.category,
        segment_id='weekend_vs_weekday',
        dimension='date',
        metric='roas',
        observed_value=weekend_roas,
        baseline_value=weekday_roas,
        absolute_delta=roas_delta,
        relative_delta_pct=relative_delta * 100,
        importance_score=importance_score,
        confidence=confidence,
        source_pattern_type='TEMPORAL_CHANGE',
        supporting_candidates=[str(supporting_info)] if debug else ['weekend_vs_weekday']
    )


def _compute_platform_funnel_role(
    definition: BusinessInsightDefinition,
    candidates: List[ScoredPatternCandidate],
    dataframe: Optional[pd.DataFrame],
    debug: bool
) -> Optional[BusinessInsight]:
    """Compute platform_funnel_role: platforms play different roles (traffic driver vs closer)."""
    
    if dataframe is None or 'platform' not in dataframe.columns:
        return None
    
    platforms = dataframe['platform'].unique()
    if len(platforms) < 2:
        return None
    
    # Find platforms with high CTR/traffic but low conversion efficiency
    traffic_platforms = []  # High CTR, low CVR/ROAS
    conversion_platforms = []  # Lower CTR, high CVR/ROAS
    
    for platform in platforms:
        platform_df = dataframe[dataframe['platform'] == platform]
        if len(platform_df) == 0:
            continue
        
        # Check CTR and conversion metrics
        ctr_candidate = None
        cvr_candidate = None
        roas_candidate = None
        
        for sp in candidates:
            candidate = sp.candidate
            if candidate.primary_segment and candidate.primary_segment.get('value') == platform:
                if candidate.metric_name == 'ctr' and candidate.pattern_type == PatternType.SEGMENT_ABOVE_BASELINE:
                    ctr_candidate = sp
                elif candidate.metric_name == 'cvr' and candidate.pattern_type == PatternType.SEGMENT_BELOW_BASELINE:
                    cvr_candidate = sp
                elif candidate.metric_name == 'roas' and candidate.pattern_type == PatternType.SEGMENT_BELOW_BASELINE:
                    roas_candidate = sp
        
        # Check if high CTR but low conversion
        if ctr_candidate and (cvr_candidate or roas_candidate):
            traffic_platforms.append({
                'platform': platform,
                'ctr_candidate': ctr_candidate,
                'conversion_candidate': cvr_candidate or roas_candidate
            })
        
        # Check if lower CTR but high conversion efficiency
        # Look for platforms with above-baseline CVR/ROAS
        for sp in candidates:
            candidate = sp.candidate
            if (candidate.primary_segment and 
                candidate.primary_segment.get('value') == platform and
                candidate.pattern_type == PatternType.SEGMENT_ABOVE_BASELINE and
                candidate.metric_name in ['cvr', 'roas'] and
                _passes_quality_gates(sp)):
                # Check if CTR is not exceptionally high (or check for lower CTR)
                ctr_sp = None
                for sp_ctr in candidates:
                    cand_ctr = sp_ctr.candidate
                    if (cand_ctr.primary_segment and
                        cand_ctr.primary_segment.get('value') == platform and
                        cand_ctr.metric_name == 'ctr'):
                        ctr_sp = sp_ctr
                        break
                
                # If CTR is not above baseline or is lower, this is a conversion platform
                if ctr_sp is None or ctr_sp.candidate.pattern_type != PatternType.SEGMENT_ABOVE_BASELINE:
                    conversion_platforms.append({
                        'platform': platform,
                        'conversion_candidate': sp,
                        'ctr_candidate': ctr_sp
                    })
    
    # Match traffic platform with conversion platform
    for traffic_plat in traffic_platforms:
        for conversion_plat in conversion_platforms:
            if traffic_plat['platform'] == conversion_plat['platform']:
                continue  # Skip same platform
            
            # Found funnel role mismatch
            traffic_platform = traffic_plat['platform']
            conversion_platform = conversion_plat['platform']
            
            ctr_candidate = traffic_plat['ctr_candidate']
            conversion_candidate_traffic = traffic_plat['conversion_candidate']
            conversion_candidate_conv = conversion_plat['conversion_candidate']
            
            # Compute deltas
            ctr_delta = None
            if ctr_candidate.candidate.baseline_value is not None:
                ctr_delta = (ctr_candidate.candidate.observed_value - ctr_candidate.candidate.baseline_value) / (abs(ctr_candidate.candidate.baseline_value) + 1e-9)
            
            conversion_delta = None
            if conversion_candidate_conv.candidate.baseline_value is not None:
                conversion_delta = (conversion_candidate_conv.candidate.observed_value - conversion_candidate_conv.candidate.baseline_value) / (abs(conversion_candidate_conv.candidate.baseline_value) + 1e-9)
            
            # Use the strongest composite score
            importance_score = max(ctr_candidate.composite_score, conversion_candidate_conv.composite_score)
            confidence = min(ctr_candidate.statistical_support, conversion_candidate_conv.statistical_support)
            
            metric_name = conversion_candidate_conv.candidate.metric_name
            
            supporting_info = {
                'traffic_platform': traffic_platform,
                'conversion_platform': conversion_platform,
                'ctr_delta': ctr_delta,
                'conversion_delta': conversion_delta,
                'metric': metric_name,
                'ctr_pattern_id': ctr_candidate.candidate.pattern_id,
                'conversion_pattern_id': conversion_candidate_conv.candidate.pattern_id
            }
            
            return BusinessInsight(
                id=definition.id,
                category=definition.category,
                segment_id=f"{traffic_platform}_vs_{conversion_platform}",
                dimension='platform',
                metric=metric_name,
                observed_value=conversion_candidate_conv.candidate.observed_value,
                baseline_value=conversion_candidate_traffic.candidate.observed_value if conversion_candidate_traffic else conversion_candidate_conv.candidate.baseline_value,
                absolute_delta=conversion_candidate_conv.candidate.observed_value - (conversion_candidate_traffic.candidate.observed_value if conversion_candidate_traffic else conversion_candidate_conv.candidate.baseline_value),
                relative_delta_pct=conversion_delta * 100 if conversion_delta else 0.0,
                importance_score=importance_score,
                confidence=confidence,
                source_pattern_type='COMPOSITE',
                supporting_candidates=[str(supporting_info)] if debug else [ctr_candidate.candidate.pattern_id, conversion_candidate_conv.candidate.pattern_id]
            )
    
    return None


def _compute_audience_platform_fit(
    definition: BusinessInsightDefinition,
    candidates: List[ScoredPatternCandidate],
    dataframe: Optional[pd.DataFrame],
    debug: bool
) -> Optional[BusinessInsight]:
    """Compute audience_platform_fit: same audience performs differently across platforms."""
    
    if dataframe is None:
        return None
    
    # Need platform and an audience dimension (campaign, device, or custom audience column)
    if 'platform' not in dataframe.columns:
        return None
    
    # Find audience dimensions (exclude platform, date, metrics)
    metric_cols = ['spend', 'revenue', 'roas', 'cpc', 'cpa', 'ctr', 'cvr', 'conversions', 'clicks', 'impressions']
    time_cols = ['date', 'day', 'hour', 'week', 'month', 'weekday']
    audience_dimensions = [col for col in dataframe.columns 
                          if col not in ['platform'] + metric_cols + time_cols]
    
    if not audience_dimensions:
        return None
    
    # For each audience dimension, check platform differences
    for audience_dim in audience_dimensions:
        audience_values = dataframe[audience_dim].dropna().unique()
        
        for audience_value in audience_values:
            audience_df = dataframe[dataframe[audience_dim] == audience_value]
            platforms = audience_df['platform'].unique()
            
            if len(platforms) < 2:
                continue
            
            # Find candidates for this audience across platforms
            platform_performance = {}
            
            for platform in platforms:
                platform_audience_df = audience_df[audience_df['platform'] == platform]
                
                # Find ROAS or CVR candidates for this audience+platform combination
                for sp in candidates:
                    candidate = sp.candidate
                    if (candidate.metric_name in ['roas', 'cvr'] and
                        candidate.primary_segment and
                        candidate.primary_segment.get('value') == platform and
                        candidate.dimensions and
                        audience_dim in candidate.dimensions and
                        candidate.dimensions[audience_dim] == audience_value and
                        sp.effect_size > 0.05 and
                        _passes_quality_gates(sp)):
                        platform_performance[platform] = {
                            'candidate': sp,
                            'value': candidate.observed_value,
                            'baseline': candidate.baseline_value,
                            'effect_size': sp.effect_size,
                            'metric': candidate.metric_name
                        }
                        break
            
            if len(platform_performance) < 2:
                continue
            
            # Find strongest and weakest platform
            platforms_sorted = sorted(platform_performance.items(), 
                                    key=lambda x: x[1]['effect_size'], 
                                    reverse=True)
            
            strong_platform_data = platforms_sorted[0]
            weak_platform_data = platforms_sorted[-1]
            
            strong_platform = strong_platform_data[0]
            weak_platform = weak_platform_data[0]
            
            if strong_platform == weak_platform:
                continue
            
            # Check spend imbalance (should not be extreme)
            strong_spend = audience_df[audience_df['platform'] == strong_platform]['spend'].sum() if 'spend' in audience_df.columns else 0
            weak_spend = audience_df[audience_df['platform'] == weak_platform]['spend'].sum() if 'spend' in audience_df.columns else 0
            total_spend = audience_df['spend'].sum() if 'spend' in audience_df.columns else 1
            
            if total_spend > 0:
                strong_spend_share = strong_spend / total_spend
                weak_spend_share = weak_spend / total_spend
                
                # Check for extreme imbalance (one platform > 80% or < 20%)
                if strong_spend_share > 0.80 or strong_spend_share < 0.20:
                    continue
                if weak_spend_share > 0.80 or weak_spend_share < 0.20:
                    continue
            
            # Found audience platform fit
            strong_perf = strong_platform_data[1]
            weak_perf = weak_platform_data[1]
            
            metric_name = strong_perf['metric']
            strong_value = strong_perf['value']
            weak_value = weak_perf['value']
            
            if strong_perf['baseline'] is not None and abs(strong_perf['baseline']) > 1e-9:
                relative_delta = (strong_value - weak_value) / abs(strong_perf['baseline'])
            else:
                relative_delta = (strong_value - weak_value) / (abs(weak_value) + 1e-9)
            
            importance_score = max(strong_perf['candidate'].composite_score, weak_perf['candidate'].composite_score)
            confidence = min(strong_perf['candidate'].statistical_support, weak_perf['candidate'].statistical_support)
            
            supporting_info = {
                'audience_segment': str(audience_value),
                'audience_dimension': audience_dim,
                'strong_platform': strong_platform,
                'weak_platform': weak_platform,
                'metric': metric_name,
                'relative_delta': relative_delta,
                'strong_effect_size': strong_perf['effect_size'],
                'weak_effect_size': weak_perf['effect_size']
            }
            
            return BusinessInsight(
                id=definition.id,
                category=definition.category,
                segment_id=f"{audience_value}_{strong_platform}_vs_{weak_platform}",
                dimension=audience_dim,
                metric=metric_name,
                observed_value=strong_value,
                baseline_value=weak_value,
                absolute_delta=strong_value - weak_value,
                relative_delta_pct=relative_delta * 100,
                importance_score=importance_score,
                confidence=confidence,
            source_pattern_type='COMPOSITE',
            supporting_candidates=[str(supporting_info)] if debug else [strong_perf['candidate'].candidate.pattern_id, weak_perf['candidate'].candidate.pattern_id]
        )
    
    return None


def _compute_month_over_month_narrative(
    definition: BusinessInsightDefinition,
    candidates: List[ScoredPatternCandidate],
    dataframe: Optional[pd.DataFrame],
    debug: bool
) -> Optional[BusinessInsight]:
    """Compute month_over_month_narrative: structural performance shift month over month."""
    
    if dataframe is None:
        return None
    
    # Need date column to group by month
    if 'date' not in dataframe.columns:
        return None
    
    try:
        dataframe['month'] = pd.to_datetime(dataframe['date']).dt.to_period('M').astype(str)
    except:
        return None
    
    months = dataframe['month'].unique()
    if len(months) < 2:
        return None
    
    # Sort months chronologically
    months_sorted = sorted(months)
    
    # Check for TEMPORAL_CHANGE candidates on revenue, roas, or conversions
    temporal_candidates = []
    for sp in candidates:
        candidate = sp.candidate
        if (candidate.pattern_type == PatternType.TEMPORAL_CHANGE and
            candidate.metric_name in ['revenue', 'roas', 'conversions'] and
            sp.effect_size > 0.05 and
            _passes_quality_gates(sp) and
            candidate.time_period is not None):
            temporal_candidates.append(sp)
    
    if len(temporal_candidates) < 2:
        return None
    
    # Group by metric and check for consistent direction
    metrics_direction = {}  # metric -> direction (1 for increase, -1 for decrease)
    
    for sp in temporal_candidates:
        candidate = sp.candidate
        metric = candidate.metric_name
        
        if candidate.baseline_value is None:
            continue
        
        direction = 1 if candidate.observed_value > candidate.baseline_value else -1
        
        if metric not in metrics_direction:
            metrics_direction[metric] = []
        metrics_direction[metric].append({
            'direction': direction,
            'candidate': sp,
            'relative_delta': (candidate.observed_value - candidate.baseline_value) / (abs(candidate.baseline_value) + 1e-9)
        })
    
    # Find metrics with consistent direction across at least 2 metrics
    consistent_metrics = []
    for metric, directions_list in metrics_direction.items():
        if len(directions_list) >= 1:  # At least one candidate
            # Check if direction is consistent
            unique_directions = set(d['direction'] for d in directions_list)
            if len(unique_directions) == 1:  # All same direction
                consistent_metrics.extend(directions_list)
    
    if len(consistent_metrics) < 2:
        return None
    
    # Get month information from time_period
    month1 = None
    month2 = None
    
    # Try to extract months from time_period
    for sp in temporal_candidates:
        candidate = sp.candidate
        if candidate.time_period:
            start = candidate.time_period.get('start')
            end = candidate.time_period.get('end')
            if start and end:
                try:
                    start_month = pd.to_datetime(start).to_period('M').strftime('%Y-%m')
                    end_month = pd.to_datetime(end).to_period('M').strftime('%Y-%m')
                    if start_month != end_month:
                        month1 = start_month
                        month2 = end_month
                        break
                except:
                    pass
    
    # Fallback: use first two months from dataframe
    if month1 is None or month2 is None:
        month1 = months_sorted[0]
        month2 = months_sorted[-1]
    
    # Get best candidate (highest composite_score)
    best_candidate = max(consistent_metrics, key=lambda x: x['candidate'].composite_score)
    sp_best = best_candidate['candidate']
    candidate_best = sp_best.candidate
    
    direction_str = "increase" if best_candidate['direction'] == 1 else "decrease"
    metrics_involved = list(set(m['candidate'].candidate.metric_name for m in consistent_metrics))
    
    importance_score = max(m['candidate'].composite_score for m in consistent_metrics)
    confidence = min(m['candidate'].statistical_support for m in consistent_metrics)
    
    relative_delta = best_candidate['relative_delta']
    
    supporting_info = {
        'month1': month1,
        'month2': month2,
        'metrics_involved': metrics_involved,
        'direction': direction_str,
        'relative_delta': relative_delta,
        'pattern_ids': [m['candidate'].candidate.pattern_id for m in consistent_metrics]
    }
    
    return BusinessInsight(
        id=definition.id,
        category=definition.category,
        segment_id=f"{month1}_to_{month2}",
        dimension='date',
        metric=candidate_best.metric_name,
        observed_value=candidate_best.observed_value,
        baseline_value=candidate_best.baseline_value,
        absolute_delta=candidate_best.observed_value - candidate_best.baseline_value,
        relative_delta_pct=relative_delta * 100,
        importance_score=importance_score,
        confidence=confidence,
        source_pattern_type='TEMPORAL_CHANGE',
        supporting_candidates=[str(supporting_info)] if debug else [m['candidate'].candidate.pattern_id for m in consistent_metrics]
    )


def _compute_risk_flags(
    candidates: List[ScoredPatternCandidate],
    tier2_insights: Dict[str, BusinessInsight],
    debug: bool
) -> Optional[BusinessInsight]:
    """Compute risk_flags: early warning signal when risk insights are triggered."""
    
    # Check if any of the risk insights are triggered
    risk_insight_ids = ["sustained_decline", "performance_volatility", 
                        "revenue_concentration_risk", "platform_dependency_risk"]
    
    triggered_risks = []
    for risk_id in risk_insight_ids:
        if risk_id in tier2_insights:
            triggered_risks.append(tier2_insights[risk_id])
    
    if not triggered_risks:
        return None
    
    # Use the highest importance risk as the primary signal
    primary_risk = max(triggered_risks, key=lambda x: x.importance_score)
    
    # Determine risk type
    risk_type_map = {
        "sustained_decline": "sustained_decline",
        "performance_volatility": "performance_volatility",
        "revenue_concentration_risk": "revenue_concentration",
        "platform_dependency_risk": "platform_dependency"
    }
    
    risk_type = risk_type_map.get(primary_risk.id, "unknown_risk")
    
    # Aggregate importance and confidence
    importance_score = max(r.importance_score for r in triggered_risks)
    confidence = min(r.confidence for r in triggered_risks)
    
    supporting_info = {
        'risk_type': risk_type,
        'triggered_risks': [r.id for r in triggered_risks],
        'primary_risk': primary_risk.id,
        'segment': primary_risk.segment_id,
        'metric': primary_risk.metric
    }
    
    return BusinessInsight(
        id="risk_flags",
        category="risk_monitoring",
        segment_id=primary_risk.segment_id,
        dimension=primary_risk.dimension,
        metric=primary_risk.metric,
        observed_value=primary_risk.observed_value,
        baseline_value=primary_risk.baseline_value,
        absolute_delta=primary_risk.absolute_delta,
        relative_delta_pct=primary_risk.relative_delta_pct,
        importance_score=importance_score,
        confidence=confidence,
        source_pattern_type='RISK_FLAG',
        supporting_candidates=[str(supporting_info)] if debug else [r.id for r in triggered_risks]
    )
