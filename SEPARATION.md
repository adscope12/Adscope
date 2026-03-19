# Separation: Deviation Signal → Pattern → Insight

## Definitions

### Deviation Signal
**Numeric deviation in a KPI vs a reference** (baseline/segment/time).

- Raw data point that deviates from expected value
- Example: Campaign_A has ROAS = 3.5 vs baseline 2.0
- **Not the output** - this is the raw deviation detected

### Pattern
**Structured statistical form that classifies deviations.**

Five pattern types:
1. `SEGMENT_ABOVE_BASELINE` - Segment metric above aggregate baseline
2. `SEGMENT_BELOW_BASELINE` - Segment metric below aggregate baseline
3. `SEGMENT_GAP` - Gap between top and bottom segments
4. `TEMPORAL_CHANGE` - Change in metric between time periods
5. `METRIC_IMBALANCE` - Deviation in ratio between two metrics

- **Classification** of the deviation signal into a structured form
- Example: The deviation signal "Campaign_A ROAS 3.5 vs baseline 2.0" becomes pattern `SEGMENT_ABOVE_BASELINE`
- **Generated as candidates** - not yet ranked or formatted

### Insight
**Ranked, human-readable summary derived from the pattern.**

- **What happened** + **Evidence**
- Example: "Campaign 'Campaign_A' shows ROAS +75.0% above baseline. ROAS = 3.50 vs baseline 2.00 (effect size: 0.75)"
- **Output** - top 3-4 ranked insights

## Flow

```
Raw Data
  ↓
[Detect Deviation Signals]
  → Numeric deviations (ROAS 3.5 vs 2.0)
  ↓
[Classify as Patterns]
  → SEGMENT_ABOVE_BASELINE (structured form)
  ↓
[Score Patterns]
  → Effect size + business impact + statistical support
  ↓
[Rank & Format as Insights]
  → "What happened: Campaign_A shows ROAS +75% above baseline. Evidence: ROAS = 3.50 vs baseline 2.00"
```

## Implementation

- **Deviation Signal Detection**: Happens in `pattern_detector.py` when comparing segments to baselines
- **Pattern Classification**: Structured as `PatternType` enum in `pattern_types.py`
- **Insight Generation**: Human-readable text in `ranker.py` (`_generate_insight_text`)
- **Output**: Formatted insights in `formatter.py`
