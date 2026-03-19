"""Format Insight objects for CLI display."""

from typing import List
from .insight_builder import Insight


def format_insights(insights: List[Insight], target_n: int = 4, selection_result=None) -> str:
    """Format insights for display."""
    if not insights:
        return "No insights found."
    
    lines = []
    lines.append(f"\n{'='*80}")
    lines.append(f"Top {len(insights)} Marketing Insights (Quality-gated)")
    if len(insights) < target_n:
        # Determine the main reason for fewer insights
        if selection_result:
            quality_rejections = (
                selection_result.rejected_by_composite +
                selection_result.rejected_by_support +
                selection_result.rejected_by_effect
            )
            diversity_rejections = selection_result.rejected_by_diversity_conflict
            segment_rejections = selection_result.rejected_by_segment_dup
            
            if quality_rejections > max(diversity_rejections, segment_rejections):
                lines.append(f"Returned fewer than {target_n} because remaining candidates failed quality gates.")
            else:
                lines.append(f"Not enough eligible insights after: segment uniqueness + diversity constraints + quality gates.")
        else:
            lines.append(f"Not enough eligible insights after: segment uniqueness + diversity constraints + quality gates.")
    lines.append(f"{'='*80}\n")
    
    for i, insight in enumerate(insights, 1):
        lines.append(f"{i}. {insight.title}")
        lines.append(f"   Pattern Type: {insight.pattern_type}")
        lines.append(f"   Dimension: {insight.dimension}")
        lines.append(f"   Segment: {insight.segment_id}")
        lines.append(f"   Metric: {insight.metric}")
        lines.append(f"   Observed Value: {insight.observed_value:.4f}")
        lines.append(f"   Baseline Value: {insight.baseline_value:.4f}")
        lines.append(f"   Absolute Delta: {insight.absolute_delta:+.4f}")
        lines.append(f"   Relative Delta: {insight.relative_delta_pct:+.2f}%")
        lines.append(f"   Importance Score: {insight.importance_score:.4f}")
        lines.append(f"   Confidence: {insight.confidence:.4f}")
        lines.append(f"   Why It Matters: {insight.why_it_matters}")
        lines.append("")
    
    return "\n".join(lines)


def format_insights_json(insights: List[Insight]) -> List[dict]:
    """Format insights as JSON-serializable list."""
    return [
        {
            'title': insight.title,
            'pattern_type': insight.pattern_type,
            'dimension': insight.dimension,
            'segment_id': insight.segment_id,
            'metric': insight.metric,
            'observed_value': insight.observed_value,
            'baseline_value': insight.baseline_value,
            'absolute_delta': insight.absolute_delta,
            'relative_delta_pct': insight.relative_delta_pct,
            'importance_score': insight.importance_score,
            'confidence': insight.confidence,
            'why_it_matters': insight.why_it_matters
        }
        for insight in insights
    ]
