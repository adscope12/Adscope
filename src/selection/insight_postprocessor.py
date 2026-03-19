"""
Insight Post-Processing Layer

This module handles post-processing of insights after generation:
- Theme deduplication
- Dataset size validation
- Evidence enhancement
"""

from typing import Dict, Any, List, Tuple, Optional
import re


def extract_insight_theme(insight: Dict[str, Any]) -> str:
    """
    Extract a simple theme label from an insight based on keywords and pattern type.
    
    Themes:
    - platform_performance
    - device_performance
    - campaign_performance
    - budget_allocation
    - conversion_efficiency
    - temporal_trend
    - traffic_imbalance
    
    Args:
        insight: Insight dict with title, summary, or pattern metadata
        
    Returns:
        Theme label string
    """
    # Get text to analyze - combine all available text fields
    title = insight.get("title", "").lower()
    summary = insight.get("summary", "").lower()
    issue = insight.get("issue_opportunity", "").lower()
    why = insight.get("why_it_matters", "").lower()
    impact = insight.get("expected_impact", "").lower()
    
    combined_text = f"{title} {summary} {issue} {why} {impact}".lower()
    
    # Platform performance theme (highest priority check)
    # Matches: "increase investment in Google", "focus on Google", "Google platform", etc.
    platform_keywords = ["platform", "google", "facebook", "meta", "channel", "ad network"]
    platform_action_keywords = ["increase", "investment", "focus", "enhance", "improve", "optimize", 
                                "underperform", "overperform", "better", "worse", "efficiency", 
                                "performance", "revenue", "spend", "allocation"]
    
    if any(pkw in combined_text for pkw in platform_keywords):
        if any(akw in combined_text for akw in platform_action_keywords):
            return "platform_performance"
    
    # Device performance theme
    device_keywords = ["device", "mobile", "desktop", "tablet", "ios", "android"]
    device_action_keywords = ["underperform", "overperform", "performance", "efficiency", 
                             "better", "worse", "optimize", "improve"]
    
    if any(dkw in combined_text for dkw in device_keywords):
        if any(akw in combined_text for akw in device_action_keywords):
            return "device_performance"
    
    # Campaign performance theme
    campaign_keywords = ["campaign", "ad group", "adgroup"]
    campaign_action_keywords = ["underperform", "overperform", "performance", "winning", 
                               "losing", "optimize", "improve"]
    
    if any(ckw in combined_text for ckw in campaign_keywords):
        if any(akw in combined_text for akw in campaign_action_keywords):
            return "campaign_performance"
    
    # Budget allocation theme
    budget_keywords = ["budget", "spend", "allocation", "investment", "cost", "media cost"]
    if any(bkw in combined_text for bkw in budget_keywords):
        return "budget_allocation"
    
    # Conversion efficiency theme
    conversion_keywords = ["conversion", "cvr", "conversion rate", "efficiency", "rate"]
    conversion_action_keywords = ["low", "poor", "underperform", "inefficient", "worse", 
                                 "improve", "optimize", "enhance"]
    
    if any(ckw in combined_text for ckw in conversion_keywords):
        if any(akw in combined_text for akw in conversion_action_keywords):
            return "conversion_efficiency"
    
    # Traffic imbalance theme
    traffic_keywords = ["traffic", "impression", "click share", "volume", "distribution", "clicks"]
    traffic_action_keywords = ["imbalance", "uneven", "disproportionate", "skewed", "distribution"]
    
    if any(tkw in combined_text for tkw in traffic_keywords):
        if any(akw in combined_text for akw in traffic_action_keywords):
            return "traffic_imbalance"
    
    # Temporal trend theme
    temporal_keywords = ["weekend", "weekday", "day", "time", "temporal", "trend", "season", 
                        "decline", "recovery", "pattern"]
    if any(tkw in combined_text for tkw in temporal_keywords):
        return "temporal_trend"
    
    # Default: use first significant word or "general"
    if title:
        # Extract first meaningful word
        words = title.split()
        if words:
            return f"general_{words[0]}"
    
    return "general"


def deduplicate_insights_by_theme(
    insights: List[Dict[str, Any]],
    score_key: str = "validation_score",
    max_insights: int = 4
) -> List[Dict[str, Any]]:
    """
    Deduplicate insights by theme, keeping only the highest-scoring insight per theme.
    Then limit to top N insights overall.
    
    Args:
        insights: List of insight dictionaries
        score_key: Key to use for scoring (default: "validation_score")
                  Falls back to "composite_score" if validation_score not available
        max_insights: Maximum number of insights to return after deduplication (default: 4)
                  
    Returns:
        Deduplicated list of insights (max 1 per theme, then top N overall)
    """
    if not insights:
        return []
    
    # Group insights by theme
    themes: Dict[str, List[Tuple[Dict[str, Any], float]]] = {}
    
    for insight in insights:
        theme = extract_insight_theme(insight)
        
        # Get score (prefer validation_score, fallback to composite_score)
        score = insight.get(score_key)
        if score is None:
            score = insight.get("composite_score", 0.0)
        
        # Ensure score is a float
        try:
            score = float(score)
        except (ValueError, TypeError):
            score = 0.0
        
        if theme not in themes:
            themes[theme] = []
        
        themes[theme].append((insight, score))
    
    # For each theme, keep only the highest-scoring insight
    deduplicated = []
    for theme, theme_insights in themes.items():
        # Sort by score (descending)
        theme_insights.sort(key=lambda x: x[1], reverse=True)
        # Keep only the top one
        best_insight, best_score = theme_insights[0]
        # Store the score in the insight for final sorting
        best_insight["_dedup_score"] = best_score
        deduplicated.append(best_insight)
    
    # Sort deduplicated insights by score (descending) to maintain priority order
    deduplicated.sort(
        key=lambda x: x.get("_dedup_score", x.get(score_key) or x.get("composite_score", 0.0)),
        reverse=True
    )
    
    # Limit to top N insights
    if max_insights > 0:
        deduplicated = deduplicated[:max_insights]
    
    # Clean up temporary score field
    for insight in deduplicated:
        insight.pop("_dedup_score", None)
    
    return deduplicated


def validate_dataset_size(row_count: int) -> Tuple[bool, Optional[str], int]:
    """
    Validate dataset size and determine insight limits.
    
    Args:
        row_count: Number of rows in the dataset
        
    Returns:
        Tuple of:
        - allow_insights: bool (False if dataset too small)
        - message: Optional error message
        - max_insights: Maximum number of insights to return (0 if too small)
    """
    if row_count < 5:
        return False, "No strong insights detected in this dataset.", 0
    
    if row_count < 8:
        return True, None, 1  # Limit to 1 insight for small datasets
    
    return True, None, 4  # Normal limit


def inject_evidence_into_summary(
    summary: str,
    pattern_data: Optional[Dict[str, Any]] = None
) -> str:
    """
    Enhance insight summary with evidence from pattern data.
    
    Args:
        summary: Original summary text
        pattern_data: Optional pattern data dict with metrics
        
    Returns:
        Enhanced summary with evidence if available
    """
    if not pattern_data:
        return summary
    
    # Extract available metrics
    observed_value = pattern_data.get("observed_value")
    baseline_value = pattern_data.get("baseline_value")
    effect_size = pattern_data.get("effect_size")
    metric_name = pattern_data.get("metric", "")
    primary_segment = pattern_data.get("primary_segment", {})
    
    # If summary already contains numbers, don't duplicate
    if re.search(r'\d+', summary):
        return summary
    
    # Try to inject evidence based on available data
    evidence_parts = []
    
    # Add effect size if significant
    if effect_size is not None and abs(effect_size) > 0.1:
        if effect_size > 0:
            evidence_parts.append(f"effect size of {effect_size:.2f}")
        else:
            evidence_parts.append(f"effect size of {abs(effect_size):.2f}")
    
    # Add observed vs baseline comparison if available
    if observed_value is not None and baseline_value is not None:
        if metric_name:
            diff = observed_value - baseline_value
            if abs(diff) > 0.01:  # Significant difference
                if diff > 0:
                    evidence_parts.append(f"{metric_name} is {diff:.2f} higher than baseline")
                else:
                    evidence_parts.append(f"{metric_name} is {abs(diff):.2f} lower than baseline")
    
    # Add segment info if available
    if primary_segment:
        segment_info = []
        for key, value in primary_segment.items():
            if key not in ["metrics", "sample_size"] and value:
                segment_info.append(f"{key}: {value}")
        if segment_info:
            evidence_parts.append(f"in {', '.join(segment_info)}")
    
    # If we have evidence, append it to summary
    if evidence_parts:
        evidence_text = ", ".join(evidence_parts)
        # Append evidence if summary doesn't already end with punctuation
        if summary and not summary.rstrip().endswith(('.', '!', '?')):
            return f"{summary}. Evidence: {evidence_text}."
        else:
            return f"{summary} Evidence: {evidence_text}."
    
    return summary
