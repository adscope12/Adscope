# Run Command & Sample CSV

## Installation

```bash
pip install -r requirements.txt
```

## Run Command

```bash
python cli.py sample_data.csv
```

### Options

```bash
# Get top 3 insights
python cli.py sample_data.csv --top-n 3

# JSON output
python cli.py sample_data.csv --json
```

## Sample CSV Format

The `sample_data.csv` file contains campaign data with:

**Required columns** (case-insensitive):
- `campaign` - Campaign identifier
- `device` - Device type (Mobile, Desktop)
- `platform` - Platform (Google, Facebook)
- `date` - Date (optional, for temporal patterns)
- `spend` - Ad spend
- `revenue` - Revenue generated
- `clicks` - Number of clicks
- `impressions` - Number of impressions
- `conversions` - Number of conversions

**Computed KPIs** (automatically calculated):
- `ROAS` = revenue / spend
- `CPA` = spend / conversions
- `CTR` = clicks / impressions
- `CVR` = conversions / clicks
- `CPC` = spend / clicks
- `AOV` = revenue / conversions

## Sample Data

The provided `sample_data.csv` includes:
- 3 campaigns (Campaign_A, Campaign_B, Campaign_C)
- 2 devices (Mobile, Desktop)
- 2 platforms (Google, Facebook)
- 2 time periods (2024-01-01, 2024-01-08)
- 18 rows total

## Expected Output

The engine will output **3-4 ranked insights** with:
- Pattern type (SEGMENT_ABOVE_BASELINE, etc.)
- Dimension (campaign/device/platform/time)
- Metric (ROAS, CPA, etc.)
- What happened (neutral phrasing)
- Evidence (supporting data)
- Scores (effect_size, impact, support, composite)

**Diversity**: Insights won't duplicate the same metric/pattern combination.

**Missing KPIs**: If KPIs are missing, statistical support is reduced but insights are still generated (no hard blocks).

## Example Output

```
================================================================================
Top 4 Marketing Insights
================================================================================

1. SEGMENT_ABOVE_BASELINE
   Dimension: campaign
   Metric: roas
   What Happened: Campaign 'Campaign_B' ROAS is +50.0% above baseline
   Evidence: ROAS: 3.00 vs baseline 2.00 (effect size: 0.50)
   Values: Observed=3.0000, Baseline=2.0000
   Scores: effect_size=0.5000, impact=0.7500, support=0.8000, composite=0.6400

2. SEGMENT_GAP
   Dimension: device
   Metric: cpa
   What Happened: Device gap: 'Mobile' CPA +25.0% vs 'Desktop'
   Evidence: Top: 15.00, Bottom: 12.00 (gap effect: 0.25)
   Values: Observed=15.0000, Baseline=12.0000
   Scores: effect_size=0.2500, impact=0.6000, support=0.7000, composite=0.4200

...
```
