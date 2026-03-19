# Quick Start - Marketing Insight Engine

## Installation

```bash
pip install -r requirements.txt
```

## Run

```bash
python cli.py sample_data.csv
```

## Sample CSV Format

Required columns (case-insensitive):
- **Dimensions**: `campaign`, `device`, `platform`, `date` (optional)
- **Metrics**: `spend`, `revenue`, `clicks`, `impressions`, `conversions`

The engine will compute:
- **ROAS** = revenue / spend
- **CPA** = spend / conversions
- **CTR** = clicks / impressions
- **CVR** = conversions / clicks

## Output

Top 3-4 insights with:
- Pattern type (SEGMENT_ABOVE_BASELINE, etc.)
- Dimension (campaign/device/platform/time)
- Metric (ROAS, CPA, etc.)
- What happened (human-readable summary)
- Evidence (supporting data)
- Scores (effect_size, impact, support, composite)

## Example Output

```
1. SEGMENT_ABOVE_BASELINE
   Dimension: campaign
   Metric: roas
   What Happened: Campaign 'Campaign_B' shows ROAS +50.0% above baseline
   Evidence: ROAS = 3.00 vs baseline 2.00 (effect size: 0.50)
   Values: Observed=3.0000, Baseline=2.0000
   Scores: effect_size=0.5000, impact=0.7500, support=0.8000, composite=0.6400
```

## Options

```bash
# Get top 3 insights
python cli.py sample_data.csv --top-n 3

# JSON output
python cli.py sample_data.csv --json
```
