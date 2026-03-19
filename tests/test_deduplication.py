"""
Minimal test case demonstrating insight deduplication.

This test shows how two duplicate candidates collapse into one.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.models.insight import ScoredPatternCandidate
from src.models.candidate import InsightCandidate
from src.candidate_generation.pattern_types import PatternType
from src.selection.insight_deduplication import build_pattern_signature, deduplicate_insights
from datetime import datetime


def create_test_candidate(
    pattern_id: str,
    dimension: str,
    segment_value: str,
    metric_name: str,
    pattern_type: PatternType,
    observed_value: float,
    baseline_value: float,
    composite_score: float
) -> ScoredPatternCandidate:
    """Helper to create a test ScoredPatternCandidate."""
    candidate = InsightCandidate(
        pattern_type=pattern_type,
        pattern_id=pattern_id,
        description=f"{dimension} {segment_value} {metric_name} test",
        primary_segment={
            'dimension': dimension,
            'value': segment_value,
            'metrics': {metric_name: observed_value},
            'sample_size': 10
        },
        observed_value=observed_value,
        metric_name=metric_name,
        dimensions={dimension: segment_value},
        raw_metrics={
            'primary': {metric_name: observed_value},
            'comparison': None,
            'aggregate': {metric_name: baseline_value}
        },
        sample_sizes={'primary': 10, 'comparison': None},
        variance_metrics={'primary_std': 0.1, 'comparison_std': None},
        tenant_id="test",
        generation_timestamp=datetime.now(),
        baseline_value=baseline_value
    )
    
    return ScoredPatternCandidate(
        candidate=candidate,
        effect_size=0.3,
        business_impact=0.5,
        statistical_support=0.7,
        composite_score=composite_score
    )


def test_deduplication():
    """Test that duplicate candidates collapse into one."""
    print("=" * 70)
    print("TEST: Insight Deduplication")
    print("=" * 70)
    print()
    
    # Create two duplicate candidates (same pattern signature, different scores)
    candidate_a = create_test_candidate(
        pattern_id="test_pattern_1",
        dimension="device",
        segment_value="mobile",
        metric_name="cvr",
        pattern_type=PatternType.SEGMENT_BELOW_BASELINE,
        observed_value=0.02,
        baseline_value=0.03,
        composite_score=0.72  # Higher score
    )
    
    candidate_b = create_test_candidate(
        pattern_id="test_pattern_2",
        dimension="device",
        segment_value="mobile",
        metric_name="cvr",
        pattern_type=PatternType.SEGMENT_BELOW_BASELINE,
        observed_value=0.021,
        baseline_value=0.031,
        composite_score=0.65  # Lower score
    )
    
    # Create one different candidate (different signature)
    candidate_c = create_test_candidate(
        pattern_id="test_pattern_3",
        dimension="platform",
        segment_value="facebook",
        metric_name="cpc",
        pattern_type=PatternType.SEGMENT_BELOW_BASELINE,
        observed_value=0.5,
        baseline_value=0.4,
        composite_score=0.58
    )
    
    # Build signatures
    signature_a = build_pattern_signature(candidate_a)
    signature_b = build_pattern_signature(candidate_b)
    signature_c = build_pattern_signature(candidate_c)
    
    print("INPUT CANDIDATES:")
    print(f"  Candidate A:")
    print(f"    Pattern ID: {candidate_a.candidate.pattern_id}")
    print(f"    Signature: {signature_a}")
    print(f"    Composite Score: {candidate_a.composite_score}")
    print()
    print(f"  Candidate B:")
    print(f"    Pattern ID: {candidate_b.candidate.pattern_id}")
    print(f"    Signature: {signature_b}")
    print(f"    Composite Score: {candidate_b.composite_score}")
    print()
    print(f"  Candidate C:")
    print(f"    Pattern ID: {candidate_c.candidate.pattern_id}")
    print(f"    Signature: {signature_c}")
    print(f"    Composite Score: {candidate_c.composite_score}")
    print()
    
    # Check if signatures match (they should for A and B)
    if signature_a == signature_b:
        print("✓ Candidates A and B have the SAME signature (duplicates)")
    else:
        print("✗ Candidates A and B have DIFFERENT signatures")
    print()
    
    if signature_c != signature_a:
        print("✓ Candidate C has a DIFFERENT signature (not a duplicate)")
    else:
        print("✗ Candidate C has the SAME signature as A")
    print()
    
    # Run deduplication
    input_candidates = [candidate_a, candidate_b, candidate_c]
    deduplicated = deduplicate_insights(input_candidates)
    
    print("=" * 70)
    print("DEDUPLICATION RESULT:")
    print("=" * 70)
    print(f"  Input candidates: {len(input_candidates)}")
    print(f"  Output candidates: {len(deduplicated)}")
    print()
    
    print("OUTPUT CANDIDATES (after deduplication):")
    for i, candidate in enumerate(deduplicated, 1):
        signature = build_pattern_signature(candidate)
        print(f"  {i}. Pattern ID: {candidate.candidate.pattern_id}")
        print(f"     Signature: {signature}")
        print(f"     Composite Score: {candidate.composite_score}")
        print()
    
    # Verify results
    print("=" * 70)
    print("VERIFICATION:")
    print("=" * 70)
    
    if len(deduplicated) == 2:
        print("✓ PASS: Deduplication reduced 3 candidates to 2")
    else:
        print(f"✗ FAIL: Expected 2 candidates, got {len(deduplicated)}")
    
    # Check that candidate A (higher score) was kept
    kept_ids = [c.candidate.pattern_id for c in deduplicated]
    if candidate_a.candidate.pattern_id in kept_ids:
        print("✓ PASS: Candidate A (higher score) was kept")
    else:
        print("✗ FAIL: Candidate A was not kept")
    
    # Check that candidate B (lower score) was removed
    if candidate_b.candidate.pattern_id not in kept_ids:
        print("✓ PASS: Candidate B (lower score) was removed")
    else:
        print("✗ FAIL: Candidate B was not removed")
    
    # Check that candidate C (different signature) was kept
    if candidate_c.candidate.pattern_id in kept_ids:
        print("✓ PASS: Candidate C (different signature) was kept")
    else:
        print("✗ FAIL: Candidate C was not kept")
    
    print()
    print("=" * 70)


if __name__ == "__main__":
    test_deduplication()
