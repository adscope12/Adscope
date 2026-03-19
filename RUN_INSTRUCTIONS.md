# Run Instructions

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the Engine

### Basic Usage

```bash
python cli.py sample_data.csv
```

This will process the sample CSV and output the top 4 statistical patterns.

### Options

- `--top-n N`: Return top N insights (default: 4)
- `--json`: Output results as JSON
- `--tenant-id ID`: Specify tenant ID (default: "default")

### Examples

```bash
# Get top 3 insights
python cli.py sample_data.csv --top-n 3

# Get results as JSON
python cli.py sample_data.csv --json

# Specify tenant
python cli.py sample_data.csv --tenant-id "tenant_123"
```

## Sample Data Format

The `sample_data.csv` file contains:
- 3 campaigns (Campaign_A, Campaign_B, Campaign_C)
- 2 devices (Mobile, Desktop)
- 2 platforms (Google, Facebook)
- 2 time periods (2024-01-01, 2024-01-08)
- Metrics: spend, revenue, clicks, impressions, conversions

## Expected Output

The engine will output the top 3-4 statistical patterns, each with:
- Pattern type (SEGMENT_ABOVE_BASELINE, SEGMENT_BELOW_BASELINE, etc.)
- Involved dimension (campaign, device, platform, or time)
- Metric analyzed
- Observed and baseline values
- Scores (effect_size, impact_weight, statistical_support, composite_score)

## Troubleshooting

- **File not found**: Ensure the CSV file path is correct
- **Missing columns**: The engine handles missing KPIs gracefully, but requires at least `spend` and `revenue` for most patterns
- **No insights**: If no patterns are found, check that your data has sufficient variation
