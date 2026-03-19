"""Output formatting for scored pattern candidates."""

import numpy as np
from typing import List, Dict
from ..models.insight import ScoredPatternCandidate
from .quality_gated_selector import select_quality_gated_insights, SelectionResult
from .selection_utils import extract_segment_id
from ..insight.insight_builder import build_insights
from ..insight.insight_formatter import format_insights as format_insights_display, format_insights_json as format_insights_json_display
from ..business_insights.mapper import map_candidates_to_business_insights
from ..business_insights.formatter import format_business_insights, format_business_insights_json


def _compute_support_stats(scored_patterns: List[ScoredPatternCandidate]) -> Dict:
    """Compute statistical_support distribution statistics."""
    if not scored_patterns:
        return {
            'min': 0.0,
            'max': 0.0,
            'mean': 0.0,
            'std': 0.0,
            'histogram': {}
        }
    
    support_values = [sp.statistical_support for sp in scored_patterns]
    
    # Compute statistics
    min_support = min(support_values)
    max_support = max(support_values)
    mean_support = np.mean(support_values)
    std_support = np.std(support_values) if len(support_values) > 1 else 0.0
    
    # Compute histogram (buckets: 0.0-0.1, 0.1-0.2, ..., 0.9-1.0)
    histogram = {}
    for i in range(10):
        bucket_start = i * 0.1
        bucket_end = (i + 1) * 0.1
        bucket_key = f"{bucket_start:.1f}-{bucket_end:.1f}"
        
        # Count values in this bucket
        # For most buckets: [start, end), for last bucket: [0.9, 1.0] (inclusive)
        if i == 9:
            # Last bucket includes 1.0
            count = sum(1 for v in support_values if bucket_start <= v <= bucket_end)
        else:
            # Other buckets: [start, end)
            count = sum(1 for v in support_values if bucket_start <= v < bucket_end)
        
        histogram[bucket_key] = count
    
    return {
        'min': min_support,
        'max': max_support,
        'mean': mean_support,
        'std': std_support,
        'histogram': histogram
    }


def format_scored_patterns(scored_patterns: List[ScoredPatternCandidate], top_n: int = 4, use_business_insights: bool = True, dataframe=None) -> str:
    """Format scored pattern candidates as Business Insights (Hebrew) or generic Insights."""
    if not scored_patterns:
        return "No patterns found."
    
    # Compute statistical_support debug stats (before selection)
    support_stats = _compute_support_stats(scored_patterns)
    
    # Apply quality-gated selection (with diversity constraints) - with debug mode
    selection_result = select_quality_gated_insights(scored_patterns, target_n=top_n, debug=True)
    
    total_count = len(scored_patterns)
    
    # Format output: debug stats + selection summary + insights
    lines = []
    lines.append(f"\n{'='*80}")
    
    # Debug stats for statistical_support
    lines.append("Statistical Support Distribution (Debug Stats)")
    lines.append(f"  Min: {support_stats['min']:.6f}")
    lines.append(f"  Max: {support_stats['max']:.6f}")
    lines.append(f"  Mean: {support_stats['mean']:.6f}")
    lines.append(f"  Std: {support_stats['std']:.6f}")
    lines.append("  Histogram:")
    for bucket, count in support_stats['histogram'].items():
        lines.append(f"    {bucket}: {count}")
    
    lines.append("")
    
    # Selection debug summary
    lines.append("Selection Debug Summary")
    lines.append(f"  Total candidates considered: {selection_result.total_considered}")
    lines.append(f"  Rejected by composite_score: {selection_result.rejected_by_composite}")
    lines.append(f"  Rejected by statistical_support: {selection_result.rejected_by_support}")
    lines.append(f"  Rejected by effect_size: {selection_result.rejected_by_effect}")
    lines.append(f"  Rejected by segment_dup: {selection_result.rejected_by_segment_dup}")
    lines.append(f"  Rejected by diversity_conflict: {selection_result.rejected_by_diversity_conflict}")
    
    # Show selection per stage if available
    if selection_result.selected_per_stage:
        lines.append("  Selected per stage:")
        for stage, count in sorted(selection_result.selected_per_stage.items()):
            if count > 0:
                stage_name = {
                    0: "Stage 0 (strict: 1/metric, 1/dimension)",
                    1: "Stage 1 (relaxed metric: 2/metric)",
                    2: "Stage 2 (relaxed dimension: 2/dimension)",
                    3: "Stage 3 (final: no metric/dimension caps)"
                }.get(stage, f"Stage {stage}")
                lines.append(f"    {stage_name}: {count}")
    lines.append("")
    
    # Top 5 quality-gate-only rejections
    if selection_result.quality_gate_only_rejections:
        lines.append("Top 5 Candidates Rejected Only by Quality Gates:")
        for i, rejection in enumerate(selection_result.quality_gate_only_rejections, 1):
            sp = rejection.candidate
            segment_id = extract_segment_id(sp.candidate)
            lines.append(f"  {i}. {sp.candidate.metric_name} | {segment_id}")
            lines.append(f"     composite_score: {sp.composite_score:.4f} | support: {sp.statistical_support:.4f} | effect_size: {sp.effect_size:.4f}")
            lines.append(f"     Failed gate: {rejection.failed_gate}")
        lines.append("")
    
    # Use business insights (default) or generic insights
    if use_business_insights:
        # Map to business insights
        # Pass two-stage ranked pool BEFORE diversity selection (mapper applies quality gates itself)
        business_insights, debug_meta = map_candidates_to_business_insights(
            scored_patterns,  # Two-stage ranked pool (before diversity selection)
            top_n=top_n,
            debug=True,
            dataframe=dataframe  # Pass dataframe for Tier 2 share calculations
        )
        
        # Format business insights (structured English output)
        insights_text = format_business_insights(business_insights, target_n=top_n, debug_meta=debug_meta)
        lines.append(insights_text)
    else:
        # Fallback to generic insights
        insights = build_insights(selection_result.selected)
        insights_text = format_insights_display(insights, target_n=top_n, selection_result=selection_result)
        lines.append(insights_text)
    
    return "\n".join(lines)


def format_scored_patterns_json(scored_patterns: List[ScoredPatternCandidate], use_business_insights: bool = True, dataframe=None, analysis_mode: str = "full") -> List[dict]:
    """Format scored pattern candidates as JSON-serializable list (quality-gated)."""
    # Use business insights (default) or generic insights
    if use_business_insights:
        # Map to business insights (pass two-stage ranked pool, mapper applies quality gates)
        business_insights, _ = map_candidates_to_business_insights(
            scored_patterns,  # Two-stage ranked pool (before diversity selection)
            top_n=4,
            debug=False,
            dataframe=dataframe,  # Pass dataframe for Tier 2 share calculations
            analysis_mode=analysis_mode  # Pass analysis mode to filter revenue/ROAS insights
        )
        # Format business insights as JSON
        return format_business_insights_json(business_insights)
    else:
        # Fallback to generic insights (apply quality-gated selection)
        selection_result = select_quality_gated_insights(scored_patterns, target_n=4, debug=False)
        insights = build_insights(selection_result.selected)
        return format_insights_json_display(insights)
