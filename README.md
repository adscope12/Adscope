# Marketing Insight Engine - Phase 1

A stateless CLI-only insight engine that processes campaign CSV data and generates statistically meaningful structural patterns. Focuses on insights (structural deviations), not raw anomalies.

**Key Principles:**
- **Structural Patterns**: Detects meaningful deviations, not z-score anomalies
- **Stateless**: No learning, no memory, no persistence
- **CLI-Only**: No API, no UI, no tenant logic
- **Insight-Focused**: Patterns reflect structural relationships, not just deviation signals

## Features

- **Campaign-Level Processing**: Parses CSV with campaign, device, platform dimensions
- **Core KPI Computation**: ROAS, CPA, Revenue, Spend, CTR, CVR
- **5 Structural Pattern Types** (not raw anomalies):
  - `SEGMENT_ABOVE_BASELINE`: Segment metric above aggregate baseline
  - `SEGMENT_BELOW_BASELINE`: Segment metric below aggregate baseline
  - `SEGMENT_GAP`: Relative difference between top and bottom segments
  - `TEMPORAL_CHANGE`: Change in metric between time periods
  - `METRIC_IMBALANCE`: Deviation between two related metrics (e.g., spend/revenue ratio)

- **Marketing KPIs**: Spend, Revenue, Clicks, Impressions, Conversions, CTR, CVR, CPC, CPA, AOV, ROAS
- **Structural Deviations**: Patterns based on baseline comparisons and segment relationships, not z-score thresholds
- **Graceful Missing Data**: Missing KPIs reduce statistical support, not hard blocks
- **Hybrid Scoring**: Effect size + business impact + statistical support (multiplicative model)
- **Top 3-4 Insights**: Pure ranking-based selection
- **Stateless**: No learning, no memory, no recommendations

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### CLI

```bash
python cli.py sample_data.csv
```

Options:
- `--top-n N`: Number of insights to return (default: 4)
- `--json`: Output as JSON
- `--tenant-id ID`: Tenant identifier (default: "default")

### Example

```bash
# Basic usage
python cli.py sample_data.csv

# Get top 3 insights as JSON
python cli.py sample_data.csv --top-n 3 --json
```

## CSV Format

Expected columns (case-insensitive):
- **Dimensions**: `campaign`, `device`, `platform`, `date` (optional)
- **Metrics**: `spend`, `revenue`, `clicks`, `impressions`, `conversions`

Example:
```csv
campaign,device,platform,date,spend,revenue,clicks,impressions,conversions
Campaign_A,Mobile,Google,2024-01-01,1000,2500,500,10000,50
Campaign_B,Desktop,Facebook,2024-01-01,800,1800,400,8000,40
```

## Output Format

Each insight includes:
- `pattern_type`: Statistical pattern type
- `involved_dimension`: Dimension analyzed (campaign/device/platform/time)
- `metric`: KPI analyzed
- `observed_value`: Observed metric value
- `baseline_value`: Baseline/comparison value
- `effect_size`: Statistical effect size (0-1)
- `impact_weight`: Business impact weight (0-1)
- `statistical_support`: Statistical support strength (0-1)
- `composite_score`: Final ranking score
- `description`: Human-readable description

## Architecture

1. **File Ingestion Layer**: Receive and validate uploaded files
2. **LLM-Assisted Reading Layer**: Interpret inconsistent column names, platform/campaign/KPI naming, handle multilingual naming (Hebrew/English), preserve relevant fields. **CRITICAL**: Does NOT modify raw customer data values (data immutability rule). Outputs canonical mappings for downstream processing.
3. **Canonicalized Internal Structure**: Apply canonical mappings, preserve original data
4. **Feature Extraction**: Parse canonicalized structure (using mappings), calculate KPIs
5. **Normalization**: Standardize metrics for comparison
6. **Deterministic Insight Engine**: Generate, score, and rank statistical pattern candidates (the ONLY component that computes insights, scores, and statistical candidates)
7. **Strategic LLM Layer**: Interpret scored patterns into strategic insights (runs after deterministic engine)
8. **User-Facing Output Layer**: Format and deliver insights to users

### Data Immutability Rule

The LLM-Assisted Reading Layer follows a strict **data immutability rule**:
- The LLM MUST NOT modify raw customer data values (numbers, text records, metrics)
- The LLM may only interpret schema and suggest mappings
- Original uploaded data must remain untouched and recoverable
- Only schema-level mappings are created; actual data values pass through unchanged

### Privacy-Preserving Learning

The system improves over time without storing customer data:
- Only abstract mapping patterns are stored (e.g., "column names like 'cost' map to 'spend'")
- No raw customer rows, metric values, or client-specific content is stored
- Learning happens through schema-level patterns, not client data

## Notes

- Missing KPIs are handled gracefully - they reduce statistical support but don't block pattern generation
- Small samples (n < 10) avoid p-values and use effect size proxies
- Epsilon floor (0.001) prevents micro-noise patterns
- No business interpretation layer - patterns are pure statistical structures
