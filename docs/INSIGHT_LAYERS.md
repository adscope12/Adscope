# Insight Layers and Deduplication

## Overview

The Marketing Insight Engine uses a layered approach to organize business insights, with explicit deduplication rules to prevent overlapping insights in the final output.

## Insight Layers

### Tier 1: Single-Signal Insights

**Definition**: Directly mapped from a single pattern type and metric.

**Characteristics**:
- Triggered by a single `PatternCandidate`
- Direct mapping from pattern type (e.g., `SEGMENT_ABOVE_BASELINE`, `SEGMENT_GAP`)
- No cross-metric or share calculations required

**Examples**:
- `segment_performance_gap`: Gap between segments on ROAS/revenue/conversions
- `segment_above_baseline`: Segment performing above baseline (ROAS/revenue/conversions)
- `segment_below_baseline`: Segment performing below baseline (ROAS/revenue/conversions)
- `spend_revenue_imbalance`: Imbalance between spend and revenue

### Tier 2: Composite Insights

**Definition**: Combine multiple signals, share calculations, or cross-metric logic.

**Characteristics**:
- Require multiple `PatternCandidates` or direct dataframe analysis
- May involve share calculations (spend_share, revenue_share, conversions_share)
- Cross-metric relationships (e.g., CTR high but CVR low)
- Temporal analysis (e.g., platform performance at same time window)

**Examples**:
- `underfunded_winner`: High ROAS segment with low spend share (< 30%)
- `high_volume_low_value`: Conversions increase but revenue per conversion decreases
- `leakage_detection`: High CTR but low CVR (funnel leakage)
- `budget_saturation_signal`: Spend increases without proportional efficiency gains
- `platform_time_mismatch`: Different platforms perform differently in same time window

### Meta: Rollup Insights

**Definition**: Summarize or aggregate other insights.

**Characteristics**:
- Triggered when multiple other insights are present
- Do not consume diversity slots
- Always appended last in the output
- Provide high-level risk/opportunity summaries

**Examples**:
- `risk_flags`: Early warning when multiple risk insights trigger (sustained_decline, performance_volatility, revenue_concentration_risk, platform_dependency_risk)

## Suppression Rules

### Principle

**If a Tier 2 insight is triggered, it suppresses the weaker Tier 1 insights that are "explained by it".**

This prevents redundant output where a composite insight already captures the information from simpler single-signal insights.

### Suppression Map

The following Tier 2 insights suppress related Tier 1 insights when triggered:

| Tier 2 Insight | Suppresses Tier 1 Insight | Condition |
|---------------|---------------------------|-----------|
| `underfunded_winner` | `segment_above_baseline` | Same segment, ROAS metric |
| `overfunded_underperformer` | `segment_below_baseline` | Same segment, ROAS metric |
| `hidden_high_performer` | `segment_above_baseline` | Same segment, ROAS metric |
| `conversion_efficiency_gap` | `segment_above_baseline`, `segment_below_baseline` | Same segment, CTR/CVR metrics |
| `high_volume_low_value` | `segment_above_baseline`, `segment_below_baseline` | Same segment, conversions/revenue metrics |
| `leakage_detection` | `segment_above_baseline`, `segment_below_baseline` | Same segment, CTR/CVR metrics |
| `budget_saturation_signal` | `segment_above_baseline` | Same segment, spend metric |
| `creative_fatigue_signal` | `segment_below_baseline` | Same segment, CTR metric |

### Suppression Logic

1. **Segment Matching**: Suppression applies when insights share the same `segment_id` or have overlapping segments (e.g., "A_vs_B" contains "A").

2. **Metric Relevance**: For specific suppressions, metric relevance is checked:
   - ROAS-related suppressions only apply to ROAS metrics
   - CTR/CVR-related suppressions only apply to CTR/CVR metrics
   - Conversions/revenue-related suppressions only apply to conversions/revenue metrics

3. **Precedence**: Tier 2 insights always take precedence over Tier 1 insights when both are triggered for the same segment/metric combination.

### Meta Insights

**Meta insights (e.g., `risk_flags`) do NOT suppress other insights.** They are:
- Appended last in the output
- Do not consume diversity slots (max 1 per segment_id)
- Provide additional context without replacing specific insights

## Selection Pipeline

The insight selection pipeline follows this order:

1. **Quality Gates**: Apply hard thresholds (composite_score >= 0.15, support >= 0.35, effect_size >= 0.02)

2. **Build Insight Candidates**: 
   - Tier 1: Map from PatternCandidates
   - Tier 2: Compute from dataframe and candidates
   - Meta: Compute after Tier 2 insights are collected

3. **Apply Suppression**: Remove Tier 1 insights that are suppressed by Tier 2 insights

4. **Diversity Selection**: 
   - Max 1 insight per `segment_id`
   - Applied to Tier 1 and Tier 2 insights only
   - Meta insights are excluded from diversity constraints

5. **Append Meta Insights**: Add Meta insights last (do not consume diversity slots)

6. **Return Results**: Up to 4 insights (quality-gated; may return fewer)

## Output Rules

- **Maximum Insights**: Up to 4 insights (default)
- **Quality Gates**: All insights must pass quality gates (composite_score, support, effect_size)
- **May Return Fewer**: If fewer than 4 insights pass quality gates, return only those that pass
- **No Bluffing**: Never return low-quality insights to fill the quota
- **Diversity**: Max 1 insight per segment_id (applied before Meta insights)
- **Meta Insights**: Always appended last, do not count toward diversity limits

## Debug Output

When `debug=True`, the output includes:

- **Definitions Triggered**: Count of candidates matched per insight definition
- **Suppressed Insights**: List of Tier 1 insights suppressed by Tier 2 insights
  - Format: `{suppressed_id} suppressed by {suppressed_by_id}`
- **Meta Insights**: List of Meta insights appended (with note that they don't consume diversity slots)
- **Tier 2 Share Values**: Share calculations used in Tier 2 insights

## Example

**Scenario**: 
- Tier 1: `segment_above_baseline` triggered for segment "A" with ROAS metric
- Tier 2: `underfunded_winner` triggered for segment "A" (high ROAS, low spend share)

**Result**:
- `underfunded_winner` is included in output
- `segment_above_baseline` is suppressed (explained by `underfunded_winner`)
- Debug output shows: `segment_above_baseline suppressed by underfunded_winner`

## Configuration

The suppression map is defined in `src/business_insights/mapper.py`:

```python
SUPPRESSION_MAP: Dict[str, List[str]] = {
    "underfunded_winner": ["segment_above_baseline"],
    "overfunded_underperformer": ["segment_below_baseline"],
    # ... (see mapper.py for full list)
}

META_INSIGHTS = {"risk_flags"}
```

## Registry

The insight registry (`src/business_insights/registry.py`) contains exactly 23 approved insights:
- 6 Tier 1 insights
- 16 Tier 2 insights  
- 1 Meta insight (`risk_flags`)

The registry is frozen and validated on import to ensure it matches the approved set.
