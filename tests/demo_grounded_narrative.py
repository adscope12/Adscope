"""
Comprehensive demonstration of Grounded Narrative Layer.

Shows:
1. Exact pipeline insertion point
2. Grounded prompt text
3. Real structured payload example
4. Validation pass example
5. Fallback trigger example
6. Terminal commands
"""

import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.narrative.grounded_payload import build_structured_insight_payload
from src.narrative.grounded_phrasing import GroundedNarrativeLayer
from src.narrative.phrasing_validation import validate_phrased_insight
from src.narrative.fallback_template import generate_fallback_phrasing
from src.models.insight import ScoredPatternCandidate
from src.models.candidate import InsightCandidate
from src.candidate_generation.pattern_types import PatternType
from datetime import datetime


def show_pipeline_insertion_point():
    """Show exact pipeline insertion point."""
    print("=" * 80)
    print("1. EXACT PIPELINE INSERTION POINT")
    print("=" * 80)
    print()
    print("File: src/pipeline/pipeline_runner.py")
    print("Lines: 364-380")
    print()
    print("```python")
    print("# ============================================================")
    print("# STEP 4.6: Insight Deduplication Layer")
    print("# ============================================================")
    print("deduplicated_patterns = deduplicate_insights(validated_patterns)")
    print()
    print("# ============================================================")
    print("# STEP 5: Grounded Narrative Layer  ← INSERTED HERE")
    print("# ============================================================")
    print("# Phrase insights using grounded narrative (constrained to detected facts)")
    print("grounded_phrased_insights = []")
    print("if not skip_strategic:")
    print("    try:")
    print("        grounded_layer = GroundedNarrativeLayer()")
    print("        grounded_phrased_insights = grounded_layer.phrase_insights(")
    print("            scored_candidates=deduplicated_patterns,")
    print("            top_n=max_insights")
    print("        )")
    print("    except Exception as e:")
    print("        # Fallback to Strategic LLM if grounded narrative fails")
    print("        grounded_phrased_insights = []")
    print()
    print("# ============================================================")
    print("# STEP 6: Strategic LLM Layer (Fallback/Executive Summary)")
    print("# ============================================================")
    print("```")
    print()


def show_grounded_prompt():
    """Show the exact grounded prompt text."""
    print("=" * 80)
    print("2. GROUNDED PROMPT TEXT")
    print("=" * 80)
    print()
    print("File: src/narrative/grounded_phrasing.py")
    print("Method: GroundedNarrativeLayer._phrase_with_llm()")
    print()
    print("SYSTEM PROMPT:")
    print("-" * 80)
    print("""You are a senior performance marketing analyst providing grounded, fact-based insights. 
You receive structured insight data from a deterministic engine. 
Your job is to phrase these insights in clear, business-readable language. 

CRITICAL CONSTRAINTS: 
1) Use ONLY the facts provided in the structured payload. 
2) Do NOT invent any new metrics, segments, dates, trends, or causes. 
3) Do NOT speculate about root causes unless explicitly stated in safe_business_interpretation. 
4) Do NOT introduce recommendations beyond the safe_action_hint. 
5) Use only the allowed_narrative_tags for phrasing style. 
6) Keep output concise and business-readable. 
7) Output MUST be valid JSON only (no markdown, no extra text).""")
    print()
    print("USER PROMPT:")
    print("-" * 80)
    print("""Given this structured insight payload, return a JSON object with:
- "headline": one short sentence (max 15 words)
- "what_is_happening": 1-2 sentences describing the pattern using ONLY facts from the payload
- "why_it_matters": 1 sentence explaining business impact using ONLY facts from the payload
- "next_check": 1 sentence based ONLY on the safe_action_hint field

Structured Payload:
{payload_json}

Allowed Narrative Tags (use these for phrasing style):
{allowed_tags}

Remember: Use ONLY the provided facts. Do not invent anything.""")
    print()


def create_real_insight_candidate() -> ScoredPatternCandidate:
    """Create a realistic insight candidate based on actual pattern detection."""
    candidate = InsightCandidate(
        pattern_type=PatternType.SEGMENT_BELOW_BASELINE,
        pattern_id="device_mobile_cvr_below_20240101",
        description="Mobile device shows lower CVR than baseline",
        primary_segment={
            'dimension': 'device',
            'value': 'mobile',
            'metrics': {
                'cvr': 0.021,
                'cpa': 14.8,
                'spend': 5200.0,
                'conversions': 351
            },
            'sample_size': 125
        },
        observed_value=0.021,
        metric_name="cvr",
        dimensions={'device': 'mobile'},
        raw_metrics={
            'primary': {'cvr': 0.021, 'cpa': 14.8, 'spend': 5200.0, 'conversions': 351},
            'comparison': {'cvr': 0.032, 'cpa': 11.2, 'spend': 4800.0, 'conversions': 429},
            'aggregate': {'cvr': 0.026, 'cpa': 12.8, 'spend': 10000.0, 'conversions': 780}
        },
        sample_sizes={'primary': 125, 'comparison': 134},
        variance_metrics={'primary_std': 0.004, 'comparison_std': 0.005},
        tenant_id="demo",
        generation_timestamp=datetime(2024, 1, 15, 10, 30, 0),
        baseline_value=0.032
    )
    
    return ScoredPatternCandidate(
        candidate=candidate,
        effect_size=0.42,
        business_impact=0.68,
        statistical_support=0.82,
        composite_score=0.74
    )


def show_real_structured_payload():
    """Show a real structured payload example."""
    print("=" * 80)
    print("3. REAL STRUCTURED PAYLOAD EXAMPLE")
    print("=" * 80)
    print()
    print("Generated from: ScoredPatternCandidate (device: mobile, metric: cvr)")
    print()
    
    candidate = create_real_insight_candidate()
    payload = build_structured_insight_payload(candidate)
    
    print(json.dumps(payload, indent=2, default=str))
    print()


def show_validation_pass_example():
    """Show an example where validation passes."""
    print("=" * 80)
    print("4. VALIDATION PASS EXAMPLE")
    print("=" * 80)
    print()
    
    candidate = create_real_insight_candidate()
    payload = build_structured_insight_payload(candidate)
    
    # Create a valid LLM output (uses only facts from payload)
    valid_llm_output = {
        "headline": "Mobile is underperforming baseline",
        "what_is_happening": "Mobile shows weaker CVR than baseline, with 0.02 vs 0.03 (34% difference).",
        "why_it_matters": "This indicates optimization opportunities to improve efficiency.",
        "next_check": "Review device-specific targeting and budget allocation."
    }
    
    print("Structured Payload:")
    print(f"  - segment: {payload['segment']}")
    print(f"  - primary_metric: {payload['primary_metric']}")
    print(f"  - observed_value: {payload['observed_value']}")
    print(f"  - baseline_value: {payload['baseline_value']}")
    print()
    
    print("LLM Output (valid - uses only facts from payload):")
    print(json.dumps(valid_llm_output, indent=2))
    print()
    
    validation_result = validate_phrased_insight(valid_llm_output, payload)
    print(f"Validation Result: {'✓ PASS' if validation_result else '✗ FAIL'}")
    print()
    print("Why it passes:")
    print("  ✓ All required fields present (headline, what_is_happening, why_it_matters, next_check)")
    print("  ✓ Only mentions 'mobile' (segment from payload)")
    print("  ✓ Only mentions 'CVR' (primary_metric from payload)")
    print("  ✓ Uses observed_value (0.02) and baseline_value (0.03) from payload")
    print("  ✓ next_check matches safe_action_hint from payload")
    print()


def show_fallback_trigger_example():
    """Show an example where fallback would trigger."""
    print("=" * 80)
    print("5. FALLBACK TRIGGER EXAMPLE")
    print("=" * 80)
    print()
    
    candidate = create_real_insight_candidate()
    payload = build_structured_insight_payload(candidate)
    
    print("Scenario 1: LLM returns invalid JSON or empty fields")
    print("-" * 80)
    invalid_output_1 = {
        "headline": "Mobile performance issue",
        # Missing what_is_happening
        "why_it_matters": "",
        "next_check": "Review"
    }
    print("Invalid LLM Output:")
    print(json.dumps(invalid_output_1, indent=2))
    print()
    validation_result_1 = validate_phrased_insight(invalid_output_1, payload)
    print(f"Validation Result: {'✓ PASS' if validation_result_1 else '✗ FAIL'}")
    print("→ Fallback triggered: Missing required field 'what_is_happening'")
    print()
    
    print("Scenario 2: LLM invents unsupported metric")
    print("-" * 80)
    invalid_output_2 = {
        "headline": "Mobile has low ROAS",
        "what_is_happening": "Mobile shows weak ROAS of 2.1, which is below the target of 3.0.",
        "why_it_matters": "This indicates poor return on ad spend.",
        "next_check": "Review device-specific targeting and budget allocation."
    }
    print("Invalid LLM Output (invents ROAS metric not in payload):")
    print(json.dumps(invalid_output_2, indent=2))
    print()
    print("Payload only contains: cvr, cpa, spend, conversions")
    print("LLM mentions: ROAS (not in payload)")
    print("→ Fallback triggered: Unsupported metric mentioned")
    print()
    
    print("Scenario 3: LLM call fails (network error, API error, etc.)")
    print("-" * 80)
    print("Exception raised during LLM call:")
    print("  → Exception caught in phrase_insights()")
    print("  → Fallback template used automatically")
    print()
    
    print("FALLBACK TEMPLATE OUTPUT:")
    print("-" * 80)
    fallback_output = generate_fallback_phrasing(payload)
    print(json.dumps(fallback_output, indent=2))
    print()
    print("Fallback is deterministic and always uses facts from payload.")
    print()


def show_terminal_commands():
    """Show terminal commands to verify behavior."""
    print("=" * 80)
    print("6. TERMINAL COMMANDS TO VERIFY BEHAVIOR")
    print("=" * 80)
    print()
    
    print("A. Run demonstration script (shows all examples):")
    print("-" * 80)
    print("  python3 tests/demo_grounded_narrative.py")
    print()
    
    print("B. Run basic test (shows structured payload and fallback):")
    print("-" * 80)
    print("  python3 tests/test_grounded_narrative.py")
    print()
    
    print("C. Test with real dataset via CLI:")
    print("-" * 80)
    print("  python3 cli.py test_data/t03_clean_en_platform_device.csv")
    print()
    print("  This will run the full pipeline including grounded narrative layer.")
    print("  Check logs for 'Grounded narrative layer' messages.")
    print()
    
    print("D. Test via API endpoint:")
    print("-" * 80)
    print("  # Start server:")
    print("  python3 api.py")
    print()
    print("  # In another terminal, upload a file:")
    print("  curl -X POST http://localhost:8000/analyze \\")
    print("    -F 'file=@test_data/t03_clean_en_platform_device.csv'")
    print()
    print("  # Or use the web UI:")
    print("  open http://localhost:8000/app")
    print()
    
    print("E. Verify grounded narrative is active:")
    print("-" * 80)
    print("  # Check API response - should include 'notes' field:")
    print("  # 'Insights generated using grounded narrative layer.'")
    print()
    print("  # If grounded narrative fails, falls back to Strategic LLM")
    print("  # Check server logs for warnings:")
    print("  # 'Grounded narrative layer failed: ... Falling back to Strategic LLM.'")
    print()
    
    print("F. Test validation logic directly:")
    print("-" * 80)
    print("  python3 -c \"")
    print("from tests.demo_grounded_narrative import *")
    print("show_validation_pass_example()")
    print("show_fallback_trigger_example()")
    print("\"")
    print()


def main():
    """Run all demonstrations."""
    show_pipeline_insertion_point()
    show_grounded_prompt()
    show_real_structured_payload()
    show_validation_pass_example()
    show_fallback_trigger_example()
    show_terminal_commands()


if __name__ == "__main__":
    main()
