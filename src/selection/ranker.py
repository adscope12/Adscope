"""Ranking and selection logic."""

from typing import List
from ..models.insight import ScoredInsight, RankedInsight


def select_top_insights(scored_insights: List[ScoredInsight], top_n: int = 4) -> List[RankedInsight]:
    """
    Select top N insights by composite score with diversity.
    
    Ensures insights aren't duplicates of the same metric/pattern combination.
    Returns top 3-4 insights (default 4, but will return fewer if fewer available).
    """
    # Filter out zero-score insights
    valid_insights = [si for si in scored_insights if si.composite_score > 0]
    
    # Sort by composite score (descending)
    sorted_insights = sorted(valid_insights, key=lambda x: x.composite_score, reverse=True)
    
    # Select top N with diversity (avoid duplicate metric/pattern combinations)
    selected = []
    seen_combinations = set()
    
    for si in sorted_insights:
        if len(selected) >= top_n:
            break
        
        candidate = si.candidate
        # Create unique key: pattern_type + metric
        combination_key = (candidate.pattern_type, candidate.metric_name)
        
        if combination_key not in seen_combinations:
            selected.append(si)
            seen_combinations.add(combination_key)
    
    top_insights = selected
    
    # Convert to RankedInsight format (Insight = human-readable summary)
    ranked = []
    for si in top_insights:
        candidate = si.candidate
        
        # Determine involved dimension
        involved_dimension = "unknown"
        if candidate.dimensions:
            involved_dimension = list(candidate.dimensions.keys())[0]
        if candidate.time_period:
            involved_dimension = "time"
        
        # Generate "what_happened" and "evidence" from pattern
        what_happened, evidence = _generate_insight_text(candidate, si)
        
        ranked.append(RankedInsight(
            pattern_type=candidate.pattern_type,
            involved_dimension=involved_dimension,
            metric=candidate.metric_name,
            observed_value=candidate.observed_value,
            baseline_value=candidate.baseline_value,
            effect_size=si.effect_size,
            impact_weight=si.business_impact,
            statistical_support=si.statistical_support,
            composite_score=si.composite_score,
            what_happened=what_happened,
            evidence=evidence
        ))
    
    return ranked


def _generate_insight_text(candidate, scored_insight):
    """Generate human-readable 'what_happened' and 'evidence' from pattern."""
    pattern_type = candidate.pattern_type
    metric = candidate.metric_name
    observed = candidate.observed_value
    baseline = candidate.baseline_value
    dimension = list(candidate.dimensions.keys())[0] if candidate.dimensions else "unknown"
    segment_value = list(candidate.dimensions.values())[0] if candidate.dimensions else "unknown"
    
    from ..candidate_generation.pattern_types import PatternType
    
    if pattern_type == PatternType.SEGMENT_ABOVE_BASELINE:
        pct_diff = ((observed - baseline) / baseline * 100) if baseline != 0 and baseline is not None else 0
        what_happened = f"{dimension.capitalize()} '{segment_value}' {metric.upper()} is {pct_diff:+.1f}% above baseline"
        evidence = f"{metric.upper()}: {observed:.2f} vs baseline {baseline:.2f if baseline is not None else 'N/A'} (effect size: {scored_insight.effect_size:.2f})"
    
    elif pattern_type == PatternType.SEGMENT_BELOW_BASELINE:
        pct_diff = ((observed - baseline) / baseline * 100) if baseline != 0 and baseline is not None else 0
        what_happened = f"{dimension.capitalize()} '{segment_value}' {metric.upper()} is {pct_diff:+.1f}% below baseline"
        evidence = f"{metric.upper()}: {observed:.2f} vs baseline {baseline:.2f if baseline is not None else 'N/A'} (effect size: {scored_insight.effect_size:.2f})"
    
    elif pattern_type == PatternType.SEGMENT_GAP:
        if candidate.comparison_segment:
            comparison_val = candidate.comparison_segment.get('metrics', {}).get(metric, baseline)
            gap_pct = ((observed - comparison_val) / comparison_val * 100) if comparison_val != 0 else 0
            top_seg = segment_value
            bottom_seg = candidate.comparison_segment.get('value', 'other')
            what_happened = f"{dimension.capitalize()} gap: '{top_seg}' {metric.upper()} {gap_pct:+.1f}% vs '{bottom_seg}'"
            evidence = f"Top: {observed:.2f}, Bottom: {comparison_val:.2f} (gap effect: {scored_insight.effect_size:.2f})"
        else:
            what_happened = f"{dimension.capitalize()} shows significant {metric.upper()} variation"
            evidence = f"Observed: {observed:.2f}, Baseline: {baseline:.2f}"
    
    elif pattern_type == PatternType.TEMPORAL_CHANGE:
        if baseline is not None:
            pct_change = ((observed - baseline) / baseline * 100) if baseline != 0 else 0
            what_happened = f"{metric.upper()} changed {pct_change:+.1f}% between time periods"
            evidence = f"Latest period: {observed:.2f}, Previous period: {baseline:.2f} (temporal effect: {scored_insight.effect_size:.2f})"
        else:
            what_happened = f"{metric.upper()} shows temporal variation"
            evidence = f"Observed: {observed:.2f}"
    
    elif pattern_type == PatternType.METRIC_IMBALANCE:
        if baseline is not None:
            ratio_diff = ((observed - baseline) / baseline * 100) if baseline != 0 else 0
            what_happened = f"{dimension.capitalize()} '{segment_value}' shows spend/revenue ratio {ratio_diff:+.1f}% vs baseline"
            evidence = f"Ratio: {observed:.2f} vs baseline {baseline:.2f} (imbalance effect: {scored_insight.effect_size:.2f})"
        else:
            what_happened = f"{dimension.capitalize()} '{segment_value}' shows metric imbalance"
            evidence = f"Observed ratio: {observed:.2f}"
    
    else:
        what_happened = f"Pattern detected in {metric.upper()}"
        evidence = f"Observed: {observed:.2f}, Baseline: {baseline:.2f if baseline else 'N/A'}"
    
    return what_happened, evidence
