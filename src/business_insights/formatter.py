"""Format BusinessInsights for CLI display - structured English output."""

from typing import List, Dict, Optional
from .registry import BusinessInsight


def format_business_insights(insights: List[BusinessInsight], target_n: int = 4, debug_meta: Dict = None) -> str:
    """Format business insights for display - structured English debug format."""
    if not insights:
        return "No business insights found."
    
    # Split insights into primary and meta
    meta_insight_ids = debug_meta.get("meta_insights", []) if debug_meta else []
    primary_insights = [insight for insight in insights if insight.id not in meta_insight_ids]
    meta_insights = [insight for insight in insights if insight.id in meta_insight_ids]
    
    lines = []
    
    # Primary insights section
    if primary_insights:
        lines.append(f"\n{'='*80}")
        lines.append(f"Top {len(primary_insights)} Business Insights (Primary)")
        if len(primary_insights) < target_n:
            lines.append(f"Returned fewer than {target_n} insights due to quality gating.")
        lines.append(f"{'='*80}\n")
        
        for i, insight in enumerate(primary_insights, 1):
            lines.append(f"{i}. Insight: {insight.id}")
            lines.append(f"   Category: {insight.category}")
            lines.append(f"   Segment: {insight.segment_id}")
            lines.append(f"   Dimension: {insight.dimension}")
            lines.append(f"   Metric: {insight.metric}")
            lines.append(f"   Observed value: {insight.observed_value:.4f}")
            lines.append(f"   Baseline value: {insight.baseline_value:.4f}")
            lines.append(f"   Absolute delta: {insight.absolute_delta:+.4f}")
            lines.append(f"   Relative delta: {insight.relative_delta_pct:+.2f}%")
            lines.append(f"   Importance score: {insight.importance_score:.4f}")
            lines.append(f"   Confidence: {insight.confidence:.4f}")
            lines.append(f"   Source pattern type: {insight.source_pattern_type}")
            if insight.supporting_candidates:
                lines.append(f"   Supporting candidates: {insight.supporting_candidates}")
            lines.append("")
    
    # Meta insights section (separate, appended last)
    if meta_insights:
        lines.append(f"\n{'='*80}")
        lines.append(f"Meta Insights (Appended)")
        lines.append(f"{'='*80}\n")
        
        for i, insight in enumerate(meta_insights, 1):
            lines.append(f"{i}. Insight: {insight.id}")
            lines.append(f"   Category: {insight.category}")
            lines.append(f"   Segment: {insight.segment_id}")
            lines.append(f"   Dimension: {insight.dimension}")
            lines.append(f"   Metric: {insight.metric}")
            lines.append(f"   Observed value: {insight.observed_value:.4f}")
            lines.append(f"   Baseline value: {insight.baseline_value:.4f}")
            lines.append(f"   Absolute delta: {insight.absolute_delta:+.4f}")
            lines.append(f"   Relative delta: {insight.relative_delta_pct:+.2f}%")
            lines.append(f"   Importance score: {insight.importance_score:.4f}")
            lines.append(f"   Confidence: {insight.confidence:.4f}")
            lines.append(f"   Source pattern type: {insight.source_pattern_type}")
            if insight.supporting_candidates:
                lines.append(f"   Supporting candidates: {insight.supporting_candidates}")
            lines.append("")
    
    # Debug info if available
    if debug_meta:
        if debug_meta.get("definitions_triggered"):
            lines.append("Debug: Definitions Triggered")
            for def_id, count in debug_meta["definitions_triggered"].items():
                lines.append(f"  {def_id}: {count} candidates matched")
            lines.append("")
        
        # Show suppressed insights if available
        if debug_meta.get("suppressed_insights"):
            lines.append("Debug: Suppressed Insights")
            for suppressed_id, suppressed_by_id in debug_meta["suppressed_insights"].items():
                lines.append(f"  {suppressed_id} suppressed by {suppressed_by_id}")
            lines.append("")
        
        # Show meta insights if available
        if debug_meta.get("meta_insights"):
            lines.append(f"Debug: Meta Insights (appended last, no diversity slot): {', '.join(debug_meta['meta_insights'])}")
            lines.append("")
        
        # Show primary vs meta counts and selection details
        if "primary_selected" in debug_meta or "meta_appended" in debug_meta:
            lines.append("Debug: Insight Selection Summary")
            lines.append(f"  Primary insights selected: {debug_meta.get('primary_selected', 0)}")
            lines.append(f"    - Tier 2 selected: {debug_meta.get('tier2_selected', 0)}")
            lines.append(f"    - Tier 1 selected: {debug_meta.get('tier1_selected', 0)}")
            lines.append(f"  Meta insights appended: {debug_meta.get('meta_appended', 0)}")
            
            if debug_meta.get('fill_required', False):
                lines.append(f"  Fill required: Yes (Tier 1 used to fill remaining slots)")
            else:
                lines.append(f"  Fill required: No")
            
            if debug_meta.get('fewer_than_4', False):
                lines.append(f"  Status: Returned fewer than 4 insights due to quality gating")
            else:
                lines.append(f"  Status: Target of 4 insights reached")
            lines.append("")
        
        # Show Tier 2 share values if available
        if debug_meta.get("tier2_insights"):
            lines.append("Debug: Tier 2 Share Values")
            for def_id, supporting_info in debug_meta["tier2_insights"].items():
                if supporting_info:
                    lines.append(f"  {def_id}: {supporting_info[0]}")
            lines.append("")
    
    return "\n".join(lines)


def format_business_insights_json(insights: List[BusinessInsight]) -> List[dict]:
    """Format business insights as JSON-serializable list."""
    return [
        {
            'id': insight.id,
            'category': insight.category,
            'segment_id': insight.segment_id,
            'dimension': insight.dimension,
            'metric': insight.metric,
            'observed_value': insight.observed_value,
            'baseline_value': insight.baseline_value,
            'absolute_delta': insight.absolute_delta,
            'relative_delta_pct': insight.relative_delta_pct,
            'importance_score': insight.importance_score,
            'confidence': insight.confidence,
            'source_pattern_type': insight.source_pattern_type,
            'supporting_candidates': insight.supporting_candidates
        }
        for insight in insights
    ]
