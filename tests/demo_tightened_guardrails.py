"""
Demonstration of tightened grounded narrative guardrails.

Shows:
- Old vs new example output
- Example that now fails validation
- Deterministic executive summary example
"""

import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.narrative.grounded_payload import build_structured_insight_payload
from src.narrative.phrasing_validation import validate_phrased_insight
from src.narrative.fallback_template import generate_fallback_phrasing
from src.models.insight import ScoredPatternCandidate
from src.models.candidate import InsightCandidate
from src.candidate_generation.pattern_types import PatternType
from datetime import datetime


def create_test_candidate() -> ScoredPatternCandidate:
    """Create a test candidate."""
    candidate = InsightCandidate(
        pattern_type=PatternType.SEGMENT_BELOW_BASELINE,
        pattern_id="device_mobile_cvr_below",
        description="Mobile device shows lower CVR than baseline",
        primary_segment={
            'dimension': 'device',
            'value': 'mobile',
            'metrics': {'cvr': 0.021, 'cpa': 14.8},
            'sample_size': 100
        },
        observed_value=0.021,
        metric_name="cvr",
        dimensions={'device': 'mobile'},
        raw_metrics={
            'primary': {'cvr': 0.021, 'cpa': 14.8},
            'comparison': {'cvr': 0.032, 'cpa': 11.2},
            'aggregate': {'cvr': 0.026, 'cpa': 12.8}
        },
        sample_sizes={'primary': 100, 'comparison': 150},
        variance_metrics={'primary_std': 0.004, 'comparison_std': 0.005},
        tenant_id="test",
        generation_timestamp=datetime.now(),
        baseline_value=0.032
    )
    
    return ScoredPatternCandidate(
        candidate=candidate,
        effect_size=0.42,
        business_impact=0.68,
        statistical_support=0.82,
        composite_score=0.74
    )


def show_old_vs_new_output():
    """Show old vs new example output."""
    print("=" * 80)
    print("OLD VS NEW EXAMPLE OUTPUT")
    print("=" * 80)
    print()
    
    candidate = create_test_candidate()
    payload = build_structured_insight_payload(candidate)
    
    print("Structured Payload:")
    print(f"  segment: {payload['segment']}")
    print(f"  primary_metric: {payload['primary_metric']}")
    print(f"  observed_value: {payload['observed_value']}")
    print(f"  baseline_value: {payload['baseline_value']}")
    print()
    
    print("OLD OUTPUT (would pass old validation, fails new validation):")
    print("-" * 80)
    old_output = {
        "headline": "Mobile is underperforming baseline",
        "what_is_happening": "Mobile shows weaker CVR than baseline, indicating that changes were made to the campaign structure. This suggests optimization opportunities.",
        "why_it_matters": "This highlights an opportunity to improve conversion efficiency and may signal improved campaign performance if addressed.",
        "next_check": "Review device-specific targeting and budget allocation, and consider testing new creative formats."
    }
    print(json.dumps(old_output, indent=2))
    print()
    old_validation = validate_phrased_insight(old_output, payload)
    print(f"Old Validation Result: {'✓ PASS' if old_validation else '✗ FAIL'}")
    print()
    print("Problems in old output:")
    print("  ✗ 'indicating that changes were made' - unsupported causal language")
    print("  ✗ 'highlights an opportunity' - unsupported language")
    print("  ✗ 'may signal improved campaign performance' - unsupported speculation")
    print("  ✗ 'consider testing new creative formats' - recommendation beyond safe_action_hint")
    print()
    
    print("NEW OUTPUT (passes new validation):")
    print("-" * 80)
    new_output = {
        "headline": "Mobile is underperforming baseline",
        "what_is_happening": "Mobile shows weaker CVR than baseline, with 0.02 vs 0.03 (34% difference).",
        "why_it_matters": "This segment shows weaker performance than the comparison target.",
        "next_check": "Review device-specific targeting and budget allocation."
    }
    print(json.dumps(new_output, indent=2))
    print()
    new_validation = validate_phrased_insight(new_output, payload)
    print(f"New Validation Result: {'✓ PASS' if new_validation else '✗ FAIL'}")
    print()
    print("Why new output passes:")
    print("  ✓ No causal language")
    print("  ✓ Only uses facts from payload")
    print("  ✓ Uses exact safe_business_interpretation")
    print("  ✓ next_check matches safe_action_hint")
    print()
    
    print("FALLBACK OUTPUT (deterministic, always safe):")
    print("-" * 80)
    fallback_output = generate_fallback_phrasing(payload)
    print(json.dumps(fallback_output, indent=2))
    print()


def show_validation_failure_example():
    """Show an example that now fails validation."""
    print("=" * 80)
    print("EXAMPLE THAT NOW FAILS VALIDATION")
    print("=" * 80)
    print()
    
    candidate = create_test_candidate()
    payload = build_structured_insight_payload(candidate)
    
    print("Structured Payload:")
    print(f"  primary_metric: {payload['primary_metric']}")
    print(f"  secondary_metrics: {payload['secondary_metrics']}")
    print(f"  segment: {payload['segment']}")
    print()
    
    print("Example 1: Unsupported metric (ROAS not in payload)")
    print("-" * 80)
    invalid_output_1 = {
        "headline": "Mobile has low ROAS",
        "what_is_happening": "Mobile shows weak ROAS of 2.1, which is below the target of 3.0.",
        "why_it_matters": "This indicates poor return on ad spend.",
        "next_check": "Review device-specific targeting and budget allocation."
    }
    print(json.dumps(invalid_output_1, indent=2))
    print()
    validation_1 = validate_phrased_insight(invalid_output_1, payload)
    print(f"Validation Result: {'✓ PASS' if validation_1 else '✗ FAIL'}")
    print("→ FAIL: ROAS is not in payload (only cvr, cpa are allowed)")
    print()
    
    print("Example 2: Causal language")
    print("-" * 80)
    invalid_output_2 = {
        "headline": "Mobile is underperforming baseline",
        "what_is_happening": "Mobile shows weaker CVR, likely due to poor targeting settings.",
        "why_it_matters": "This suggests that optimization is needed.",
        "next_check": "Review device-specific targeting and budget allocation."
    }
    print(json.dumps(invalid_output_2, indent=2))
    print()
    validation_2 = validate_phrased_insight(invalid_output_2, payload)
    print(f"Validation Result: {'✓ PASS' if validation_2 else '✗ FAIL'}")
    print("→ FAIL: 'likely due to' and 'suggests that' are forbidden causal phrases")
    print()
    
    print("Example 3: Unsupported date")
    print("-" * 80)
    invalid_output_3 = {
        "headline": "Mobile is underperforming baseline",
        "what_is_happening": "Mobile shows weaker CVR than baseline, with a spike on January 15th.",
        "why_it_matters": "This segment shows weaker performance than the comparison target.",
        "next_check": "Review device-specific targeting and budget allocation."
    }
    print(json.dumps(invalid_output_3, indent=2))
    print()
    validation_3 = validate_phrased_insight(invalid_output_3, payload)
    print(f"Validation Result: {'✓ PASS' if validation_3 else '✗ FAIL'}")
    print("→ FAIL: Date mentioned but time_period not in payload")
    print()


def show_deterministic_executive_summary():
    """Show deterministic executive summary examples."""
    print("=" * 80)
    print("DETERMINISTIC EXECUTIVE SUMMARY EXAMPLES")
    print("=" * 80)
    print()
    
    print("Example 1: Single insight")
    print("-" * 80)
    headlines_1 = ["Mobile is underperforming baseline"]
    if len(headlines_1) == 1:
        exec_summary_1 = f"Top finding: {headlines_1[0]}"
    print(f"Headlines: {headlines_1}")
    print(f"Executive Summary: {exec_summary_1}")
    print()
    
    print("Example 2: Two insights")
    print("-" * 80)
    headlines_2 = [
        "Mobile is underperforming baseline",
        "Google shows stronger efficiency than Facebook"
    ]
    if len(headlines_2) == 2:
        exec_summary_2 = f"Top findings show {headlines_2[0].lower()} and {headlines_2[1].lower()}"
    print(f"Headlines: {headlines_2}")
    print(f"Executive Summary: {exec_summary_2}")
    print()
    
    print("Example 3: Three insights")
    print("-" * 80)
    headlines_3 = [
        "Mobile is underperforming baseline",
        "Google shows stronger efficiency than Facebook",
        "Weekend performance gap detected"
    ]
    if len(headlines_3) == 3:
        key_terms = []
        for h in headlines_3:
            words = h.split()[:4]
            key_terms.append(" ".join(words).lower())
        exec_summary_3 = f"Top findings show {key_terms[0]}, {key_terms[1]}, and {key_terms[2]}"
    print(f"Headlines: {headlines_3}")
    print(f"Executive Summary: {exec_summary_3}")
    print()
    
    print("Key Points:")
    print("  ✓ Executive summary built ONLY from validated headlines")
    print("  ✓ No new facts, metrics, or recommendations")
    print("  ✓ Deterministic compression of approved insights")
    print("  ✓ No LLM-generated narrative expansion")
    print()


def show_terminal_commands():
    """Show terminal commands for re-testing."""
    print("=" * 80)
    print("TERMINAL COMMANDS FOR RE-TESTING")
    print("=" * 80)
    print()
    
    print("1. Run this demonstration:")
    print("   python3 tests/demo_tightened_guardrails.py")
    print()
    
    print("2. Test validation logic:")
    print("   python3 -c \"")
    print("   from tests.demo_tightened_guardrails import *")
    print("   show_validation_failure_example()")
    print("   \"")
    print()
    
    print("3. Test with real dataset (check for fallback usage):")
    print("   python3 cli.py test_data/t03_clean_en_platform_device.csv")
    print()
    print("   Look for:")
    print("   - More fallback usage (validation is stricter)")
    print("   - Simpler executive summaries")
    print("   - No causal language in insights")
    print()
    
    print("4. Test via API:")
    print("   python3 api.py")
    print("   # Then upload file via /app or POST /analyze")
    print()
    print("   Check response for:")
    print("   - Cleaner, more observational insights")
    print("   - Deterministic executive summary")
    print("   - No unsupported language")
    print()


def main():
    """Run all demonstrations."""
    show_old_vs_new_output()
    show_validation_failure_example()
    show_deterministic_executive_summary()
    show_terminal_commands()


if __name__ == "__main__":
    main()
