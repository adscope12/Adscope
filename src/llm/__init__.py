from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv


def _make_json_serializable(obj: Any) -> Any:
    """
    Recursively convert non-JSON-serializable objects to JSON-friendly types.
    
    Handles numpy bools, integers, floats, arrays, and pandas Timestamps.
    This is a safety net before json.dumps() calls.
    """
    import numpy as np
    import pandas as pd
    from datetime import datetime, date
    
    # Handle pandas Timestamp
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    
    # Handle datetime objects
    if isinstance(obj, datetime):
        return obj.isoformat()
    
    # Handle date objects
    if isinstance(obj, date):
        return obj.isoformat()
    
    # Handle numpy boolean types explicitly
    if isinstance(obj, np.bool_):
        return bool(obj)
    
    # Handle numpy integer types
    if isinstance(obj, np.integer):
        return int(obj)
    
    # Handle numpy floating types
    if isinstance(obj, np.floating):
        return float(obj)
    
    # Handle numpy arrays
    if isinstance(obj, np.ndarray):
        return [_make_json_serializable(item) for item in obj.tolist()]
    
    # Handle other numpy scalar types (via .item() method)
    if hasattr(obj, 'item') and hasattr(obj, 'dtype'):
        try:
            return _make_json_serializable(obj.item())
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


# --- Environment loading (explicit, stable) ---
def _load_env() -> None:
    # Load .env explicitly from repo root (current working directory)
    env_path = Path.cwd() / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=True)


@dataclass
class StrategicInsight:
    title: str
    summary: str
    evidence_pattern_ids: List[str]
    recommended_actions: List[str]
    confidence: float  # 0..1


class StrategicLLMLayer:
    """
    Strategic LLM Layer - runs AFTER the deterministic insight engine.
    
    Architecture position:
    1. LLM-Assisted Reading Layer (runs BEFORE deterministic engine)
       - Interprets inconsistent column names, platform/campaign/KPI naming
       - Handles multilingual naming (Hebrew/English), typos
       - Preserves relevant fields
    2. Deterministic Insight Engine (this runs here)
       - Feature extraction, normalization, pattern generation, scoring
    3. Strategic LLM Layer (this class - runs AFTER deterministic engine)
       - Takes scored patterns from the deterministic engine
       - Prioritizes and synthesizes into a small set of actionable insights
       - DOES NOT invent new data, only uses provided patterns
    """

    def __init__(self, model: Optional[str] = None):
        _load_env()

        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("Missing OPENAI_API_KEY in environment (.env).")

        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

        # Lazy import to keep module import clean
        from openai import OpenAI  # type: ignore
        self.client = OpenAI(api_key=self.api_key)

    def analyze(
        self,
        scored_patterns: List[Dict[str, Any]],
        top_n: int = 4,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Returns a structured JSON dict:
        {
          "prioritized_insights": [ ... up to top_n ... ],
          "notes": "...",
        }
        """

        # Keep payload small & safe (don't send huge raw frames)
        payload = {
            "top_n": top_n,
            "patterns": scored_patterns,
            "context": context or {},
        }
        
        # CRITICAL: Convert payload to JSON-serializable types before json.dumps()
        # This ensures numpy bools/int/floats in context (e.g., validation_metadata) are converted
        payload = _make_json_serializable(payload)

        system = (
            "You are a senior performance marketing analyst. "
            "You receive scored pattern outputs from a deterministic engine. "
            "Your job is to prioritize and synthesize them into actionable strategic insights. "
            "CRITICAL RULES: "
            "1) Use ONLY the provided patterns/context. Do NOT invent metrics, numbers, or facts. "
            "2) Do NOT modify or change any numeric values from the patterns. "
            "3) Do NOT invent new insights - only interpret and prioritize provided patterns. "
            "4) If something is missing, say it explicitly. "
            "5) Output MUST be valid JSON only (no markdown, no extra text)."
        )

        user = (
            "Given this JSON input (engine patterns + optional context), return a JSON object with:\n"
            f'- "prioritized_insights": array of up to {top_n} items. Each item must include:\n'
            '   - title (string): Clear, actionable title\n'
            '   - summary (string, 1-2 sentences): What the issue/opportunity is and why it matters. '
            '     IMPORTANT: Include specific evidence from the data when available, such as:\n'
            '     * Metric values (e.g., "Mobile generates 65% of clicks but converts 2.3x worse")\n'
            '     * Effect sizes (e.g., "effect size of 0.45 indicates significant deviation")\n'
            '     * Observed vs baseline comparisons (e.g., "conversion rate is 0.12 vs baseline 0.08")\n'
            '     * Segment details (e.g., "in Mobile, Google campaigns")\n'
            '     Use the observed_value, baseline_value, effect_size, and primary_segment fields from patterns.\n'
            '   - evidence_pattern_ids (array of strings: use pattern["id"] for traceability)\n'
            '   - recommended_actions (array of 2-4 concise, actionable steps)\n'
            '   - confidence (number 0..1): Confidence in this insight\n'
            '- "top_priorities": array of top 3 priorities, each with:\n'
            '   - issue_opportunity (string): What the issue/opportunity is\n'
            '   - why_it_matters (string): Why this matters. Include specific metrics/evidence from patterns when available.\n'
            '   - expected_impact (string): Expected impact\n'
            '- "risks_warnings": array of risk/warning signals (if any)\n'
            '- "recommended_checks": array of recommended next checks (max 5)\n'
            '- "executive_summary": string (2-4 sentences): High-level summary\n'
            '- "notes": string (short). Mention any key missing info.\n'
            "Input JSON:\n"
            f"{json.dumps(payload, ensure_ascii=False)}"
        )

        # Try Responses API first (newer SDK), fallback to Chat Completions (older SDK)
        try:
            if hasattr(self.client, "responses"):
                resp = self.client.responses.create(
                    model=self.model,
                    input=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                )
                text = getattr(resp, "output_text", None)
                if not text:
                    # Some SDK variants store text differently; last resort:
                    text = str(resp)
            else:
                raise AttributeError("responses not available")

        except Exception:
            # Fallback: chat.completions
            try:
                # Try with response_format for JSON mode (newer API)
                chat = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    temperature=0.2,
                    response_format={"type": "json_object"},
                )
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

        # CRITICAL FIX #3: Safer LLM JSON parsing with graceful failure handling
        result = None
        
        # Try direct JSON parsing
        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            import re
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass
            
            # If still no result, try to find JSON object in text
            if result is None:
                json_match = re.search(r'\{.*\}', text, re.DOTALL)
                if json_match:
                    try:
                        result = json.loads(json_match.group(0))
                    except json.JSONDecodeError:
                        pass
        
        # CRITICAL FIX #7: Sanitized error - don't leak raw LLM output
        if result is None:
            raise RuntimeError(
                "Strategic analysis failed: Unable to parse LLM response. "
                "Please try again. If the problem persists, the insights may be too complex to analyze."
            )
        
        # Validate result structure
        if not isinstance(result, dict):
            raise RuntimeError(
                "Strategic analysis failed: Invalid response format. Please try again."
            )
        
        return result
        