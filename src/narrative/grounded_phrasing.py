"""
Grounded Narrative Layer - LLM Phrasing with Strict Constraints.

This module provides grounded LLM phrasing that only uses detected facts,
with validation and fallback templates.
"""

import json
import os
from typing import Dict, Any, List, Optional
from pathlib import Path
from dotenv import load_dotenv

from .grounded_payload import build_structured_insight_payload
from .narrative_tags import get_narrative_tags_for_pattern
from .phrasing_validation import validate_phrased_insight
from .fallback_template import generate_fallback_phrasing


def _load_env() -> None:
    """Load .env file."""
    env_path = Path.cwd() / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=True)


def _make_json_serializable(obj: Any) -> Any:
    """Recursively convert non-JSON-serializable objects."""
    import numpy as np
    import pandas as pd
    from datetime import datetime, date
    
    if isinstance(obj, (pd.Timestamp, datetime, date)):
        return obj.isoformat()
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return [_make_json_serializable(item) for item in obj.tolist()]
    if hasattr(obj, 'item') and hasattr(obj, 'dtype'):
        try:
            return _make_json_serializable(obj.item())
        except (ValueError, AttributeError):
            pass
    if isinstance(obj, dict):
        return {key: _make_json_serializable(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_json_serializable(item) for item in obj]
    return obj


class GroundedNarrativeLayer:
    """
    Grounded Narrative Layer - Constrains LLM to only use detected facts.
    
    This layer sits between insight deduplication and final API response.
    It ensures the LLM acts as a grounded narrator, not a free analyst.
    """
    
    def __init__(self, model: Optional[str] = None):
        _load_env()
        
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("Missing OPENAI_API_KEY in environment (.env).")
        
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        
        from openai import OpenAI
        self.client = OpenAI(api_key=self.api_key)
    
    def phrase_insights(
        self,
        scored_candidates: List[Any],
        top_n: int = 4
    ) -> List[Dict[str, Any]]:
        """
        Phrase insights using grounded narrative approach.
        
        Args:
            scored_candidates: List of ScoredPatternCandidate objects
            top_n: Maximum number of insights to phrase
            
        Returns:
            List of phrased insights with structure:
            {
                "headline": "...",
                "what_is_happening": "...",
                "why_it_matters": "...",
                "next_check": "..."
            }
        """
        if not scored_candidates:
            return []
        
        # Limit to top_n
        candidates = scored_candidates[:top_n]
        
        phrased_insights = []
        
        for candidate in candidates:
            # Build structured payload
            payload = build_structured_insight_payload(candidate)
            payload = _make_json_serializable(payload)
            
            # Try LLM phrasing
            try:
                llm_output = self._phrase_with_llm(payload)
                
                # STRICT VALIDATION - be aggressive in using fallback
                if validate_phrased_insight(llm_output, payload):
                    # Additional check: if output seems too long or complex, prefer fallback
                    total_length = sum(len(str(v)) for v in llm_output.values())
                    if total_length > 500:  # Suspiciously long output
                        fallback_output = generate_fallback_phrasing(payload)
                        phrased_insights.append(fallback_output)
                    else:
                        phrased_insights.append(llm_output)
                else:
                    # Validation failed - use fallback
                    fallback_output = generate_fallback_phrasing(payload)
                    phrased_insights.append(fallback_output)
            
            except Exception as e:
                # LLM failed - use fallback (any exception triggers fallback)
                fallback_output = generate_fallback_phrasing(payload)
                phrased_insights.append(fallback_output)
        
        return phrased_insights
    
    def _phrase_with_llm(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Phrase a single insight using LLM with strict constraints."""
        
        system = (
            "You are a senior performance marketing analyst providing grounded, fact-based insights. "
            "You receive structured insight data from a deterministic engine. "
            "Your job is to phrase these insights in clear, business-readable language. "
            "\n"
            "CRITICAL CONSTRAINTS: "
            "1) Use ONLY the facts provided in the structured payload. "
            "2) Do NOT invent any new metrics, segments, dates, trends, or causes. "
            "3) Do NOT use causal language such as 'suggesting that', 'indicating that changes were made', "
            "   'likely due to', 'this may mean', 'highlighting an opportunity' (unless in safe_action_hint). "
            "4) Do NOT introduce recommendations beyond the safe_action_hint. "
            "5) Use only the allowed_narrative_tags for phrasing style. "
            "6) Keep output concise and business-readable. "
            "7) Output MUST be valid JSON only (no markdown, no extra text). "
            "8) Stay observational: describe what happened, not why it happened or what it implies beyond safe_business_interpretation."
        )
        
        # Extract only allowed fields for reference
        allowed_fields = {
            "segment": payload.get("segment"),
            "comparison_target": payload.get("comparison_target"),
            "primary_metric": payload.get("primary_metric"),
            "secondary_metrics": payload.get("secondary_metrics", []),
            "observed_value": payload.get("observed_value"),
            "baseline_value": payload.get("baseline_value"),
            "direction": payload.get("direction"),
            "safe_business_interpretation": payload.get("safe_business_interpretation"),
            "safe_action_hint": payload.get("safe_action_hint"),
        }
        if payload.get("time_period"):
            allowed_fields["time_period"] = payload.get("time_period")
        
        user = (
            "Given this structured insight payload, return a JSON object with:\n"
            '- "headline": one short sentence (max 15 words)\n'
            '- "what_is_happening": 1-2 sentences describing the pattern using ONLY the allowed fields below\n'
            '- "why_it_matters": 1 sentence using ONLY safe_business_interpretation from the payload\n'
            '- "next_check": copy safe_action_hint exactly (or rephrase minimally if needed for readability)\n'
            "\n"
            "ALLOWED FIELDS (use ONLY these):\n"
            f"{json.dumps(allowed_fields, ensure_ascii=False, indent=2)}\n"
            "\n"
            "FORBIDDEN LANGUAGE (do NOT use):\n"
            "- 'suggesting that...'\n"
            "- 'indicating that changes were made...'\n"
            "- 'likely due to...'\n"
            "- 'this may mean...'\n"
            "- 'highlighting an opportunity...' (unless in safe_action_hint)\n"
            "- any implied root cause language\n"
            "\n"
            "ALLOWED LANGUAGE (use these patterns):\n"
            "- 'X outperformed Y'\n"
            "- 'X showed higher/lower Y'\n"
            "- 'A spike occurred on date Z' (only if time_period in payload)\n"
            "- 'This pattern is associated with stronger/weaker efficiency'\n"
            "- 'This may justify reviewing...' (only if aligned with safe_action_hint)\n"
            "\n"
            "Remember: Be observational only. Do not invent, speculate, or imply causes."
        )
        
        # Call LLM
        try:
            chat = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            text = chat.choices[0].message.content
        except TypeError:
            # Fallback for older API versions
            chat = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.2,
            )
            text = chat.choices[0].message.content
        
        # Parse JSON
        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown
            import re
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(1))
            else:
                json_match = re.search(r'\{.*\}', text, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group(0))
                else:
                    raise RuntimeError("Failed to parse LLM response as JSON")
        
        # Validate structure
        required_fields = ["headline", "what_is_happening", "why_it_matters", "next_check"]
        for field in required_fields:
            if field not in result:
                result[field] = ""
        
        return result
