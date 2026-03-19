# Phase 1: Pattern Scoring Only

## Overview

Phase 1 implements **scoring for statistical patterns only**. No insights layer, no top-N selection, no narrative fields.

## What Phase 1 Does

1. **Parse CSV** and compute KPIs (ROAS, CPA, Revenue, Spend, CTR, CVR)
2. **Normalize metrics** for pattern detection
3. **Generate pattern candidates** (5 pattern types)
4. **Score each candidate**:
   - `effect_size` (0-1)
   - `business_impact` (0-1)
   - `statistical_support` (0-1)
   - `composite_score = (0.6 * effect_size + 0.4 * business_impact) * statistical_support`
5. **Rank by composite_score** (descending)
6. **Output ranked list** of scored pattern candidates

## Output Format

Each scored pattern candidate includes:
- `pattern_type`: Pattern type (SEGMENT_ABOVE_BASELINE, etc.)
- `pattern_id`: Unique identifier
- `dimension`: campaign/device/platform/time
- `segment`: Segment value
- `metric`: KPI analyzed
- `observed_value`: Observed metric value
- `baseline_value`: Baseline/comparison value
- `effect_size`: Effect size score (0-1)
- `business_impact`: Business impact score (0-1)
- `statistical_support`: Statistical support score (0-1)
- `composite_score`: Composite score (0-1)

**No narrative fields, no recommendations, no "3-4 insights" requirement.**

## Run Command

```bash
# Install
pip install -r requirements.txt

# Run
python cli.py sample_data.csv

# JSON output
python cli.py sample_data.csv --json
```

## Sample CSV

File: `sample_data.csv`
- Columns: campaign, device, platform, date, spend, revenue, clicks, impressions, conversions
- 18 rows with 3 campaigns × 2 devices × 2 platforms × 2 time periods

## Example Output

```
================================================================================
Scored Pattern Candidates (Ranked by Composite Score)
================================================================================

1. SEGMENT_ABOVE_BASELINE
   Pattern ID: SEGMENT_ABOVE_BASELINE_campaign_Campaign_B_roas
   Dimension: campaign
   Segment: Campaign_B
   Metric: roas
   Observed Value: 3.0000
   Baseline Value: 2.0000
   Scores:
     - Effect Size: 0.5000
     - Business Impact: 0.7500
     - Statistical Support: 0.8000
     - Composite Score: 0.6400

2. SEGMENT_GAP
   Pattern ID: SEGMENT_GAP_device_Mobile_Desktop_roas
   Dimension: device
   Segment: Mobile vs Desktop
   Metric: roas
   Observed Value: 2.5000
   Baseline Value: 2.0000
   Scores:
     - Effect Size: 0.2500
     - Business Impact: 0.6000
     - Statistical Support: 0.7000
     - Composite Score: 0.4200

...
```
