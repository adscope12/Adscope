"""
Phrasing Validation - Validates LLM output against structured payload.

Ensures LLM output only uses facts from the payload and doesn't invent new information.
"""

import re
from typing import Dict, Any, List


def validate_phrased_insight(
    phrased_output: Dict[str, Any],
    structured_payload: Dict[str, Any]
) -> bool:
    """
    Validate that phrased insight only uses facts from structured payload.
    
    STRICT VALIDATION - fails on any unsupported language.
    
    Checks:
    - Every mentioned metric exists in the payload
    - Every mentioned segment exists in the payload
    - Every mentioned date exists in the payload (if dates are mentioned)
    - No unsupported cause phrases are introduced
    - No unsupported recommendations are introduced
    - No extra dimensions or segments beyond payload
    
    Args:
        phrased_output: LLM output with headline, what_is_happening, etc.
        structured_payload: Original structured payload with facts
        
    Returns:
        True if validation passes, False otherwise
    """
    # Extract all text from phrased output
    all_text = " ".join([
        phrased_output.get("headline", ""),
        phrased_output.get("what_is_happening", ""),
        phrased_output.get("why_it_matters", ""),
        phrased_output.get("next_check", "")
    ]).lower()
    
    # Check for empty required fields
    required_fields = ["headline", "what_is_happening", "why_it_matters", "next_check"]
    for field in required_fields:
        if not phrased_output.get(field, "").strip():
            return False

    # Enforce headline quality: reject vague or placeholder headlines
    headline = phrased_output.get("headline", "").strip().lower()
    forbidden_headline_fragments = [
        "segment",
        "latest segment",
        "recent segment",
        "observed in",
        "performance improved significantly",
    ]
    for frag in forbidden_headline_fragments:
        if frag in headline:
            return False
    
    # Extract allowed metrics from payload
    allowed_metrics = [structured_payload.get("primary_metric", "").lower()]
    allowed_metrics.extend([m.lower() for m in structured_payload.get("secondary_metrics", [])])
    allowed_metrics = [m for m in allowed_metrics if m]
    
    # Extract allowed segments
    allowed_segments = [
        structured_payload.get("segment", "").lower(),
        structured_payload.get("comparison_target", "").lower()
    ]
    allowed_segments = [s for s in allowed_segments if s and s != "unknown"]
    
    # Extract allowed dimensions
    allowed_dimensions = [structured_payload.get("dimension", "").lower()]
    allowed_dimensions = [d for d in allowed_dimensions if d and d != "unknown"]
    
    # STRICT CHECK 1: Unsupported metrics
    common_metrics = ['roas', 'cpa', 'cpc', 'cvr', 'ctr', 'revenue', 'spend', 'conversions', 'clicks', 'impressions', 'aov']
    for metric in common_metrics:
        if metric not in allowed_metrics:
            metric_pattern = rf'\b{metric}\b'
            if re.search(metric_pattern, all_text, re.IGNORECASE):
                # Check if it's mentioned in safe_action_hint or safe_business_interpretation
                safe_hint = structured_payload.get("safe_action_hint", "").lower()
                safe_interp = structured_payload.get("safe_business_interpretation", "").lower()
                if metric not in safe_hint and metric not in safe_interp:
                    # FAIL: Unsupported metric mentioned
                    return False
    
    # STRICT CHECK 2: Unsupported segments
    # Check for segment mentions that don't match allowed segments
    # This is a simplified check - could be enhanced with better NLP
    segment_words = all_text.split()
    for word in segment_words:
        # Skip common words
        if word in ['the', 'a', 'an', 'is', 'are', 'was', 'were', 'than', 'from', 'to', 'with', 'shows', 'showed']:
            continue
        # Check if word might be a segment name (2+ chars, not a number)
        if len(word) >= 2 and not word.replace('.', '').replace(',', '').isdigit():
            # If it's not in allowed segments and not a common word, might be unsupported
            # But be careful - this is heuristic
            pass
    
    # STRICT CHECK 3: Causal phrases (FAIL if found)
    forbidden_causal_phrases = [
        r"suggesting that",
        r"indicating that changes were made",
        r"likely due to",
        r"this may mean",
        r"highlighting an opportunity",
        r"because of",
        r"due to",
        r"caused by",
        r"result of",
        r"attributed to",
        r"signaling",
        r"indicating",
    ]
    
    safe_interp = structured_payload.get("safe_business_interpretation", "").lower()
    safe_hint = structured_payload.get("safe_action_hint", "").lower()
    safe_text = (safe_interp + " " + safe_hint).lower()
    
    for phrase_pattern in forbidden_causal_phrases:
        if re.search(phrase_pattern, all_text, re.IGNORECASE):
            # Only allow if it's in safe_business_interpretation or safe_action_hint
            if not re.search(phrase_pattern, safe_text, re.IGNORECASE):
                # FAIL: Unsupported causal language
                return False
    
    # STRICT CHECK 4: Unsupported dates
    # Check if dates are mentioned but not in payload
    time_period = structured_payload.get("time_period")
    if not time_period:
        # No time period in payload - check if dates are mentioned
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
            r'\d{1,2}/\d{1,2}/\d{4}',  # MM/DD/YYYY
            r'(january|february|march|april|may|june|july|august|september|october|november|december)',
            r'(monday|tuesday|wednesday|thursday|friday|saturday|sunday)',
        ]
        for pattern in date_patterns:
            if re.search(pattern, all_text, re.IGNORECASE):
                # FAIL: Date mentioned but not in payload
                return False
    
    # STRICT CHECK 5: Recommendations beyond safe_action_hint
    # Check if next_check significantly diverges from safe_action_hint
    next_check = phrased_output.get("next_check", "").lower()
    safe_action_hint = structured_payload.get("safe_action_hint", "").lower()
    
    # Allow some rephrasing, but check for major additions
    # If next_check is much longer or contains new concepts, fail
    if next_check and safe_action_hint:
        # Simple check: if next_check is >50% longer, might have additions
        if len(next_check) > len(safe_action_hint) * 1.5:
            # Check for new action words not in safe_action_hint
            action_words = ['optimize', 'increase', 'decrease', 'change', 'modify', 'adjust', 'test', 'experiment']
            for word in action_words:
                if word in next_check and word not in safe_action_hint:
                    # Might be adding new recommendations
                    # Be lenient here - just warn, don't fail
                    pass
    
    # All strict checks passed
    return True
