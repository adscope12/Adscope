"""
Grounded Narrative Layer - Structured Insight Payload Builder.

This module builds structured, deterministic payloads from scored insights
to constrain LLM phrasing to only use detected facts.
"""

from typing import Dict, Any, List, Optional
from ..models.insight import ScoredPatternCandidate
from ..candidate_generation.pattern_types import PatternType


def _format_date_only(value: Any) -> Optional[str]:
    """
    Format a date-like value as YYYY-MM-DD (no time component).
    """
    if value is None:
        return None
    try:
        import pandas as pd
        ts = pd.to_datetime(value)
        if pd.isna(ts):
            return None
        return ts.date().isoformat()
    except Exception:
        # If parsing fails, fall back to string without changing content
        s = str(value).strip()
        return s or None


def _format_time_period(time_period: Any) -> Optional[Dict[str, Any]]:
    """
    Ensure time_period is rendered cleanly:
    - single date => start=end=YYYY-MM-DD
    - range => YYYY-MM-DD to YYYY-MM-DD
    - never include 00:00:00
    """
    if not time_period:
        return None
    if isinstance(time_period, dict):
        start = _format_date_only(time_period.get("start"))
        end = _format_date_only(time_period.get("end"))
        if start or end:
            return {"start": start, "end": end}
        return None
    # If a single value is provided, treat it as a single-day period
    d = _format_date_only(time_period)
    if d:
        return {"start": d, "end": d}
    return None


def _clean_temporal_label(text: Any) -> Optional[str]:
    """
    Clean temporal labels like:
    - '2024-01-14 00:00:00' -> '2024-01-14'
    - '2024-01-13 00:00:00 to 2024-01-14 00:00:00' -> '2024-01-13 to 2024-01-14'
    """
    if text is None:
        return None
    s = str(text).strip()
    if not s:
        return None

    if " to " in s:
        left, right = s.split(" to ", 1)
        left_fmt = _format_date_only(left)
        right_fmt = _format_date_only(right)
        if left_fmt and right_fmt:
            return f"{left_fmt} to {right_fmt}"
        # fallback
        return s.replace(" 00:00:00", "")

    # Single date/time
    only = _format_date_only(s)
    if only:
        return only
    return s.replace(" 00:00:00", "")


def build_structured_insight_payload(scored_candidate: ScoredPatternCandidate) -> Dict[str, Any]:
    """
    Build a structured insight payload from a scored candidate.
    
    This payload contains all facts that the LLM is allowed to use,
    preventing it from inventing new patterns, metrics, or segments.
    
    Args:
        scored_candidate: ScoredPatternCandidate to build payload for
        
    Returns:
        Structured payload dictionary
    """
    candidate = scored_candidate.candidate
    
    # Extract dimension and segment
    dimension = "unknown"
    segment = "unknown"
    if candidate.dimensions:
        dimension = list(candidate.dimensions.keys())[0]
        segment = str(candidate.dimensions.get(dimension, "unknown")).strip()
    
    # Extract segment from primary_segment if available (preserve original casing)
    if candidate.primary_segment:
        segment_value = candidate.primary_segment.get('value')
        if segment_value is not None:
            segment = str(segment_value).strip()

    # Clean temporal segment labels (avoid '00:00:00' in output)
    if dimension.lower() in {"date", "time"} or candidate.time_period is not None:
        cleaned = _clean_temporal_label(segment)
        if cleaned:
            segment = cleaned
    
    # Determine comparison target
    comparison_target = _determine_comparison_target(candidate)
    
    # Extract primary metric
    primary_metric = candidate.metric_name
    
    # Extract secondary metrics from raw_metrics
    secondary_metrics = _extract_secondary_metrics(candidate)
    
    # Determine direction
    direction = _determine_direction_from_pattern(candidate)
    
    # Determine safe business interpretation
    safe_business_interpretation = _determine_safe_interpretation(candidate, scored_candidate)
    
    # Determine safe action hint
    safe_action_hint = _determine_safe_action_hint(candidate, scored_candidate)
    
    # Get allowed narrative tags
    from .narrative_tags import get_narrative_tags_for_pattern
    allowed_narrative_tags = get_narrative_tags_for_pattern(
        candidate.pattern_type,
        direction,
        candidate.pattern_id
    )
    
    # Build payload
    payload = {
        "pattern_id": candidate.pattern_id,
        "pattern_type": candidate.pattern_type.value if hasattr(candidate.pattern_type, 'value') else str(candidate.pattern_type),
        "dimension": dimension,
        "segment": segment,
        "comparison_target": comparison_target,
        "primary_metric": primary_metric,
        "secondary_metrics": secondary_metrics,
        "direction": direction,
        "observed_value": candidate.observed_value,
        "baseline_value": candidate.baseline_value,
        "effect_size": scored_candidate.effect_size,
        "business_impact": scored_candidate.business_impact,
        "statistical_support": scored_candidate.statistical_support,
        "composite_score": scored_candidate.composite_score,
        "safe_business_interpretation": safe_business_interpretation,
        "safe_action_hint": safe_action_hint,
        "allowed_narrative_tags": allowed_narrative_tags,
    }
    
    # Add time period if available
    if candidate.time_period:
        payload["time_period"] = _format_time_period(candidate.time_period)
    
    return payload


def _determine_comparison_target(candidate) -> str:
    """Determine what the segment is being compared to."""
    if candidate.comparison_segment:
        comp_value = candidate.comparison_segment.get('value')
        if comp_value is not None:
            cleaned = _clean_temporal_label(comp_value)
            if cleaned:
                return cleaned
            return str(comp_value).strip()
    
    if candidate.baseline_value is not None:
        return "baseline"
    
    return "overall average"


def _extract_secondary_metrics(candidate) -> List[str]:
    """Extract secondary metrics from raw_metrics."""
    secondary = []
    
    if candidate.primary_segment:
        metrics = candidate.primary_segment.get('metrics', {})
        primary_metric = candidate.metric_name.lower()
        
        for metric_name, value in metrics.items():
            if metric_name.lower() != primary_metric and value is not None:
                secondary.append(metric_name)
    
    return secondary[:3]  # Limit to top 3 secondary metrics


def _determine_direction_from_pattern(candidate) -> str:
    """Determine direction (positive/negative) from pattern type and values."""
    metric = (candidate.metric_name or "").lower()
    is_cost_metric = metric in {"cpa", "cpc"}

    if candidate.pattern_type == PatternType.SEGMENT_ABOVE_BASELINE:
        # For cost metrics, "above baseline" is worse (higher cost)
        return "negative" if is_cost_metric else "positive"
    
    if candidate.pattern_type == PatternType.SEGMENT_BELOW_BASELINE:
        # For cost metrics, "below baseline" is better (lower cost)
        return "positive" if is_cost_metric else "negative"
    
    if candidate.pattern_type == PatternType.SEGMENT_GAP:
        if candidate.baseline_value is not None:
            if is_cost_metric:
                return "positive" if candidate.observed_value < candidate.baseline_value else "negative"
            return "positive" if candidate.observed_value > candidate.baseline_value else "negative"
        return "unknown"
    
    if candidate.pattern_type == PatternType.TEMPORAL_CHANGE:
        if candidate.baseline_value is not None:
            if is_cost_metric:
                return "positive" if candidate.observed_value < candidate.baseline_value else "negative"
            return "positive" if candidate.observed_value > candidate.baseline_value else "negative"
        return "unknown"
    
    if candidate.pattern_type == PatternType.METRIC_IMBALANCE:
        return "negative"  # Imbalance is typically negative
    
    return "unknown"


def _determine_safe_interpretation(candidate, scored_candidate) -> str:
    """Determine a safe, deterministic business interpretation."""
    direction = _determine_direction_from_pattern(candidate)
    metric = candidate.metric_name.lower()

    # Fully metric-aware interpretations (used verbatim by grounded phrasing)
    if metric == "cvr":
        return (
            "Conversion efficiency improved versus the comparison target (higher CVR)."
            if direction == "positive"
            else "Conversion efficiency worsened versus the comparison target (lower CVR)."
        )
    if metric == "roas":
        return (
            "Return on ad spend improved versus the comparison target (higher ROAS)."
            if direction == "positive"
            else "Return on ad spend worsened versus the comparison target (lower ROAS)."
        )
    if metric == "cpa":
        # NOTE: direction logic is already corrected for CPA above.
        return (
            "Acquisition cost efficiency improved versus the comparison target (lower CPA)."
            if direction == "positive"
            else "Acquisition cost efficiency worsened versus the comparison target (higher CPA)."
        )
    if metric == "revenue":
        return (
            "Business output increased versus the comparison target (higher revenue)."
            if direction == "positive"
            else "Business output decreased versus the comparison target (lower revenue)."
        )
    if metric == "conversions":
        return (
            "Outcome volume increased versus the comparison target (more conversions)."
            if direction == "positive"
            else "Outcome volume decreased versus the comparison target (fewer conversions)."
        )
    if metric == "spend":
        return (
            "Spend shifted versus the comparison target, which is primarily relevant for budget allocation context."
        )

    # Fallbacks
    if direction == "positive":
        return "This segment outperforms the comparison target."
    return "This segment underperforms the comparison target."


def _determine_safe_action_hint(candidate, scored_candidate) -> str:
    """Determine a safe, generic action hint based on pattern type."""
    dimension = "unknown"
    if candidate.dimensions:
        dimension = list(candidate.dimensions.keys())[0]

    metric = (candidate.metric_name or "").strip()
    # Try to capture comparison entity for more specific next checks (still deterministic)
    primary_val = None
    if candidate.primary_segment:
        primary_val = candidate.primary_segment.get("value")
    comparison_val = None
    if candidate.comparison_segment:
        comparison_val = candidate.comparison_segment.get("value")
    comp_label = None
    if comparison_val is not None:
        comp_label = str(comparison_val).strip()
    primary_label = None
    if primary_val is not None:
        primary_label = str(primary_val).strip()

    # Time period (formatted upstream) can be used to make temporal checks less generic
    tp = None
    if candidate.time_period and isinstance(candidate.time_period, dict):
        tp_start = _format_date_only(candidate.time_period.get("start"))
        tp_end = _format_date_only(candidate.time_period.get("end"))
        if tp_start and tp_end:
            tp = f"{tp_start} to {tp_end}" if str(tp_start) != str(tp_end) else str(tp_start)
    
    metric_lower = metric.lower()

    if dimension == "device":
        return f"Review device targeting and budget split for {metric_lower} differences."
    elif dimension == "platform":
        return f"Review platform-level budget allocation and delivery for {metric_lower} differences."
    elif dimension == "campaign":
        if primary_label and comp_label and comp_label.lower() not in {"baseline", "overall average"}:
            return f"Compare budget and settings between {primary_label} and {comp_label} for {metric} drivers."
        if primary_label:
            return f"Review {primary_label} campaign settings and {metric} performance drivers."
        return "Review campaign settings and performance metrics."
    elif dimension in ['date', 'weekend', 'weekday']:
        if tp:
            return f"Review what changed around {tp} for {metric_lower} (budget, targeting, and delivery) and validate the pattern."
        return "Review time-based performance patterns and scheduling."
    else:
        return "Review segment performance and optimization opportunities."


