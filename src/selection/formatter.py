"""Output formatting for insights."""

from typing import List
from ..models.insight import RankedInsight


def format_insights(ranked_insights: List[RankedInsight]) -> str:
    """Format ranked insights for display (human-readable summaries)."""
    if not ranked_insights:
        return "No insights found."
    
    lines = []
    lines.append(f"\n{'='*80}")
    lines.append(f"Top {len(ranked_insights)} Marketing Insights")
    lines.append(f"{'='*80}\n")
    
    for i, insight in enumerate(ranked_insights, 1):
        lines.append(f"{i}. {insight.pattern_type.value}")
        lines.append(f"   Dimension: {insight.involved_dimension}")
        lines.append(f"   Metric: {insight.metric}")
        lines.append(f"   What Happened: {insight.what_happened}")
        lines.append(f"   Evidence: {insight.evidence}")
        value_line = f"   Values: Observed={insight.observed_value:.4f}"
        if insight.baseline_value is not None:
            value_line += f", Baseline={insight.baseline_value:.4f}"
        lines.append(value_line)
        lines.append(f"   Scores: effect_size={insight.effect_size:.4f}, impact={insight.impact_weight:.4f}, support={insight.statistical_support:.4f}, composite={insight.composite_score:.4f}")
        lines.append("")
    
    return "\n".join(lines)


def format_insights_json(ranked_insights: List[RankedInsight]) -> List[dict]:
    """Format ranked insights as JSON-serializable list."""
    return [
        {
            'pattern_type': insight.pattern_type.value,
            'involved_dimension': insight.involved_dimension,
            'metric': insight.metric,
            'observed_value': insight.observed_value,
            'baseline_value': insight.baseline_value,
            'effect_size': insight.effect_size,
            'impact_weight': insight.impact_weight,
            'statistical_support': insight.statistical_support,
            'composite_score': insight.composite_score,
            'what_happened': insight.what_happened,
            'evidence': insight.evidence
        }
        for insight in ranked_insights
    ]
