# Implementation Summary - Marketing Insight Engine Phase 1

## Architecture Overview

**Stateless, CLI-only Marketing Insight Engine** that processes campaign CSV data and generates structural insights (not raw anomalies).

### Core Principles
- ✅ **Structural Patterns**: Detects meaningful deviations based on baseline comparisons and segment relationships
- ✅ **Stateless**: No learning, no memory, no persistence
- ✅ **CLI-Only**: No API, no UI, no tenant logic
- ✅ **Insight-Focused**: Patterns reflect structural relationships, not z-score thresholds

## Pipeline

```
[File Ingestion Layer]
  → Receive uploaded file
  ↓
[LLM-Assisted Reading Layer]
  → Interpret inconsistent column names, platform/campaign/KPI naming
  → Handle Hebrew/English/typos/mixed naming
  → Preserve relevant extra fields
  → CRITICAL: Does NOT modify raw customer data values (data immutability)
  → Output: Canonical mappings + original data (unchanged)
  ↓
[Canonicalized Internal Structure]
  → Apply canonical mappings, preserve original data
  ↓
[Feature Extraction]
  → Parse canonicalized structure, compute KPIs (ROAS, CPA, Revenue, Spend, CTR, CVR)
  ↓
[Normalization]
  → Standardize metrics for pattern detection
  ↓
[Deterministic Insight Engine]
  → Candidate Generation → Scoring → Selection
  → Top 3-4 Scored Pattern Candidates
  ↓
[Strategic LLM Layer]
  → Interpret scored patterns into strategic insights
  ↓
[User-Facing Output Layer]
  → Format and deliver insights to users
```

## Data Immutability Rule

The LLM-Assisted Reading Layer follows a strict **data immutability rule**:
- The LLM MUST NOT modify raw customer data values (numbers, text records, metrics)
- The LLM may only interpret schema and suggest mappings
- Original uploaded data must remain untouched and recoverable
- Only schema-level mappings are created; actual data values pass through unchanged

## Privacy-Preserving Learning

The system improves over time without storing customer data:
- Only abstract mapping patterns are stored (e.g., "column names like 'cost' map to 'spend'")
- No raw customer rows, metric values, or client-specific content is stored
- Learning happens through schema-level patterns, not client data

## Pattern Types (Structural, Not Anomalies)

1. **SEGMENT_ABOVE_BASELINE**: Segment metric above aggregate baseline
   - Structural: Compares segment mean to overall baseline
   - Not anomaly: Uses baseline comparison, not z-score threshold

2. **SEGMENT_BELOW_BASELINE**: Segment metric below aggregate baseline
   - Structural: Compares segment mean to overall baseline
   - Not anomaly: Uses baseline comparison, not z-score threshold

3. **SEGMENT_GAP**: Relative difference between top and bottom segments
   - Structural: Compares extreme segments within dimension
   - Not anomaly: Focuses on relationship, not outlier detection

4. **TEMPORAL_CHANGE**: Change in metric between time periods
   - Structural: Compares latest vs previous period
   - Not anomaly: Detects shifts, not point anomalies

5. **METRIC_IMBALANCE**: Deviation in ratio between two metrics
   - Structural: Compares spend/revenue ratio to baseline
   - Not anomaly: Focuses on relationship imbalance, not single-metric outlier

## Key Implementation Details

### Pattern Detection (Not Anomaly Detection)
- Uses **baseline comparisons** (aggregate means), not z-score thresholds
- Focuses on **structural relationships** (segment comparisons, temporal changes)
- Generates **meaningful deviation signals**, not statistical outliers

### Scoring Model
- **Effect Size**: Magnitude of deviation (relative differences, not z-scores)
- **Business Impact**: Revenue/spend magnitude, scale factor, KPI importance
- **Statistical Support**: Sample adequacy, variance, significance (avoids p-values for n < 10)
- **Composite**: `(effect_size * 0.6 + impact * 0.4) * statistical_support`

### Missing Data Handling
- Missing KPIs reduce statistical support, not hard blocks
- Graceful degradation: patterns still generated if some KPIs missing

### Stateless Design
- No tenant logic (removed)
- No learning/memory
- No persistence
- Pure function: CSV → Insights

## File Structure

```
src/
├── feature_extraction/    # CSV parsing, KPI calculation
├── normalization/         # Metric standardization
├── candidate_generation/ # Structural pattern detection
├── scoring/              # Effect size, impact, support, composite
├── selection/           # Ranking and formatting
├── models/               # Data structures
└── engine.py             # Main orchestration

cli.py                    # CLI interface
test_engine.py            # Test script
sample_data.csv           # Sample campaign data
```

## Usage

```bash
# Install
pip install -r requirements.txt

# Run
python cli.py sample_data.csv

# Options
python cli.py sample_data.csv --top-n 3 --json
```

## Output Format

Each insight includes:
- `pattern_type`: Structural pattern type
- `involved_dimension`: campaign/device/platform/time
- `metric`: KPI analyzed
- `observed_value`: Observed metric value
- `baseline_value`: Baseline/comparison value
- `effect_size`: Statistical effect size (0-1)
- `impact_weight`: Business impact (0-1)
- `statistical_support`: Statistical support strength (0-1)
- `composite_score`: Final ranking score
- `description`: Human-readable description

## Testing

```bash
python test_engine.py
```

## Notes

- **Not an anomaly detector**: Patterns are structural deviation signals, not z-score outliers
- **No business recommendations**: Pure statistical patterns
- **No learning**: Stateless, deterministic
- **CLI-only**: No API, no UI, no tenant logic
