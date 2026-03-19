"""
Deterministic Fallback Template - Template-based phrasing when LLM fails.

Provides safe, deterministic phrasing using structured payload data.
"""

from typing import Dict, Any, Optional


def _normalize_segment(raw_segment: str) -> str:
    """
    Normalize segment text to avoid vague placeholders.
    """
    if not raw_segment:
        return "this segment"
    
    cleaned = raw_segment.strip()
    lowered = cleaned.lower()
    
    # Disallow vague placeholders
    forbidden = {"segment", "latest segment", "recent segment", "this segment"}
    if lowered in forbidden:
        return "this segment"
    
    return cleaned


def _build_headline(
    segment: str,
    comparison_target: str,
    primary_metric: str,
    direction: str,
    dimension: str,
    time_period: Optional[Dict[str, Any]],
    observed_value: float,
    baseline_value: float,
) -> str:
    """
    Build a specific, readable headline using available fields.
    """
    seg = _normalize_segment(segment)
    comp = (comparison_target or "").strip() or "baseline"
    metric = (primary_metric or "performance").strip()
    
    metric_display = metric.upper() if len(metric) <= 4 else metric.title()
    
    # Prefer segment vs comparison wording when a non-generic segment exists
    dim = (dimension or "").strip().lower()
    start = None
    end = None
    if isinstance(time_period, dict):
        start = (time_period.get("start") or "").strip() or None
        end = (time_period.get("end") or "").strip() or None

    # Date-based headlines: prefer explicit dates/ranges when available
    if start and end:
        if start == end:
            verb = "spiked" if direction == "positive" else "dropped" if direction == "negative" else "shifted"
            return f"{metric_display} {verb} on {start}"
        else:
            verb = "improved" if direction == "positive" else "declined" if direction == "negative" else "shifted"
            return f"{metric_display} {verb} from {start} to {end}"

    # Numeric framing when baseline is available and meaningful
    if baseline_value not in (None, 0):
        try:
            ratio = observed_value / baseline_value
            if ratio >= 1.5 and direction == "positive":
                return f"{metric_display} increased {ratio:.1f}x"
            if ratio <= (1 / 1.5) and direction == "negative":
                inv = baseline_value / observed_value if observed_value else 0
                if inv > 0:
                    return f"{metric_display} dropped {inv:.1f}x"
        except Exception:
            pass

    if direction == "positive":
        if seg != "this segment":
            return f"{seg} outperformed {comp} in {metric_display}"
        return f"{metric_display} outperformed {comp}"
    elif direction == "negative":
        if seg != "this segment":
            return f"{seg} underperformed {comp} in {metric_display}"
        return f"{metric_display} underperformed versus {comp}"
    else:
        if seg != "this segment":
            return f"{seg} {metric_display} differed from {comp}"
        return f"{metric_display} differed from {comp}"


def generate_fallback_phrasing(structured_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate deterministic phrasing from structured payload.
    
    Used when LLM fails or validation fails.
    
    Args:
        structured_payload: Structured insight payload
        
    Returns:
        Phrased insight with headline, what_is_happening, why_it_matters, next_check
    """
    dimension = structured_payload.get("dimension", "segment")
    segment = structured_payload.get("segment", "this segment")
    comparison_target = structured_payload.get("comparison_target", "baseline")
    primary_metric = structured_payload.get("primary_metric", "performance")
    direction = structured_payload.get("direction", "unknown")
    observed_value = structured_payload.get("observed_value", 0)
    baseline_value = structured_payload.get("baseline_value", 0)
    safe_action_hint = structured_payload.get("safe_action_hint", "Review segment performance.")
    time_period = structured_payload.get("time_period")
    
    # Generate headline (specific, avoids vague placeholders)
    headline = _build_headline(
        segment,
        comparison_target,
        primary_metric,
        direction,
        dimension,
        time_period,
        observed_value,
        baseline_value,
    )
    
    # Generate what_is_happening
    metric_display = primary_metric.upper() if len(primary_metric) <= 4 else primary_metric.title()
    
    if baseline_value is not None and baseline_value != 0:
        pct_change = abs((observed_value - baseline_value) / baseline_value * 100)
        ratio = observed_value / baseline_value if baseline_value else None
        if direction == "positive":
            if ratio and ratio >= 1.5:
                what_is_happening = (
                    f"{_normalize_segment(segment)} reached {observed_value:.2f} vs {baseline_value:.2f} "
                    f"for {comparison_target} ({ratio:.1f}x, {pct_change:.0f}% higher)."
                )
            else:
                what_is_happening = (
                    f"{_normalize_segment(segment)} reached {observed_value:.2f} vs {baseline_value:.2f} "
                    f"for {comparison_target} ({pct_change:.0f}% higher)."
                )
        else:
            if observed_value not in (None, 0) and baseline_value and baseline_value / observed_value >= 1.5:
                what_is_happening = (
                    f"{_normalize_segment(segment)} reached {observed_value:.2f} vs {baseline_value:.2f} "
                    f"for {comparison_target} ({baseline_value / observed_value:.1f}x lower, {pct_change:.0f}% decline)."
                )
            else:
                what_is_happening = (
                    f"{_normalize_segment(segment)} reached {observed_value:.2f} vs {baseline_value:.2f} "
                    f"for {comparison_target} ({pct_change:.0f}% lower)."
                )
    else:
        what_is_happening = (
            f"{_normalize_segment(segment)} shows {metric_display} of {observed_value:.2f}, "
            f"differing from {comparison_target}."
        )
    
    # Generate why_it_matters (metric-aware, less repetitive)
    metric_lower = (primary_metric or "").lower().strip()
    dim_lower = (dimension or "").lower().strip()
    comp_lower = (comparison_target or "").lower().strip()
    seg_norm = _normalize_segment(segment)

    tp_label = None
    if isinstance(time_period, dict):
        tp_start = (time_period.get("start") or "").strip()
        tp_end = (time_period.get("end") or "").strip()
        if tp_start and tp_end:
            tp_label = f"{tp_start} to {tp_end}" if tp_start != tp_end else tp_start

    if metric_lower == "cvr":
        if tp_label:
            why_it_matters = (
                f"CVR changed over {tp_label}, which affects conversion efficiency (how many clicks turn into conversions)."
            )
        elif dim_lower == "campaign" and seg_norm != "this segment" and comp_lower and comp_lower not in {"baseline", "overall average"}:
            why_it_matters = (
                f"CVR differences between {seg_norm} and {comparison_target} affect conversion efficiency and can guide budget allocation between campaigns."
            )
        else:
            why_it_matters = (
                "CVR affects conversion efficiency—how many clicks turn into conversions—and changes here can materially shift performance."
            )
    elif metric_lower == "roas":
        if tp_label:
            why_it_matters = f"ROAS moved over {tp_label}, which changes return on ad spend and can impact day-to-day budget efficiency."
        elif dim_lower == "campaign" and seg_norm != "this segment" and comp_lower and comp_lower not in {"baseline", "overall average"}:
            why_it_matters = (
                f"ROAS differences between {seg_norm} and {comparison_target} are budget-relevant—higher return typically justifies prioritizing spend."
            )
        else:
            why_it_matters = (
                "ROAS reflects return on ad spend—changes here can justify reallocating budget toward what’s working (or away from what isn’t)."
            )
    elif metric_lower == "cpa":
        if tp_label:
            why_it_matters = f"CPA shifted over {tp_label}, which changes acquisition cost efficiency and can affect scaling decisions."
        elif dim_lower == "campaign" and seg_norm != "this segment" and comp_lower and comp_lower not in {"baseline", "overall average"}:
            why_it_matters = (
                f"CPA differences between {seg_norm} and {comparison_target} change acquisition cost efficiency and can guide budget allocation."
            )
        else:
            why_it_matters = (
                "CPA reflects acquisition cost efficiency—higher CPA can reduce profitable scaling, while lower CPA can support expansion."
            )
    elif metric_lower == "revenue":
        if tp_label:
            why_it_matters = f"Revenue moved over {tp_label}, directly affecting business output and pacing decisions."
        elif dim_lower == "campaign" and seg_norm != "this segment" and comp_lower and comp_lower not in {"baseline", "overall average"}:
            why_it_matters = (
                f"Revenue differences between {seg_norm} and {comparison_target} are budget-relevant—higher output typically deserves priority."
            )
        else:
            why_it_matters = (
                "Revenue changes reflect business output—shifts here can justify reallocating budget toward higher-yield segments."
            )
    elif metric_lower == "conversions":
        if tp_label:
            why_it_matters = f"Conversions shifted over {tp_label}, affecting outcome volume and short-term performance pacing."
        elif dim_lower == "campaign" and seg_norm != "this segment" and comp_lower and comp_lower not in {"baseline", "overall average"}:
            why_it_matters = (
                f"Conversion volume differences between {seg_norm} and {comparison_target} help prioritize spend where outcomes are stronger."
            )
        else:
            why_it_matters = (
                "Conversions reflect outcome volume—changes here can signal where the business is gaining or losing sales momentum."
            )
    else:
        # Dimension-aware fallback
        if dim_lower == "campaign" and comp_lower and comp_lower not in {"baseline", "overall average"}:
            why_it_matters = (
                "Campaign comparisons are budget-relevant—differences like this help prioritize spend between campaigns."
            )
        else:
            why_it_matters = (
                "This pattern helps prioritize where to focus analysis and optimization effort."
            )
    
    # Generate next_check
    next_check = safe_action_hint
    
    return {
        "headline": headline,
        "what_is_happening": what_is_happening,
        "why_it_matters": why_it_matters,
        "next_check": next_check
    }
