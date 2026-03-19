# Phase 1 Output Format

## Requirements

For each scored PatternCandidate, output must include:
- `pattern_type`: Pattern type (SEGMENT_ABOVE_BASELINE, etc.)
- `dimension`: campaign/device/platform/time
- `metric`: KPI name (roas, cpa, etc.)
- `segment_id`: Segment identifier or group
- `observed_value`: Observed metric value
- `baseline_value`: Baseline/comparison value (can be None)
- `effect_size`: Effect size score (0-1)
- `business_impact`: Business impact score (0-1)
- `statistical_support`: Statistical support score (0-1)
- `composite_score`: Composite score (0-1)

## Scoring Formula

```
composite_score = (0.6 * effect_size + 0.4 * business_impact) * statistical_support
```

All scores are continuous values in [0, 1].

## Output Behavior

- **Full ranked list** kept internally (sorted desc by composite_score)
- **Top 10 patterns** printed for debugging (text output)
- **All patterns** included in JSON output
- No narratives, no recommendations, no "3-4 insights" requirement

## Run Command

```bash
# Text output (top 10 for debugging)
python cli.py sample_data.csv

# JSON output (all patterns)
python cli.py sample_data.csv --json
```

## Example Output

```
================================================================================
Top 10 Scored Pattern Candidates (of 42 total)
Ranked by Composite Score (descending)
================================================================================

1. SEGMENT_ABOVE_BASELINE
   Dimension: campaign
   Segment ID: Campaign_B
   Metric: roas
   Observed Value: 3.000000
   Baseline Value: 2.000000
   Effect Size: 0.500000
   Business Impact: 0.750000
   Statistical Support: 0.800000
   Composite Score: 0.640000

2. SEGMENT_GAP
   Dimension: device
   Segment ID: Mobile_vs_Desktop
   Metric: cpa
   Observed Value: 15.000000
   Baseline Value: 12.000000
   Effect Size: 0.250000
   Business Impact: 0.600000
   Statistical Support: 0.700000
   Composite Score: 0.420000

...
```
