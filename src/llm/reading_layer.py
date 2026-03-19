"""
LLM-Assisted Reading Layer

This layer runs BEFORE the deterministic insight engine and interprets
inconsistent file structure from different clients.

Purpose:
- Help interpret uploaded files from different clients
- Handle inconsistent column names, mixed languages (Hebrew/English), typos,
  alternate KPI names, and inconsistent categorical values
- Suggest canonical mappings for fields and values
- Preserve potentially relevant extra fields instead of discarding them
- Prepare input into a cleaner canonical structure before the deterministic engine runs

CRITICAL: Data Immutability Rule
The LLM MUST NOT modify raw customer data values. This is a fundamental
architectural constraint:

What the LLM MUST NOT do:
- Change numbers (metric values, counts, amounts)
- Rewrite textual field values that are actual data records
- "Correct" metric values
- Estimate missing values
- Fabricate or interpolate any client data
- Generate business insights
- Compute scores or metrics
- Replace the deterministic engine
- Analyze business performance directly from raw client data

What the LLM MAY do:
- Interpret schema (column names, structure)
- Suggest mappings (column name → canonical name)
- Normalize labels conceptually (e.g., "Google Ads" → canonical "google")
- Classify fields (dimension, metric, metadata)
- Identify uncertainty (flag ambiguous fields)
- Preserve original data exactly (all transformations are reversible)

Data Preservation Requirements:
- Original uploaded data must remain untouched and recoverable
- All transformations must preserve the original data exactly
- Mapping information is metadata only - actual data values pass through unchanged
- The reading layer outputs a mapping structure, not modified data

Privacy-Preserving Learning:
The system may improve over time through abstract mapping patterns, schema-level
learnings, normalized alias suggestions, field classification confidence trends,
prompt improvements, and rule refinements. However:
- No raw customer rows may be stored
- No customer-specific numeric data may be stored
- No full uploaded files may be stored
- No client-specific text content may be stored
- No recoverable original client data may persist after processing

Allowed future memory examples:
- "column names similar to 'עלות', 'cost', 'spend' often map to canonical spend"
- "facebook / פייסבוק / meta ads are often platform aliases"
- "a field called results may be ambiguous and require caution"
- confidence trends for mappings
- generic schema resolution heuristics

Not allowed:
- storing client tables
- storing exact client metric values
- storing campaign names from clients
- storing raw categories from client datasets if they are client-specific
- storing anything that reconstructs the uploaded data

This module is a placeholder for future implementation.
"""

# TODO: Implement LLM-Assisted Reading Layer
# This will be implemented in a future phase
