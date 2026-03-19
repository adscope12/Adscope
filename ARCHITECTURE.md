# Insight Engine Architecture

## Overview
A Statistical Pattern Ranking Engine that processes marketing campaign data and identifies statistically meaningful deviations, ranking them by effect size, business impact, and statistical support. The engine focuses on pure statistical structures; business interpretation is layered on top in a separate phase.

## Core Principles
- **No hard thresholds** - Continuous scoring only
- **No action recommendations** - Pure insight ranking
- **No artificial minimums** - All insights considered
- **No rule-based gating** - All pattern types enabled
- **Clean tenant isolation** - Minimal, clear boundaries

## LLM Layer Architecture

The system uses **two distinct LLM layers** at different stages:

### 1. LLM-Assisted Reading Layer (Before Deterministic Engine)
**Position**: Runs immediately after file upload, before feature extraction
**Purpose**: Interpret and normalize inconsistent file structure

**Responsibilities**:
- Interpret inconsistent column names (e.g., "campaign_name" vs "campaign" vs "Campaign")
- Interpret inconsistent platform/campaign/KPI naming (e.g., "Google Ads" vs "Google" vs "גוגל")
- Handle multilingual naming (Hebrew/English) and typos
- Handle mixed naming conventions and abbreviations
- Preserve potentially relevant extra fields instead of discarding them
- Suggest canonical mappings for fields and values
- Classify fields (dimension vs metric vs metadata)
- Identify uncertain fields requiring caution

**CRITICAL: Data Immutability Rule**
The LLM **MUST NOT** modify raw customer data values. This is a fundamental architectural constraint:

**What the LLM MUST NOT do**:
- ❌ Change numbers (metric values, counts, amounts)
- ❌ Rewrite textual field values that are actual data records (campaign names, platform names, etc.)
- ❌ "Correct" metric values
- ❌ Estimate missing values
- ❌ Fabricate or interpolate any client data
- ❌ Generate business insights
- ❌ Compute scores or metrics
- ❌ Replace the deterministic engine
- ❌ Delete fields aggressively
- ❌ Make business decisions
- ❌ Analyze business performance directly from raw client data

**What the LLM MAY do**:
- ✅ Interpret schema (column names, structure)
- ✅ Suggest mappings (column name → canonical name)
- ✅ Normalize labels conceptually (e.g., "Google Ads" → canonical "google")
- ✅ Classify fields (dimension, metric, metadata)
- ✅ Identify uncertainty (flag ambiguous fields)
- ✅ Preserve original data exactly (all transformations are reversible)

**Data Preservation Requirements**:
- Original uploaded data must remain untouched and recoverable
- All transformations must preserve the original data exactly
- Mapping information is metadata only - actual data values pass through unchanged
- The reading layer outputs a mapping structure, not modified data

**Output**: Canonical column mappings, value normalization mappings (categorical only), field classifications, preserved relevant fields, uncertain field flags, original data reference (unchanged)

### 2. Strategic LLM Layer (After Deterministic Engine)
**Position**: Runs after the deterministic insight engine has scored patterns
**Purpose**: Interpret scored patterns into strategic insights
**Responsibilities**:
- Take scored patterns from the deterministic engine
- Prioritize and synthesize into actionable insights
- Provide strategic interpretation of statistical patterns
- Generate recommendations based on scored patterns

**Constraints**:
- ❌ Does NOT invent new data or metrics
- ❌ Only uses provided scored patterns
- ❌ Does NOT replace the deterministic engine

**Output**: Prioritized strategic insights, recommendations, executive summaries

**Key Separation**: The reading layer handles **data interpretation** (before processing), while the strategic layer handles **insight interpretation** (after processing). They operate at completely different stages and serve different purposes.

**Data Immutability**: The reading layer interprets structure only - it never modifies customer data values. All numeric values, text records, and metric data pass through unchanged. Only schema-level mappings are created.

## Key Architectural Clarifications

### 1. Pattern Definition
A **Pattern** is a statistically detectable deviation or relationship in normalized campaign data, characterized by:
- A primary data segment (focus of the pattern)
- An optional comparison point (baseline, segment, or time period)
- One or more metrics (KPIs) exhibiting the deviation
- Dimensions defining segment boundaries
- **Pure statistical structure** - no business interpretation at pattern level

Pattern types (Phase 1 - Statistical Structures): 
- SEGMENT_ABOVE_BASELINE, SEGMENT_BELOW_BASELINE, SEGMENT_GAP, TEMPORAL_CHANGE, METRIC_IMBALANCE

### 2. InsightCandidate Structure
Complete structure defined below with all fields including:
- Pattern identification (type, ID)
- Narrative description
- Data points (primary/comparison segments, values)
- Dimensions and context
- Raw metrics for scoring
- Statistical metadata (sample sizes, variance)
- Tenant and timestamp metadata

### 3. Scoring Calculations
- **Effect Size**: Relative difference, Cohen's d, log ratios, correlation coefficients (continuous 0-1)
- **Business Impact**: Revenue/spend magnitude, scale factor, KPI importance (continuous 0-1)
- **Statistical Support**: Sample adequacy, variance, significance, consistency (continuous 0-1)
- **Composite**: Hybrid multiplicative-additive model (statistical support as multiplier, effect + impact as base)

### 4. Normalized Metrics Layer
New layer between Feature Extraction and Candidate Generation that:
- Standardizes KPIs to comparable scales
- Handles missing data
- Creates dimension hierarchies
- Standardizes time periods
- Enables cross-dimensional pattern detection

### 5. Noise Avoidance
**Strategy**: Continuous scoring naturally deprioritizes noise without blocking
- Multiplicative statistical support prevents weak signals from surviving
- Minimal signal floor (ε = 0.001) prevents micro-noise computationally
- Low scores in any dimension → lower composite → lower rank
- Top 3-4 selection excludes low-scoring noise
- No hard cutoffs - pure ranking approach
- Multi-dimensional scoring requires strength across dimensions

### 6. Pattern Generation Philosophy
**Statistical Core, Neutral Generation**:
- **Target**: < 60 candidates for 20-40 row datasets
- **Statistical structures**: Patterns are pure deviations, not business narratives
- **Balanced deviations**: Equal focus on above-baseline and below-baseline
- **Single-dimension focus**: No cross-dimensional combinations
- **Extreme segments**: Focus on top 1 and bottom 1 segments per dimension
- **Primary KPIs**: ROAS, CPA, Revenue, Spend (core metrics)
- **Baseline comparisons**: Segments vs. aggregate, not exhaustive pairings
- **Metric relationships**: Detect imbalances between related metrics
- **Temporal changes**: Detect shifts between time periods (direction neutral)
- **Business interpretation**: Applied later, not in pattern generation
- Final selection filters to top 3-4 strongest insights

## Architecture Layers

### 0. File Ingestion Layer
**Purpose**: Receive and validate uploaded files from clients

**Responsibilities**:
- Accept file uploads (CSV, Excel, etc.)
- Validate file format and basic structure
- Pass files to LLM-Assisted Reading Layer for interpretation
- Track file metadata (size, upload timestamp, format) - NO client data content

**Input**: Raw uploaded file from client
**Output**: Validated file ready for reading layer processing

**Files** (to be implemented):
- `src/ingestion/file_handler.py` - File upload and validation

---

### 1. LLM-Assisted Reading Layer
**Purpose**: Interpret and normalize inconsistent file structure before deterministic processing

**Responsibilities**:
- Interpret inconsistent column names (e.g., "campaign_name" vs "campaign" vs "Campaign")
- Interpret inconsistent platform/campaign/KPI naming (e.g., "Google Ads" vs "Google" vs "גוגל")
- Handle multilingual naming (Hebrew/English) and typos
- Handle mixed naming conventions and abbreviations
- Preserve potentially relevant extra fields instead of discarding them
- Suggest canonical mappings for fields and values
- Classify fields (dimension vs metric vs metadata)
- Identify uncertain fields requiring caution
- Prepare input into cleaner canonical structure

**CRITICAL: Data Immutability Rule**
The LLM **MUST NOT** modify raw customer data values. This is a fundamental architectural constraint:

**What the LLM MUST NOT do**:
- ❌ Change numbers (metric values, counts, amounts)
- ❌ Rewrite textual field values that are actual data records (campaign names, platform names, etc.)
- ❌ "Correct" metric values
- ❌ Estimate missing values
- ❌ Fabricate or interpolate any client data
- ❌ Generate business insights
- ❌ Compute scores or metrics
- ❌ Replace the deterministic engine
- ❌ Delete fields aggressively
- ❌ Make business decisions
- ❌ Analyze business performance directly from raw client data

**What the LLM MAY do**:
- ✅ Interpret schema (column names, structure)
- ✅ Suggest mappings (column name → canonical name)
- ✅ Normalize labels conceptually (e.g., "Google Ads" → canonical "google")
- ✅ Classify fields (dimension, metric, metadata)
- ✅ Identify uncertainty (flag ambiguous fields)
- ✅ Preserve original data exactly (all transformations are reversible)

**Data Preservation Requirements**:
- Original uploaded data must remain untouched and recoverable
- All transformations must preserve the original data exactly
- Mapping information is metadata only - actual data values pass through unchanged
- The reading layer outputs a mapping structure, not modified data

**Output Structure**:
- Canonical column mappings (original column name → canonical name)
- Value normalization mappings (original value → canonical value) for categorical fields only
- Field classifications (dimension, metric, metadata, uncertain)
- Additional relevant fields (preserved for potential use)
- Uncertain fields requiring caution (flagged for review)
- Original data reference (untouched, recoverable)

**Input**: Raw uploaded CSV file (with inconsistent naming)
**Output**: Canonicalized structure with mappings + original data (unchanged)

**Files** (to be implemented):
- `src/llm/reading_layer.py` - LLM-assisted file reading and interpretation

**Note**: This layer runs BEFORE the deterministic insight engine. The strategic LLM layer (which interprets scored patterns) runs AFTER the deterministic engine.

---

### 2. Canonicalized Internal Structure
**Purpose**: Apply mappings from reading layer to create standardized internal representation

**Responsibilities**:
- Apply canonical column name mappings
- Apply canonical value mappings (for categorical fields only)
- Preserve original data alongside canonical structure
- Create standardized data structure for deterministic engine
- Maintain traceability back to original data

**Input**: Original data + canonical mappings from reading layer
**Output**: Canonicalized data structure (with original data preserved)

**Files** (to be implemented):
- `src/normalization/canonicalizer.py` - Apply canonical mappings

---

### 3. Feature Extraction Layer
**Purpose**: Transform canonicalized data into structured KPI features

**Responsibilities**:
- Parse canonicalized data structure (using mappings from reading layer)
- Calculate core KPIs (ROAS, CPA, CTR, CVR, AOV, Spend, Revenue, etc.)
- Structure data for analysis
- Handle tenant isolation at data level
- **Note**: Does NOT normalize metrics (that's the next layer)
- **Note**: Works with canonical column names from reading layer
- **Note**: Uses original data values (only structure is canonicalized)

**Input**: Canonicalized data structure (with original data preserved)
**Output**: Raw feature set with computed KPIs

**Files**:
- `src/feature_extraction/parser.py` - CSV parsing
- `src/feature_extraction/kpi_calculator.py` - KPI computation
- `src/feature_extraction/feature_set.py` - Feature structure

---

### 4. Normalized Metrics Layer
**Purpose**: Standardize metrics across different scales and dimensions for pattern detection

**Responsibilities**:
- Normalize KPIs to comparable scales (z-scores, percentiles, or relative scales)
- Handle missing data gracefully (imputation or exclusion flags)
- Create dimension hierarchies (device → platform, campaign → ad group, etc.)
- Standardize time periods for temporal comparisons
- Create normalized metric views that enable cross-dimensional pattern detection
- **No filtering** - all data points are normalized, none are excluded

**Input**: Raw feature set with KPIs
**Output**: Normalized feature set with standardized metrics

**Files**:
- `src/normalization/metric_normalizer.py` - KPI normalization logic
- `src/normalization/dimension_standardizer.py` - Dimension hierarchy creation
- `src/normalization/temporal_normalizer.py` - Time period standardization
- `src/normalization/normalized_set.py` - Normalized data structure

---

### 5. Candidate Generation Layer
**Purpose**: Generate statistical pattern structures through guided, focused generation

**Philosophy**: 
- **Guided, not exhaustive** - Only generate statistically meaningful deviations
- **Statistical structures** - Focus on measurable deviations (above/below baseline, gaps, temporal changes, metric imbalances)
- **No combinatorial exploration** - Avoid cross-dimensional combinations
- **Neutral patterns** - No business interpretation at generation level
- **Target < 60 candidates** for 20-40 row datasets

**Responsibilities**:
- Generate only statistical pattern types (see Phase 1 patterns below)
- Focus on primary dimensions (campaign, device, platform) individually
- Create segment vs. baseline deviations (above and below)
- Generate segment gaps (top vs. bottom)
- Generate temporal changes if temporal data exists
- Generate metric imbalances (two-metric deviations)
- Create pattern descriptors with metadata
- **Do NOT** generate exhaustive combinations or cross-dimensional patterns
- **Do NOT** apply business interpretation or naming

**Input**: Normalized feature set with standardized metrics
**Output**: List of pattern candidates (target: < 60 for typical dataset)

**Files**:
- `src/candidate_generation/pattern_detector.py` - Statistical pattern detection logic
- `src/candidate_generation/pattern_types.py` - Statistical pattern type definitions
- `src/candidate_generation/candidate.py` - Candidate data structure

---

### 6. Scoring Layer
**Purpose**: Score each candidate using continuous metrics

**Responsibilities**:
- Calculate statistical effect size (Cohen's d, relative difference, etc.)
- Calculate business impact weight (revenue impact, spend magnitude, etc.)
- Calculate statistical support strength (p-values, confidence intervals, sample sizes)
- Combine scores into composite ranking score
- **No thresholds** - all scores are continuous

**Input**: Insight candidates
**Output**: Scored candidates with ranking metrics

**Files**:
- `src/scoring/effect_size.py` - Statistical effect size calculations
- `src/scoring/business_impact.py` - Business impact scoring
- `src/scoring/statistical_support.py` - Statistical significance metrics
- `src/scoring/composite_scorer.py` - Combined scoring logic

---

### 7. Selection Layer
**Purpose**: Select top N insights (3-4) based on scores

**Responsibilities**:
- Rank all candidates by composite score
- Select top 3-4 insights
- Format output for consumption
- Ensure no duplicate/redundant insights

**Input**: Scored candidates
**Output**: Top 3-4 ranked insights

**Files**:
- `src/selection/ranker.py` - Ranking and selection logic
- `src/selection/formatter.py` - Output formatting

---

### 8. Strategic LLM Layer
**Purpose**: Interpret scored patterns into strategic insights

**Position**: Runs after the deterministic insight engine has scored patterns

**Responsibilities**:
- Take scored patterns from the deterministic engine
- Prioritize and synthesize into actionable insights
- Provide strategic interpretation of statistical patterns
- Generate recommendations based on scored patterns

**Constraints**:
- ❌ Does NOT invent new data or metrics
- ❌ Only uses provided scored patterns
- ❌ Does NOT replace the deterministic engine
- ❌ Does NOT analyze raw client data directly

**Input**: Scored pattern candidates from deterministic engine
**Output**: Prioritized strategic insights, recommendations, executive summaries

**Files**:
- `src/llm/strategic_layer.py` - Strategic LLM layer implementation

**Note**: This layer runs AFTER the deterministic engine. The reading layer (which interprets file structure) runs BEFORE the deterministic engine.

---

### 9. User-Facing Output Layer
**Purpose**: Format and deliver insights to users

**Responsibilities**:
- Format strategic insights for presentation
- Generate user-friendly reports
- Handle output formatting (JSON, text, etc.)
- Present insights with appropriate context

**Input**: Strategic insights from Strategic LLM Layer
**Output**: Formatted user-facing insights

**Files** (to be implemented):
- `src/output/formatter.py` - Output formatting
- `src/output/report_generator.py` - Report generation

---

## Data Flow

```
[0. File Ingestion Layer]
  → Receive uploaded file
  ↓
[1. LLM-Assisted Reading Layer]
  → Interpret inconsistent column names, platform/campaign/KPI naming
  → Handle Hebrew/English/typos/mixed naming
  → Preserve relevant extra fields
  → Output: Canonical mappings + original data (unchanged)
  ↓
[2. Canonicalized Internal Structure]
  → Apply canonical mappings
  → Preserve original data
  ↓
[3. Feature Extraction Layer]
  → Parse canonicalized structure
  → Raw Features + KPIs
  ↓
[4. Normalized Metrics Layer]
  → Normalized Features (standardized scales)
  ↓
[5. Deterministic Insight Engine]
  → Candidate Generation → Scoring → Selection
  → Top 3-4 Scored Pattern Candidates
  ↓
[6. Strategic LLM Layer]
  → Interpret scored patterns into strategic insights
  → Prioritize and synthesize insights
  → Output: Actionable strategic recommendations
  ↓
[7. User-Facing Output Layer]
  → Format and deliver insights to users
```

## Privacy-Preserving Self-Improvement Mechanism

The system is designed to improve over time **without storing customer data**. This enables continuous learning while maintaining strict privacy guarantees.

### Explicit Privacy Rules

**What MUST NOT be stored**:
- ❌ Raw customer rows
- ❌ Customer-specific numeric data (metric values, counts, amounts)
- ❌ Full uploaded files
- ❌ Client-specific text content (campaign names, platform names from clients)
- ❌ Recoverable original client data
- ❌ Any data that can reconstruct the uploaded file

**What MAY be stored for learning** (abstract patterns only):
- ✅ Abstract mapping patterns (e.g., "column names similar to 'עלות', 'cost', 'spend' often map to canonical 'spend'")
- ✅ Schema-level learnings (e.g., "a field called 'results' may be ambiguous and require caution")
- ✅ Normalized alias suggestions (e.g., "facebook / פייסבוק / meta ads are often platform aliases")
- ✅ Field classification confidence trends (aggregate statistics on mapping accuracy)
- ✅ Generic schema resolution heuristics
- ✅ Prompt improvements and refinements
- ✅ Rule refinements based on aggregate patterns
- ✅ Aggregate non-client-specific metadata

### Learning Mechanism Design

**Allowed Future Memory / Learning Examples**:
- "Column names containing 'עלות', 'cost', 'spend', 'expense' → canonical 'spend' (confidence: 0.92)"
- "Platform aliases: 'facebook' / 'פייסבוק' / 'meta ads' / 'fb' → canonical 'facebook' (confidence: 0.95)"
- "Field named 'results' has ambiguous classification (requires user confirmation in 60% of cases)"
- "Hebrew column names for 'campaign' include: 'קמפיין', 'מסע פרסום', 'קידום'"
- "Confidence trends: Column name mappings improve from 0.75 to 0.89 over 1000 files"
- "Schema pattern: Files with 'date' column typically have temporal patterns"

**Not Allowed**:
- ❌ Storing client tables (even anonymized)
- ❌ Storing exact client metric values (even aggregated)
- ❌ Storing campaign names from clients (even normalized)
- ❌ Storing raw categories from client datasets if they are client-specific
- ❌ Storing anything that reconstructs the uploaded data

### Implementation Approach

1. **Abstract Pattern Storage**: Only store abstract patterns (e.g., "column name patterns", "value alias patterns") without client-specific data
2. **Aggregate Statistics**: Store aggregate confidence trends and accuracy metrics without client identifiers
3. **Schema Heuristics**: Build generic schema resolution rules based on patterns across clients
4. **Prompt Refinement**: Improve LLM prompts based on aggregate mapping quality metrics
5. **Rule Evolution**: Refine mapping rules based on aggregate patterns, not individual client data

### Data Lifecycle

1. **Processing**: Client data is processed in memory only
2. **Mapping Generation**: LLM generates canonical mappings (metadata only)
3. **Pattern Extraction**: Abstract patterns are extracted (no client data)
4. **Learning Update**: Abstract patterns are stored for future use
5. **Data Deletion**: Original client data is deleted after processing completes
6. **No Persistence**: No recoverable client data persists after processing

This design ensures the system improves over time while maintaining strict privacy guarantees and compliance with data protection regulations.

## Core Data Structures

### FeatureSet
- Campaign data with computed KPIs
- Tenant identifier
- Metadata (date ranges, dimensions, etc.)

### InsightCandidate
**Exact Structure**:
```python
{
    # Pattern identification
    "pattern_type": str,  # Enum: SEGMENT_ABOVE_BASELINE, SEGMENT_BELOW_BASELINE, SEGMENT_GAP, TEMPORAL_CHANGE, METRIC_IMBALANCE
    "pattern_id": str,    # Unique identifier for this candidate
    
    # Narrative description
    "description": str,   # Human-readable insight description
    
    # Data points involved
    "primary_segment": dict,  # {dimension: value, metrics: {...}, sample_size: int}
    "comparison_segment": dict | None,  # For comparisons/trends
    "baseline_value": float | None,  # Baseline metric value
    "observed_value": float,  # Observed metric value
    "metric_name": str,  # Which KPI (ROAS, CPA, CTR, etc.)
    
    # Dimensions and context
    "dimensions": dict,  # {device: "mobile", campaign: "X", ...}
    "time_period": dict | None,  # {start: date, end: date} for temporal patterns
    "affected_campaigns": list[str],  # Campaign IDs involved
    
    # Raw metrics for scoring
    "raw_metrics": {
        "primary": dict,  # All KPIs for primary segment
        "comparison": dict | None,  # All KPIs for comparison segment
        "aggregate": dict  # Aggregate metrics (total spend, revenue, etc.)
    },
    
    # Statistical metadata
    "sample_sizes": {
        "primary": int,
        "comparison": int | None
    },
    "variance_metrics": {
        "primary_std": float,
        "comparison_std": float | None
    },
    
    # Metadata
    "tenant_id": str,
    "generation_timestamp": datetime
}
```

### ScoredInsight
- InsightCandidate + scores:
  - Effect size score
  - Business impact score
  - Statistical support score
  - Composite score

### RankedInsight
- Final output format
- Top 3-4 insights with all metadata

## File Structure

```
src/
├── llm/
│   ├── __init__.py
│   ├── reading_layer.py      # LLM-assisted file reading (to be implemented)
│   └── strategic_layer.py    # Strategic LLM layer (interprets scored patterns)
├── feature_extraction/
│   ├── __init__.py
│   ├── parser.py
│   ├── kpi_calculator.py
│   └── feature_set.py
├── normalization/
│   ├── __init__.py
│   ├── metric_normalizer.py
│   ├── dimension_standardizer.py
│   ├── temporal_normalizer.py
│   └── normalized_set.py
├── candidate_generation/
│   ├── __init__.py
│   ├── pattern_detector.py
│   ├── insight_types.py
│   └── candidate.py
├── scoring/
│   ├── __init__.py
│   ├── effect_size.py
│   ├── business_impact.py
│   ├── statistical_support.py
│   └── composite_scorer.py
├── selection/
│   ├── __init__.py
│   ├── ranker.py
│   └── formatter.py
├── models/
│   ├── __init__.py
│   ├── feature_set.py
│   ├── candidate.py
│   └── insight.py
└── engine.py  # Main orchestration
```

tests/
├── feature_extraction/
├── candidate_generation/
├── scoring/
└── selection/

requirements.txt
README.md
```

## Implementation Phases

### Phase 1: Core Infrastructure (Statistical Pattern Generation)
1. Feature extraction (CSV parsing, KPI calculation)
2. Normalized metrics layer (basic normalization)
3. **Statistical candidate generation** (pure structural deviations):
   - SEGMENT_ABOVE_BASELINE (top 1 vs. baseline, 4 KPIs per dimension)
   - SEGMENT_BELOW_BASELINE (bottom 1 vs. baseline, 4 KPIs per dimension)
   - SEGMENT_GAP (top vs. bottom, 4 KPIs per dimension)
   - METRIC_IMBALANCE (spend/revenue ratio deviations, 2 per dimension)
   - TEMPORAL_CHANGE (if temporal: 2 KPIs)
   - Target: < 60 candidates
4. Basic scoring (effect size only)
5. Simple selection (top N by score)

### Phase 2: Enhanced Patterns
1. Additional business-relevant pattern types (if needed)
2. Full scoring suite (all three dimensions)
3. Composite scoring refinement
4. **Note**: Still guided generation, not exhaustive - maintain < 100 candidates

### Phase 3: Optimization
1. Performance tuning
2. Edge case handling
3. Tenant isolation hardening

## Pattern Definition

A **Pattern** is a statistically detectable deviation or relationship in the normalized campaign data. Patterns are characterized by:

1. **Structural Elements**:
   - A primary data segment (the focus of the pattern)
   - An optional comparison point (baseline, another segment, or time period)
   - One or more metrics (KPIs) that exhibit the pattern
   - Dimensions that define the segment boundaries

2. **Pattern Types (Phase 1 - Statistical Deviations Only)**:
   
   **Statistical Pattern Structures**:
   - **SEGMENT_ABOVE_BASELINE**: Segment metric value significantly above aggregate baseline for a given KPI
   - **SEGMENT_BELOW_BASELINE**: Segment metric value significantly below aggregate baseline for a given KPI
   - **SEGMENT_GAP**: Relative difference between top and bottom segments for a given KPI
   - **TEMPORAL_CHANGE**: Change in metric value between time periods (direction determined by data)
   - **METRIC_IMBALANCE**: Deviation between two related metrics (e.g., spend vs revenue ratio)

3. **Pattern Requirements**:
   - Must involve at least one computed KPI
   - Must be statistically detectable (but not necessarily significant - scoring handles that)
   - Must be expressible as a measurable deviation or relationship
   - Segments must have ≥ 2 data points (data quality requirement)
   - **No business interpretation** - patterns are pure statistical structures

4. **Pattern Generation Philosophy (Guided, Not Exhaustive)**:
   - **Single-dimension focus**: Generate patterns within one dimension at a time (campaign, device, platform)
   - **Balanced deviations**: Generate both above-baseline and below-baseline deviations equally
   - **Extreme segments**: Focus on top 1 and bottom 1 segments per dimension, not all pairs
   - **Baseline comparisons**: Compare segments to aggregate baseline
   - **No cross-dimensional combinations**: Do NOT combine dimensions (e.g., no "mobile campaigns on Google")
   - **Primary KPIs**: Focus on ROAS, CPA, Revenue, Spend (core metrics)
   - **No exhaustive pairings**: Do NOT generate all possible segment pairs
   - **Statistical neutrality**: Patterns are structural deviations, not business narratives
   - Noise is handled through scoring, not blocking

## Scoring Calculation Principles

### Effect Size Calculation
**Purpose**: Measure the magnitude of the difference or relationship

**Methods** (selected based on pattern type):
- **For comparisons** (SEGMENT_COMPARISON, deviation signals):
  - **Relative difference**: `|observed - baseline| / baseline` (for ratios like ROAS)
  - **Cohen's d**: `(mean1 - mean2) / pooled_std` (for absolute metrics)
  - **Log ratio**: `log(observed / baseline)` (for multiplicative relationships)
  
- **For trends** (TIME_TREND):
  - **Percent change**: `(current - previous) / previous`
  - **Slope magnitude**: Linear regression slope normalized by mean
  - **Acceleration**: Second derivative if sufficient data points
  
- **For correlations** (CORRELATION):
  - **Pearson r**: Standard correlation coefficient
  - **Spearman ρ**: For non-linear relationships
  
**Output**: Continuous score 0-1 (or unbounded, then normalized) where higher = larger effect

### Business Impact Weight Calculation
**Purpose**: Measure the business significance based on scale and magnitude

**Components**:
1. **Revenue/Spend Magnitude**:
   - Absolute revenue affected: `sum(revenue for affected campaigns)`
   - Absolute spend affected: `sum(spend for affected campaigns)`
   - Normalized by total portfolio size
   
2. **Scale Factor**:
   - Number of campaigns/segments affected
   - Percentage of total portfolio
   - Breadth of dimension coverage
   
3. **KPI Importance Weight**:
   - ROAS, Revenue, Spend → High weight
   - CTR, CVR → Medium weight
   - CPA, AOV → Context-dependent weight
   
4. **Combination**:
   - `impact = (revenue_magnitude * 0.4) + (spend_magnitude * 0.3) + (scale_factor * 0.2) + (kpi_weight * 0.1)`
   - Normalized to 0-1 scale relative to dataset maximums

**Output**: Continuous score 0-1 where higher = greater business impact

### Statistical Support Strength Calculation
**Purpose**: Measure the reliability and confidence in the pattern

**Components**:
1. **Sample Size Adequacy**:
   - `sample_score = min(1.0, log(sample_size + 1) / log(optimal_sample_size + 1))`
   - Optimal sample size varies by metric type (typically 30+ for parametric tests)
   - For very small samples (< 5), use alternative metrics (see below)
   - No hard minimum - continuous scaling
   
2. **Variance Consideration**:
   - Coefficient of variation: `std / mean` (if mean > 0)
   - Lower variance → higher support (more consistent pattern)
   - `variance_score = 1 / (1 + coefficient_of_variation)`
   - For zero variance (single data point), use effect size as proxy
   
3. **Statistical Significance** (sample-size aware):
   - **For large samples (n ≥ 10 per group)**:
     - T-test p-value for comparisons (lower p = higher support)
     - `significance_score = 1 - min(1.0, p_value * 10)` (p=0.05 → score=0.5, p=0.01 → score=0.9)
     - Confidence interval width (narrower = higher support)
   
   - **For small samples (n < 10 per group)**:
     - **DO NOT use p-values** - they are unreliable with small samples
     - Use effect size magnitude as proxy for significance
     - Use bootstrap confidence intervals if n ≥ 5
     - For n < 5, rely on effect size and variance only
     - `significance_score = effect_size_score * sample_adequacy_factor`
     - Where `sample_adequacy_factor = min(1.0, sample_size / 10)`
   
4. **Pattern Consistency**:
   - For trends: R² of fit (if n ≥ 3 data points)
   - For correlations: Strength of correlation (if n ≥ 5 pairs)
   - For deviation signals: Distance from mean in standard deviations
   - For very small samples, consistency = effect size magnitude
   
5. **Combination**:
   - `support = (sample_score * 0.3) + (variance_score * 0.2) + (significance_score * 0.3) + (consistency_score * 0.2)`
   - All components are continuous, no binary thresholds
   - Small sample adjustments: if n < 5, reduce significance weight to 0.1, increase effect size proxy weight

**Output**: Continuous score 0-1 where higher = stronger statistical support

**Key Principle**: Statistical support should reflect reliability. With small samples, we acknowledge uncertainty rather than forcing unreliable p-values.

### Composite Score
**Purpose**: Combine all three dimensions into final ranking score

**Formula (Hybrid Multiplicative-Additive Model)**:
```
base_score = (effect_size * 0.6) + (business_impact * 0.4)
composite_score = base_score * statistical_support
```

**Rationale**:
- **Multiplicative component**: Statistical support acts as a reliability multiplier
  - Weak statistical support (e.g., 0.2) severely reduces composite score
  - Strong statistical support (e.g., 0.9) preserves base score
  - **Prevents**: High business impact from rescuing weak statistical signals
  
- **Additive component**: Effect size and business impact combine additively
  - Effect size weighted 60% (primary driver of insight value)
  - Business impact weighted 40% (scale matters but secondary)
  
- **Behavior**:
  - High effect + high impact + high support → Very high composite (e.g., 0.8 * 0.9 = 0.72)
  - High effect + high impact + low support → Low composite (e.g., 0.8 * 0.2 = 0.16)
  - Low effect + high impact + high support → Low composite (e.g., 0.3 * 0.9 = 0.27)
  
**Minimal Meaningful Signal Floor (ε)**:
- Apply a very small epsilon threshold (ε = 0.001) to composite score
- Patterns with `composite_score < ε` are still generated and scored, but effectively rank at zero
- This prevents micro-noise patterns (e.g., 0.0001% differences) from consuming computational resources
- **Not a hard block** - patterns below ε are still in the candidate list, just ranked at bottom
- Purpose: Computational efficiency, not insight filtering

**No Hard Thresholds**: All scores are continuous. Weak patterns naturally rank lower but are not excluded from candidate generation.

## Noise Avoidance Strategy

**Principle**: Use continuous scoring to naturally deprioritize noise rather than blocking it.

**Mechanisms**:

1. **Statistical Support Penalty**:
   - Low sample sizes → lower support score → lower composite
   - High variance → lower support score → lower composite
   - Weak significance → lower support score → lower composite
   - **Result**: Noisy patterns rank low but aren't blocked

2. **Effect Size Scaling**:
   - Tiny differences → low effect size → lower composite
   - Large differences → high effect size → higher composite
   - **Result**: Meaningless differences naturally rank below meaningful ones

3. **Business Impact Filtering**:
   - Patterns affecting tiny spend/revenue → low impact score
   - Patterns affecting large spend/revenue → high impact score
   - **Result**: Trivial patterns rank low

4. **Composite Score Ranking**:
   - Top 3-4 selection naturally excludes low-scoring noise
   - No hard cutoffs - pure ranking
   - **Result**: Noise exists in candidate list but doesn't appear in final output

5. **Multi-dimensional Scoring**:
   - A pattern needs strength in multiple dimensions to rank high
   - Single-dimension strength is insufficient
   - **Result**: Balanced, reliable insights rise to top

**Key Point**: Noise is handled through **ranking**, not **filtering**. All candidates are scored, but only the strongest (by composite score) are selected.

## Phase 1: Explicit Allowed Comparisons

### Pattern Generation Rules (Phase 1)

**Allowed Pattern Types** (5 statistical structures):

1. **SEGMENT_ABOVE_BASELINE**: Top 1 segment per dimension vs. aggregate baseline (4 KPIs: ROAS, CPA, Revenue, Spend)
2. **SEGMENT_BELOW_BASELINE**: Bottom 1 segment per dimension vs. aggregate baseline (4 KPIs: ROAS, CPA, Revenue, Spend)
3. **SEGMENT_GAP**: Top segment vs. bottom segment per dimension (4 KPIs: ROAS, CPA, Revenue, Spend)
4. **TEMPORAL_CHANGE**: Change in metric between latest and previous period (if temporal: 2 KPIs - ROAS, Revenue)
5. **METRIC_IMBALANCE**: Deviation in ratio between two metrics (e.g., spend/revenue ratio) - top 1 and bottom 1 per dimension

**Allowed Dimensions** (process independently, no combinations):
- `campaign` (if present)
- `device` (if present: mobile, desktop, tablet)
- `platform` (if present: Google, Facebook, etc.)

**Allowed KPIs** (4 primary business metrics):
- `ROAS` (Return on Ad Spend)
- `CPA` (Cost Per Acquisition)
- `Revenue`
- `Spend`

**Generation Logic**:
1. For each dimension (campaign, device, platform):
   - **SEGMENT_ABOVE_BASELINE**: Top 1 segment by each KPI vs. baseline (ROAS, CPA, Revenue, Spend) = **4 patterns**
   - **SEGMENT_BELOW_BASELINE**: Bottom 1 segment by each KPI vs. baseline (ROAS, CPA, Revenue, Spend) = **4 patterns**
   - **SEGMENT_GAP**: Top segment vs. bottom segment by each KPI (ROAS, CPA, Revenue, Spend) = **4 patterns**
   - **METRIC_IMBALANCE**: Top 1 and bottom 1 by (spend/revenue) ratio = **2 patterns**
   - **Total per dimension: 14 patterns**

2. For temporal data (if present):
   - **TEMPORAL_CHANGE**: Change in ROAS and Revenue between periods (direction determined by data) = **2 patterns**

3. **Total per dataset**:
   - 3 dimensions × 14 patterns = **42 patterns**
   - Temporal (if exists): **2 patterns**
   - **Total: ~42-44 patterns** (well under 60 target)

3. **NOT Generated**:
   - ❌ Cross-dimensional combinations (e.g., "mobile campaigns on Google")
   - ❌ All pairwise segment comparisons
   - ❌ Correlation patterns
   - ❌ Secondary KPIs (CTR, CVR, AOV) in Phase 1
   - ❌ Exhaustive dimension exploration

**Example for 8 campaigns, 3 devices, 2 platforms**:
- Campaigns: 14 patterns (4 above + 4 below + 4 gap + 2 imbalance)
- Devices: 14 patterns (4 above + 4 below + 4 gap + 2 imbalance)
- Platforms: 14 patterns (4 above + 4 below + 4 gap + 2 imbalance)
- Temporal (if exists): 2 patterns
- **Total: ~42-44 patterns** (well under 60 target)

## Pattern Generation Estimates (Phase 1 - Guided Generation)

### Expected Pattern Count for 20-40 Row Dataset

**Assumptions for typical marketing dataset**:
- **Dimensions**: campaign (5-10 unique), device (3: mobile/desktop/tablet), platform (2-3), time period (4-8 weeks if temporal)
- **Business KPIs**: 4 primary (ROAS, CPA, Revenue, Spend)
- **Rows**: 20-40

**Pattern counts by type (Statistical Pattern Generation)**:

1. **SEGMENT_ABOVE_BASELINE**:
   - **Per dimension**: Top 1 segment × 4 KPIs (ROAS, CPA, Revenue, Spend)
   - Campaigns: 1 × 4 = **4 patterns**
   - Devices: 1 × 4 = **4 patterns**
   - Platforms: 1 × 4 = **4 patterns**
   - **Subtotal: ~12 patterns**

2. **SEGMENT_BELOW_BASELINE**:
   - **Per dimension**: Bottom 1 segment × 4 KPIs (ROAS, CPA, Revenue, Spend)
   - Campaigns: 1 × 4 = **4 patterns**
   - Devices: 1 × 4 = **4 patterns**
   - Platforms: 1 × 4 = **4 patterns**
   - **Subtotal: ~12 patterns**

3. **SEGMENT_GAP**:
   - **Per dimension**: Top vs. bottom segment × 4 KPIs (ROAS, CPA, Revenue, Spend)
   - Campaigns: 1 × 4 = **4 patterns**
   - Devices: 1 × 4 = **4 patterns**
   - Platforms: 1 × 4 = **4 patterns**
   - **Subtotal: ~12 patterns**

4. **METRIC_IMBALANCE**:
   - **Per dimension**: Top 1 and bottom 1 by (spend/revenue) ratio
   - Campaigns: **2 patterns**
   - Devices: **2 patterns**
   - Platforms: **2 patterns**
   - **Subtotal: ~6 patterns**

5. **TEMPORAL_CHANGE** (if temporal data exists):
   - Change in ROAS and Revenue between periods = **2 patterns**
   - **Subtotal: ~2 patterns** (only if temporal)

**Total Estimate (Phase 1)**:
- **Without temporal data**: **~42 patterns**
- **With temporal data**: **~44 patterns**
- **Well under 60 target**

**Generation Rules Applied**:
- Single-dimension focus only (no cross-dimensional combinations)
- Top 2-3 performers per dimension (not all segments)
- Primary business KPIs only (ROAS, CPA, Revenue, Spend)
- Baseline comparisons prioritized over pairwise comparisons
- Segments with < 2 data points: Skipped (data quality)

**Target**: **< 50 candidates** for 20-40 row datasets

**Scoring Impact**:
- With multiplicative composite scoring, weak patterns (low statistical support) will have very low composite scores
- Top 3-4 selection naturally filters to strongest patterns
- Patterns below ε (0.001) effectively rank at zero

## Key Design Decisions

1. **Statistical Pattern Core**: Patterns are pure statistical structures, not business narratives. Business interpretation layered on top later.
2. **Neutral Generation**: Generate structural deviations (above/below baseline, gaps, temporal changes, metric imbalances) without business framing.
3. **Single-Dimension Focus**: Generate patterns within one dimension at a time. No cross-dimensional combinations.
4. **Extreme Segments**: Focus on top 1 and bottom 1 segments per dimension, not all possible pairs.
5. **Balanced Deviations**: Equal focus on above-baseline and below-baseline deviations. Target < 60 candidates for typical datasets.
4. **Hybrid Scoring Model**: Multiplicative statistical support prevents weak signals from surviving on business impact alone.
5. **Minimal Signal Floor (ε)**: Very small epsilon (0.001) prevents micro-noise without hard blocking.
6. **Small Sample Handling**: Avoid p-values for n < 10; use effect size and variance-based proxies instead.
7. **No Hard Thresholds**: All scoring is continuous. Selection is purely rank-based.
8. **Primary KPIs**: Focus on ROAS, CPA, Revenue, Spend (core metrics) in Phase 1.
9. **Separation of Concerns**: Statistical pattern detection (Phase 1) is separate from business insight interpretation (future layer).
9. **Noise Handling**: Continuous scoring naturally deprioritizes weak patterns without blocking them.
10. **Modular Layers**: Each layer is independent and testable.
11. **Stateless**: No pattern memory or learning (Phase 1).
12. **Tenant Isolation**: Handled at data ingestion level, minimal overhead.
13. **Normalized Metrics**: Separate layer ensures comparable scales for pattern detection.
