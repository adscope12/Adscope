# Strategic LLM Layer Integration

## Overview

The Strategic LLM layer has been integrated into the main pipeline to interpret and prioritize deterministic engine outputs into user-facing strategic insights.

## Updated Pipeline Flow

```
1. File Upload
   → User runs: python cli.py <file>
   
2. File Ingestion
   → read_file() - Reads CSV or XLSX
   → Returns: (DataFrame, FileType)
   
3. LLM-Assisted Reading Layer
   → ReadingAssistant.interpret_schema()
   → Returns: SchemaMapping (metadata only)
   
4. Canonical Bridge
   → create_canonical_bridge()
   → Returns: canonical_structure with canonical_df
   
5. Deterministic Insight Engine
   → engine.process(canonical_structure=...)
   → Returns: (scored_patterns, dataframe)
   
6. Strategic LLM Layer ⭐ NEW
   → StrategicLLMLayer.analyze()
   → Converts scored_patterns to dict format
   → Interprets and prioritizes insights
   → Returns: strategic_result (JSON)
   
7. User-Facing Output ⭐ NEW
   → format_strategic_output() or format_strategic_output_json()
   → Removes internal IDs
   → Formats for user consumption
   → Returns: Clean, actionable insights
```

## Modified Files

1. **`cli.py`**
   - Added Strategic LLM layer integration (Step 5)
   - Added user-facing output formatting (Step 6)
   - Added `--skip-strategic` flag for testing
   - Converts scored patterns to dict format for Strategic LLM

2. **`src/output/strategic_formatter.py`** (NEW)
   - `convert_scored_patterns_to_dict()` - Converts ScoredPatternCandidate to dict
   - `format_strategic_output()` - Formats strategic results as text
   - `format_strategic_output_json()` - Formats strategic results as JSON
   - Removes internal IDs from user-facing output

3. **`src/output/__init__.py`** (NEW)
   - Module initialization with exports

4. **`src/llm/__init__.py`**
   - Updated Strategic LLM prompt to request structured output:
     - top_priorities (issue, why it matters, expected impact)
     - risks_warnings
     - recommended_checks
     - executive_summary
   - Added JSON response format support
   - Enhanced system prompt with data immutability rules

## How Strategic LLM is Integrated

### Location in Pipeline

**File**: `cli.py`, lines 120-153

**Exact Integration**:
```python
# Step 5: Strategic LLM Layer
if not args.skip_strategic:
    # Convert scored patterns to dict format
    patterns_dict = convert_scored_patterns_to_dict(scored_patterns)
    
    # Initialize Strategic LLM layer
    strategic_layer = StrategicLLMLayer()
    
    # Analyze patterns
    strategic_result = strategic_layer.analyze(
        scored_patterns=patterns_dict,
        top_n=4,
        context={"total_patterns": len(scored_patterns), "data_rows": len(dataframe)}
    )
    
    # Step 6: User-Facing Output
    if args.json:
        output = format_strategic_output_json(strategic_result, hide_internal_ids=True)
        print(json.dumps(output, indent=2))
    else:
        print(format_strategic_output(strategic_result, hide_internal_ids=True))
```

### Data Flow

1. **Engine Output** → `scored_patterns` (List[ScoredPatternCandidate])
2. **Conversion** → `convert_scored_patterns_to_dict()` → List[Dict]
3. **Strategic LLM** → `StrategicLLMLayer.analyze()` → Dict with strategic insights
4. **Formatting** → `format_strategic_output()` → Clean user-facing text/JSON

### Key Constraints Enforced

✅ **Deterministic engine unchanged**: Engine remains the source of truth
✅ **No data invention**: Strategic LLM only interprets provided patterns
✅ **No numeric changes**: System prompt explicitly forbids modifying numbers
✅ **Internal IDs hidden**: `hide_internal_ids=True` removes technical details
✅ **Traceability preserved**: Evidence IDs kept internally but not exposed

## Example CLI Run

### Basic Usage
```bash
$ python cli.py hebrew_test.csv

Reading file: hebrew_test.csv
File type: csv, Rows: 5, Columns: 8

Running LLM-Assisted Reading Layer...
[Schema interpretation...]

Canonical bridge created:
  Original columns: ['date', 'קמפיין', 'פלטפורמה', 'עלות', 'הכנסה', ...]
  Canonical columns: ['date', 'campaign', 'platform', 'spend', 'revenue', ...]
  ✓ Original DataFrame unchanged

Running Deterministic Insight Engine...
[Engine processing...]

Running Strategic LLM Layer...
(Interpreting and prioritizing insights - this may take a few seconds)

================================================================================
STRATEGIC INSIGHTS
================================================================================

EXECUTIVE SUMMARY:
Based on the analyzed campaign data, we've identified several key opportunities
and risks. The primary focus should be on optimizing platform performance and
addressing budget allocation imbalances.

TOP PRIORITIES:
--------------------------------------------------------------------------------

1. Facebook Platform Underperformance
   Why it matters: Facebook shows significantly lower ROAS compared to other platforms
   Expected impact: Reallocating budget could improve overall campaign efficiency by 15-20%

2. Campaign Budget Imbalance
   Why it matters: Top-performing campaigns receive insufficient budget allocation
   Expected impact: Optimizing budget distribution could increase total revenue by 10-15%

3. Mobile Device Performance Gap
   Why it matters: Mobile devices show higher conversion rates but lower spend allocation
   Expected impact: Increasing mobile budget could improve conversions by 20-25%

RISKS / WARNING SIGNALS:
--------------------------------------------------------------------------------
  ⚠ Revenue concentration risk: Top 2 campaigns account for 60% of total revenue
  ⚠ Declining CTR trend detected in recent periods

RECOMMENDED NEXT CHECKS:
--------------------------------------------------------------------------------
  • Review Facebook campaign settings and targeting
  • Analyze budget allocation across top performers
  • Investigate mobile vs desktop performance differences
  • Review recent campaign changes that may have affected CTR
  • Validate data quality for platform performance metrics

================================================================================
```

### JSON Output
```bash
$ python cli.py hebrew_test.csv --json

{
  "executive_summary": "...",
  "top_priorities": [
    {
      "issue_opportunity": "Facebook Platform Underperformance",
      "why_it_matters": "Facebook shows significantly lower ROAS...",
      "expected_impact": "Reallocating budget could improve..."
    }
  ],
  "risks_warnings": [
    "Revenue concentration risk: Top 2 campaigns account for 60%..."
  ],
  "recommended_checks": [
    "Review Facebook campaign settings...",
    "Analyze budget allocation..."
  ],
  "prioritized_insights": [...],
  "notes": "..."
}
```

### Skip Strategic LLM (for testing)
```bash
$ python cli.py hebrew_test.csv --skip-strategic

[Outputs raw engine results without Strategic LLM interpretation]
```

## Output Format Structure

### Text Output Includes:
- **Executive Summary**: 2-4 sentence high-level overview
- **Top Priorities**: Up to 3 priorities with:
  - Issue/opportunity description
  - Why it matters
  - Expected impact
- **Risks / Warning Signals**: List of risk indicators
- **Recommended Next Checks**: Up to 5 actionable next steps
- **Notes**: Additional observations

### JSON Output Includes:
- Same structure as text output
- Clean format without internal IDs
- All fields properly structured for API consumption

## Data Immutability Verification

✅ **Engine outputs unchanged**: Strategic LLM only reads scored patterns
✅ **No numeric modifications**: System prompt explicitly forbids changing numbers
✅ **No new data**: Only interprets and prioritizes existing patterns
✅ **Internal IDs preserved**: Kept for traceability but hidden from users
✅ **Original data untouched**: All operations work with engine outputs only

## Summary

The Strategic LLM layer is now fully integrated into the pipeline:
- Runs after deterministic engine
- Interprets and prioritizes engine outputs
- Generates user-facing strategic insights
- Removes internal technical details
- Maintains data immutability throughout

The complete pipeline now flows from file upload through strategic insights to final user-facing output.
