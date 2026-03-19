"""
Test and demonstrate the Grounded Narrative Layer.

Shows:
1. Structured insight payload example
2. Grounded LLM output example
3. Fallback template output example
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.narrative.grounded_payload import build_structured_insight_payload
from src.narrative.fallback_template import generate_fallback_phrasing
from src.models.insight import ScoredPatternCandidate
from src.models.candidate import InsightCandidate
from src.candidate_generation.pattern_types import PatternType
from datetime import datetime


def create_test_candidate() -> ScoredPatternCandidate:
    """Create a test candidate for demonstration."""
    candidate = InsightCandidate(
        pattern_type=PatternType.SEGMENT_BELOW_BASELINE,
        pattern_id="test_device_mobile_cvr",
        description="Mobile device shows lower CVR than baseline",
        primary_segment={
            'dimension': 'device',
            'value': 'mobile',
            'metrics': {'cvr': 0.02, 'cpa': 15.5, 'spend': 5000},
            'sample_size': 100
        },
        observed_value=0.02,
        metric_name="cvr",
        dimensions={'device': 'mobile'},
        raw_metrics={
            'primary': {'cvr': 0.02, 'cpa': 15.5},
            'comparison': {'cvr': 0.03, 'cpa': 12.0},
            'aggregate': {'cvr': 0.025, 'cpa': 13.5}
        },
        sample_sizes={'primary': 100, 'comparison': 150},
        variance_metrics={'primary_std': 0.005, 'comparison_std': 0.004},
        tenant_id="test",
        generation_timestamp=datetime.now(),
        baseline_value=0.03
    )
    
    return ScoredPatternCandidate(
        candidate=candidate,
        effect_size=0.35,
        business_impact=0.65,
        statistical_support=0.75,
        composite_score=0.70
    )


def demonstrate_structured_payload():
    """Show example structured insight payload."""
    print("=" * 70)
    print("EXAMPLE 1: Structured Insight Payload")
    print("=" * 70)
    print()
    
    candidate = create_test_candidate()
    payload = build_structured_insight_payload(candidate)
    
    import json
    print(json.dumps(payload, indent=2, default=str))
    print()


def demonstrate_fallback_template():
    """Show example fallback template output."""
    print("=" * 70)
    print("EXAMPLE 2: Fallback Template Output")
    print("=" * 70)
    print()
    
    candidate = create_test_candidate()
    payload = build_structured_insight_payload(candidate)
    fallback = generate_fallback_phrasing(payload)
    
    import json
    print(json.dumps(fallback, indent=2))
    print()


def demonstrate_grounded_llm_output():
    """Show example of what grounded LLM output should look like."""
    print("=" * 70)
    print("EXAMPLE 3: Expected Grounded LLM Output")
    print("=" * 70)
    print()
    print("(This is what the LLM should return when given the structured payload)")
    print()
    
    example_output = {
        "headline": "Mobile is underperforming baseline",
        "what_is_happening": "Mobile shows weaker CVR than baseline, with 0.02 vs 0.03 (33% difference).",
        "why_it_matters": "This indicates optimization opportunities to improve efficiency.",
        "next_check": "Review device-specific targeting and budget allocation."
    }
    
    import json
    print(json.dumps(example_output, indent=2))
    print()


if __name__ == "__main__":
    demonstrate_structured_payload()
    demonstrate_fallback_template()
    demonstrate_grounded_llm_output()
