# Implementation Changes Summary

## Changes Implemented

### 1. Renamed "Outlier" to "Deviation Signal"
- Updated `SEPARATION.md`: Outlier → Deviation Signal
- Updated all documentation references
- Clarified that deviation signals are intermediate detection results, not final output

### 2. Added Diversity Logic
- Modified `select_top_insights()` in `ranker.py`
- Ensures insights don't duplicate the same metric/pattern combination
- Uses `(pattern_type, metric_name)` as unique key
- Prevents multiple insights for same pattern+metric pair

### 3. Neutral Phrasing
- Updated insight text generation in `_generate_insight_text()`
- Changed "shows" to "is" for more neutral phrasing
- Example: "Campaign 'X' ROAS is +50% above baseline" (not "shows")
- All insights use factual, neutral language

### 4. Missing KPI Handling
- Enhanced `calculate_statistical_support()` in `statistical_support.py`
- Missing KPIs reduce variance_score to 0.3 (not 0.0)
- No hard blocks - patterns still generated with reduced support
- Graceful degradation: missing data reduces score but doesn't prevent insights

### 5. Documentation
- Created `RUN_COMMAND.md` with exact run command and sample CSV format
- Updated all references from "outlier" to "deviation signal"
- Clarified separation: Deviation Signal → Pattern → Insight

## Run Command

```bash
# Install dependencies
pip install -r requirements.txt

# Run engine
python cli.py sample_data.csv

# Options
python cli.py sample_data.csv --top-n 3
python cli.py sample_data.csv --json
```

## Sample CSV

File: `sample_data.csv`
- 18 rows
- 3 campaigns × 2 devices × 2 platforms × 2 time periods
- Columns: campaign, device, platform, date, spend, revenue, clicks, impressions, conversions

## Output

- **3-4 ranked insights** (diverse metric/pattern combinations)
- **Neutral phrasing** (factual, no recommendations)
- **Missing KPI tolerant** (reduces support, no hard blocks)
- **Pattern-first approach** (structural patterns, not raw anomalies)
