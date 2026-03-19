# Grounded Narrative Layer Integration

## Overview

The Grounded Narrative Layer constrains LLM phrasing to only use facts detected by the deterministic engine. It prevents the LLM from inventing new patterns, metrics, segments, or recommendations.

## Pipeline Integration

### Exact Location

**File:** `src/pipeline/pipeline_runner.py`

**Inserted After:** STEP 4.6 (Insight Deduplication Layer)  
**Inserted Before:** STEP 6 (Strategic LLM Layer - Fallback)

```python
# Lines 364-415 in src/pipeline/pipeline_runner.py

# ============================================================
# STEP 4.6: Insight Deduplication Layer
# ============================================================
deduplicated_patterns = deduplicate_insights(validated_patterns)

# ============================================================
# STEP 5: Grounded Narrative Layer  ← NEW LAYER
# ============================================================
grounded_phrased_insights = []
if not skip_strategic:
    try:
        grounded_layer = GroundedNarrativeLayer()
        grounded_phrased_insights = grounded_layer.phrase_insights(
            scored_candidates=deduplicated_patterns,
            top_n=max_insights
        )
    except Exception as e:
        # Fallback to Strategic LLM if grounded narrative fails
        grounded_phrased_insights = []

# ============================================================
# STEP 6: Strategic LLM Layer (Fallback/Executive Summary)
# ============================================================
if grounded_phrased_insights:
    # Use grounded insights
    strategic_result = _build_strategic_result_from_grounded(...)
else:
    # Fallback to original Strategic LLM
    strategic_result = strategic_layer.analyze(...)
```

### Updated Pipeline Flow

```
candidate_generation
→ candidate_scoring
→ insight_validation (STEP 4.5)
→ insight_deduplication (STEP 4.6)
→ grounded_narrative_phrasing (STEP 5) ← NEW
→ strategic_llm_fallback (STEP 6) ← Modified
→ user_facing_output (STEP 7)
```

## Files Created

1. **`src/narrative/grounded_payload.py`**
   - `build_structured_insight_payload()`: Builds deterministic payload from scored candidates
   - Extracts: dimension, segment, comparison_target, metrics, direction, values, scores
   - Determines: safe_business_interpretation, safe_action_hint, allowed_narrative_tags

2. **`src/narrative/narrative_tags.py`**
   - `get_narrative_tags_for_pattern()`: Returns allowed narrative tags per pattern type
   - Tags constrain LLM phrasing style (e.g., "outperforming segment", "efficiency drag")

3. **`src/narrative/grounded_phrasing.py`**
   - `GroundedNarrativeLayer`: Main class for grounded LLM phrasing
   - `phrase_insights()`: Phrases each insight with strict constraints
   - Uses structured payload + narrative tags + validation + fallback

4. **`src/narrative/phrasing_validation.py`**
   - `validate_phrased_insight()`: Validates LLM output against structured payload
   - Checks: metrics exist, segments exist, no unsupported causes/recommendations

5. **`src/narrative/fallback_template.py`**
   - `generate_fallback_phrasing()`: Deterministic template-based phrasing
   - Used when LLM fails or validation fails

6. **`src/narrative/__init__.py`**
   - Module exports

## Files Modified

1. **`src/pipeline/pipeline_runner.py`**
   - Added import: `from src.narrative import GroundedNarrativeLayer`
   - Added STEP 5: Grounded Narrative Layer
   - Added helper: `_build_strategic_result_from_grounded()`
   - Modified STEP 6: Strategic LLM Layer (now fallback only)

## Structured Insight Payload Structure

```json
{
  "pattern_id": "test_device_mobile_cvr",
  "pattern_type": "SEGMENT_BELOW_BASELINE",
  "dimension": "device",
  "segment": "mobile",
  "comparison_target": "baseline",
  "primary_metric": "cvr",
  "secondary_metrics": ["cpa", "spend"],
  "direction": "negative",
  "observed_value": 0.02,
  "baseline_value": 0.03,
  "effect_size": 0.35,
  "business_impact": 0.65,
  "statistical_support": 0.75,
  "composite_score": 0.7,
  "safe_business_interpretation": "This segment shows weaker performance than the comparison target.",
  "safe_action_hint": "Review device-specific targeting and budget allocation.",
  "allowed_narrative_tags": [
    "efficiency drag",
    "weaker conversion economics",
    "underperforming segment",
    "optimization needed"
  ]
}
```

## Grounded LLM Output Format

Each insight returns:

```json
{
  "headline": "Mobile is underperforming baseline",
  "what_is_happening": "Mobile shows weaker CVR than baseline, with 0.02 vs 0.03 (33% difference).",
  "why_it_matters": "This indicates optimization opportunities to improve efficiency.",
  "next_check": "Review device-specific targeting and budget allocation."
}
```

## Fallback Template Output

When LLM fails or validation fails, deterministic template generates:

```json
{
  "headline": "Mobile is underperforming baseline",
  "what_is_happening": "Mobile shows weaker CVR than baseline, with 0.02 vs 0.03 (33% difference).",
  "why_it_matters": "This indicates optimization opportunities to improve efficiency.",
  "next_check": "Review device-specific targeting and budget allocation."
}
```

## Narrative Tags by Pattern Type

- **winning_segment**: "outperforming segment", "stronger efficiency", "better return on spend"
- **underperforming_segment**: "efficiency drag", "weaker conversion economics", "optimization needed"
- **temporal_spike**: "sudden disruption", "unusual movement", "requires investigation"
- **gradual_decline**: "weakening over time", "deteriorating efficiency", "trend worth addressing early"
- **recovery_pattern**: "signs of recovery", "improving efficiency", "regained momentum"
- **weekend_gap**: "day-of-week performance gap", "weaker weekend efficiency", "scheduling opportunity"

## Validation Rules

The validation layer checks:
- Every mentioned metric exists in structured payload
- Every mentioned segment exists in structured payload
- No unsupported cause phrases ("because of", "due to", etc.) unless in safe_business_interpretation
- No unsupported recommendations beyond safe_action_hint

## Testing

Run the test to see examples:

```bash
python3 tests/test_grounded_narrative.py
```

This demonstrates:
1. Structured insight payload structure
2. Fallback template output
3. Expected grounded LLM output format

## Integration Behavior

- **Primary Path**: Grounded narrative phrases insights → converts to strategic result format
- **Fallback Path**: If grounded narrative fails → falls back to original Strategic LLM
- **Both paths** maintain compatibility with existing API response format

## Constraints Preserved

✅ Deterministic scoring and ranking unchanged  
✅ Deduplication layer unchanged  
✅ FULL MODE and PERFORMANCE MODE support unchanged  
✅ No new services or databases  
✅ No architecture refactoring  
✅ Simple MVP-friendly implementation
