"""
Strategic output formatting for user-facing results.

This module formats Strategic LLM output into clean, user-facing results
without exposing internal IDs or technical details.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, date
import pandas as pd


def _make_json_serializable(obj: Any) -> Any:
    """
    Recursively convert non-JSON-serializable objects to JSON-friendly types.
    
    Handles:
    - pandas Timestamp -> ISO format string
    - datetime objects -> ISO format string
    - date objects -> ISO format string
    - numpy types -> Python native types
    
    Args:
        obj: Object to convert
        
    Returns:
        JSON-serializable version of the object
    """
    # Handle pandas Timestamp
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    
    # Handle datetime objects
    if isinstance(obj, datetime):
        return obj.isoformat()
    
    # Handle date objects
    if isinstance(obj, date):
        return obj.isoformat()
    
    # Handle numpy types
    if hasattr(obj, 'item'):  # numpy scalar types
        try:
            return obj.item()
        except (ValueError, AttributeError):
            pass
    
    # Handle dictionaries - recurse
    if isinstance(obj, dict):
        return {key: _make_json_serializable(value) for key, value in obj.items()}
    
    # Handle lists/tuples - recurse
    if isinstance(obj, (list, tuple)):
        return [_make_json_serializable(item) for item in obj]
    
    # Return as-is if already serializable
    return obj


def format_strategic_output(
    strategic_result: Dict[str, Any],
    hide_internal_ids: bool = True,  # CRITICAL FIX #8: Always True by default
) -> str:
    """
    Format Strategic LLM output into user-facing text.
    
    Removes internal IDs and technical details, focusing on actionable insights.
    
    Args:
        strategic_result: Result from StrategicLLMLayer.analyze()
        hide_internal_ids: If True, remove internal pattern IDs from output
        
    Returns:
        Formatted string for user display
    """
    lines = []
    lines.append("\n" + "=" * 80)
    lines.append("STRATEGIC INSIGHTS")
    lines.append("=" * 80)
    lines.append("")
    
    # Executive Summary (if provided)
    exec_summary = strategic_result.get("executive_summary")
    if exec_summary:
        lines.append("EXECUTIVE SUMMARY:")
        lines.append("-" * 80)
        lines.append(exec_summary)
        lines.append("")
    
    # Top Priorities (structured format)
    top_priorities = strategic_result.get("top_priorities", [])
    if top_priorities:
        lines.append("TOP PRIORITIES:")
        lines.append("-" * 80)
        for i, priority in enumerate(top_priorities, 1):
            lines.append(f"\n{i}. {priority.get('issue_opportunity', 'Priority')}")
            lines.append(f"   Why it matters: {priority.get('why_it_matters', '')}")
            lines.append(f"   Expected impact: {priority.get('expected_impact', '')}")
    
    # Prioritized insights (if top_priorities not provided, fallback)
    if not top_priorities:
        prioritized_insights = strategic_result.get("prioritized_insights", [])
        if prioritized_insights:
            lines.append("TOP PRIORITIES:")
            lines.append("-" * 80)
            for i, insight in enumerate(prioritized_insights, 1):
                lines.append(f"\n{i}. {insight.get('title', 'Insight')}")
                lines.append(f"   {insight.get('summary', '')}")
                
                # Recommended actions
                actions = insight.get('recommended_actions', [])
                if actions:
                    lines.append("   Recommended Actions:")
                    for action in actions:
                        lines.append(f"   • {action}")
                
                # Confidence (if provided)
                confidence = insight.get('confidence')
                if confidence is not None:
                    lines.append(f"   Confidence: {confidence:.0%}")
    
    # Risks / Warning Signals
    risks_warnings = strategic_result.get("risks_warnings", [])
    if risks_warnings:
        lines.append("\n" + "-" * 80)
        lines.append("RISKS / WARNING SIGNALS:")
        for risk in risks_warnings:
            lines.append(f"  ⚠ {risk}")
    
    # Recommended Next Checks
    recommended_checks = strategic_result.get("recommended_checks", [])
    if recommended_checks:
        lines.append("\n" + "-" * 80)
        lines.append("RECOMMENDED NEXT CHECKS:")
        for check in recommended_checks:
            lines.append(f"  • {check}")
    
    # Notes
    notes = strategic_result.get("notes")
    if notes:
        lines.append("\n" + "-" * 80)
        lines.append("NOTES:")
        lines.append(notes)
    
    lines.append("\n" + "=" * 80)
    
    return "\n".join(lines)


def format_strategic_output_json(
    strategic_result: Dict[str, Any],
    hide_internal_ids: bool = True,  # CRITICAL FIX #8: Always True by default
) -> Dict[str, Any]:
    """
    Format Strategic LLM output into user-facing JSON.
    
    Removes internal IDs and technical details for clean API responses.
    
    Args:
        strategic_result: Result from StrategicLLMLayer.analyze()
        hide_internal_ids: If True, remove internal pattern IDs from output
        
    Returns:
        Clean JSON structure for user consumption
    """
    output = {
        "executive_summary": strategic_result.get("executive_summary"),
        "top_priorities": [],
        "risks_warnings": strategic_result.get("risks_warnings", []),
        "recommended_checks": strategic_result.get("recommended_checks", []),
        "prioritized_insights": [],
        "notes": strategic_result.get("notes"),
    }
    
    # Format top priorities (structured format)
    top_priorities = strategic_result.get("top_priorities", [])
    if top_priorities:
        for priority in top_priorities:
            clean_priority = {
                "issue_opportunity": priority.get("issue_opportunity"),
                "why_it_matters": priority.get("why_it_matters"),
                "expected_impact": priority.get("expected_impact"),
            }
            output["top_priorities"].append(clean_priority)
    
    # Format prioritized insights (fallback if top_priorities not provided)
    for insight in strategic_result.get("prioritized_insights", []):
        clean_insight = {
            "title": insight.get("title"),
            "summary": insight.get("summary"),
            "recommended_actions": insight.get("recommended_actions", []),
            "confidence": insight.get("confidence"),
        }
        
        # CRITICAL FIX #8: Ensure internal IDs never leak - always hide by default
        # Only include evidence IDs in debug mode (explicitly requested)
        # Never expose pattern IDs, evidence IDs, or internal identifiers to users
        if not hide_internal_ids:
            # Only for explicit debugging - still sanitize
            evidence_ids = insight.get("evidence_pattern_ids", [])
            if evidence_ids:
                # Sanitize IDs - remove internal structure if present
                clean_insight["evidence_pattern_ids"] = [
                    str(id) if not isinstance(id, dict) else "internal_ref"
                    for id in evidence_ids
                ]
        
        output["prioritized_insights"].append(clean_insight)
    
    # Make output JSON serializable (convert Timestamps, datetime objects, etc.)
    output = _make_json_serializable(output)
    
    return output


def convert_scored_patterns_to_dict(
    scored_patterns: List[Any],
) -> List[Dict[str, Any]]:
    """
    Convert ScoredPatternCandidate objects to dictionaries for Strategic LLM.
    
    Extracts relevant information while preserving traceability.
    CRITICAL FIX #6: Validates input before processing.
    
    Args:
        scored_patterns: List of ScoredPatternCandidate objects
        
    Returns:
        List of dictionaries with pattern information
        
    Raises:
        ValueError: If scored_patterns is empty or invalid
    """
    # CRITICAL FIX #6: Strategic LLM input validation
    if not scored_patterns:
        raise ValueError("Cannot convert empty pattern list. No insights to analyze.")
    
    if not isinstance(scored_patterns, list):
        raise ValueError(f"Expected list of patterns, got {type(scored_patterns).__name__}")
    
    patterns = []
    
    for sp in scored_patterns:
        # Validate pattern structure
        if not hasattr(sp, 'candidate'):
            raise ValueError("Invalid pattern structure: missing 'candidate' attribute")
        
        if not hasattr(sp, 'effect_size'):
            raise ValueError("Invalid pattern structure: missing 'effect_size' attribute")
        candidate = sp.candidate
        
        # Extract key information
        pattern_dict = {
            "id": candidate.pattern_id,
            "pattern_type": str(candidate.pattern_type) if candidate.pattern_type else "unknown",
            "description": candidate.description,
            "metric": candidate.metric_name,
            "observed_value": candidate.observed_value,
            "baseline_value": candidate.baseline_value,
            "dimensions": candidate.dimensions,
            "effect_size": sp.effect_size,
            "business_impact": sp.business_impact,
            "composite_score": sp.composite_score,
            "sample_size": candidate.sample_sizes.get("primary", 0),
        }
        
        # Add segment information
        if candidate.primary_segment:
            pattern_dict["primary_segment"] = candidate.primary_segment
        
        if candidate.comparison_segment:
            pattern_dict["comparison_segment"] = candidate.comparison_segment
        
        # Make pattern_dict JSON serializable (convert Timestamps, datetime objects, etc.)
        pattern_dict = _make_json_serializable(pattern_dict)
        
        patterns.append(pattern_dict)
    
    return patterns
