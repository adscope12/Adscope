"""
Grounded Narrative Layer - Constrains LLM to only use detected facts.
"""

from .grounded_payload import build_structured_insight_payload
from .grounded_phrasing import GroundedNarrativeLayer
from .phrasing_validation import validate_phrased_insight
from .fallback_template import generate_fallback_phrasing

__all__ = [
    "build_structured_insight_payload",
    "GroundedNarrativeLayer",
    "validate_phrased_insight",
    "generate_fallback_phrasing",
]
