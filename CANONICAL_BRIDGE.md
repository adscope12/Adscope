# Canonical Bridge Implementation

## Overview

The canonical bridge provides a safe mapping layer between the reading assistant and the deterministic insight engine. It creates a canonicalized view of the data without modifying the original DataFrame.

## Key Principles

✅ **Original DataFrame Unchanged**: The original DataFrame is never modified
✅ **No Data Mutations**: Only column names and categorical labels are changed
✅ **No Numeric Changes**: All numeric values pass through unchanged
✅ **No Field Deletion**: All fields are preserved
✅ **Copy-Based**: Works with a copy, original remains untouched

## How the Canonical Bridge Works

### 1. Column Name Mapping

**Example**:
- Original column: `"עלות"` (Hebrew for "cost")
- Canonical column: `"spend"`
- Process: DataFrame copy is created, column is renamed
- Original: `df["עלות"]` still exists unchanged
- Canonical: `canonical_df["spend"]` contains same data

### 2. Categorical Value Mapping

**Example**:
- Original value: `"פייסבוק"` (Hebrew for "Facebook")
- Canonical value: `"facebook"`
- Process: Only string/categorical columns are affected
- Numeric columns: Completely untouched
- Original: Original values remain in original DataFrame
- Canonical: Mapped values in canonical DataFrame copy

### 3. Data Immutability

```python
# Original DataFrame
original_df = pd.DataFrame({
    "עלות": [100, 200, 300],  # Hebrew column name
    "פלטפורמה": ["פייסבוק", "Google", "Meta"]  # Hebrew values
})

# Canonical bridge creates a copy
canonical_df = original_df.copy()
canonical_df = canonical_df.rename(columns={"עלות": "spend", "פלטפורמה": "platform"})
canonical_df["platform"] = canonical_df["platform"].replace({
    "פייסבוק": "facebook",
    "Meta": "facebook"
})

# Original remains unchanged
assert original_df.columns.tolist() == ["עלות", "פלטפורמה"]
assert original_df["פלטפורמה"].iloc[0] == "פייסבוק"

# Canonical has mapped names
assert canonical_df.columns.tolist() == ["spend", "platform"]
assert canonical_df["platform"].iloc[0] == "facebook"

# Numeric values unchanged
assert original_df["עלות"].iloc[0] == canonical_df["spend"].iloc[0] == 100
```

## Implementation Details

### File: `src/normalization/canonicalizer.py`

**Function: `create_canonical_bridge()`**

1. **Creates Copy**: `canonical_df = df.copy()`
   - Original DataFrame untouched

2. **Renames Columns**: Uses `rename(columns=column_mapping_dict)`
   - Only column names changed
   - Data values unchanged

3. **Maps Categorical Values**: Uses `replace()` on object columns only
   - Only affects string/categorical columns
   - Numeric columns completely untouched
   - Only label changes, not data modifications

4. **Returns Structure**:
   ```python
   {
       "original_df": df,  # Original (unchanged)
       "canonical_df": canonical_df,  # Canonicalized copy
       "schema_mapping": schema_mapping,
       "column_mapping_dict": {...},
       "value_mapping_dicts": {...},
   }
   ```

### File: `src/engine.py`

**Updated `process()` method**:

- Accepts `canonical_structure` parameter
- Uses `canonical_df` from structure
- Falls back to file path for backward compatibility
- Engine works with canonicalized column names

### File: `src/feature_extraction/parser.py`

**New function: `parse_dataframe()`**:

- Accepts DataFrame directly (from canonical structure)
- Normalizes column names to lowercase
- Extracts metadata
- Returns FeatureSet for engine processing

## Example Flow

### Input File (Hebrew/English mixed)
```csv
קמפיין,עלות,הכנסה,פלטפורמה
Campaign A,1000,2500,פייסבוק
Campaign B,800,1800,Google
Campaign C,1200,3000,Meta
```

### Step 1: File Ingestion
```python
df, file_type = read_file("data.csv")
# df has columns: ['קמפיין', 'עלות', 'הכנסה', 'פלטפורמה']
```

### Step 2: Reading Assistant
```python
schema_mapping = reading_assistant.interpret_schema("data.csv", original_df=df)
# Returns mappings:
# - 'קמפיין' → 'campaign'
# - 'עלות' → 'spend'
# - 'הכנסה' → 'revenue'
# - 'פלטפורמה' → 'platform'
# - 'פייסבוק' → 'facebook'
# - 'Meta' → 'facebook'
```

### Step 3: Canonical Bridge
```python
canonical_structure = create_canonical_bridge(df, schema_mapping)

# Original DataFrame (unchanged)
original_df = canonical_structure["original_df"]
# Columns: ['קמפיין', 'עלות', 'הכנסה', 'פלטפורמה']
# Values: ['פייסבוק', 'Google', 'Meta']

# Canonical DataFrame (copy with mappings)
canonical_df = canonical_structure["canonical_df"]
# Columns: ['campaign', 'spend', 'revenue', 'platform']
# Values: ['facebook', 'google', 'facebook']

# Verify immutability
assert original_df["עלות"].iloc[0] == canonical_df["spend"].iloc[0] == 1000
assert original_df["פלטפורמה"].iloc[0] == "פייסבוק"  # Original unchanged
assert canonical_df["platform"].iloc[0] == "facebook"  # Canonical mapped
```

### Step 4: Engine Processing
```python
engine = InsightEngine()
scored_patterns, dataframe = engine.process(canonical_structure=canonical_structure)

# Engine works with canonical column names:
# - 'spend' instead of 'עלות'
# - 'revenue' instead of 'הכנסה'
# - 'platform' instead of 'פלטפורמה'
# - 'facebook' instead of 'פייסבוק' or 'Meta'
```

## Data Immutability Verification

### ✅ Original DataFrame Unchanged
- `original_df` reference maintained
- No modifications to original
- All original columns and values preserved

### ✅ No Numeric Data Changes
- Numeric columns pass through unchanged
- Only column names and categorical labels modified
- All metric values (spend, revenue, etc.) identical

### ✅ No Field Deletion
- All columns preserved
- Additional fields maintained
- Uncertain fields preserved

### ✅ Copy-Based Architecture
- Works with `df.copy()`
- Original never touched
- Canonical is independent copy

## Modified Files

1. **`src/normalization/canonicalizer.py`**
   - Added `create_canonical_bridge()` function
   - Updated `prepare_canonical_structure()` to use bridge
   - Implements column and value mapping

2. **`src/engine.py`**
   - Updated `process()` to accept `canonical_structure`
   - Uses `canonical_df` from structure
   - Maintains backward compatibility with file path

3. **`src/feature_extraction/parser.py`**
   - Added `parse_dataframe()` function
   - Updated `parse_csv()` to use `parse_dataframe()`
   - Supports both file path and DataFrame input

4. **`cli.py`**
   - Updated to create canonical bridge
   - Passes canonical structure to engine
   - Logs canonical column names

## Usage Example

```bash
$ python cli.py data.csv

Reading file: data.csv
File type: csv, Rows: 3, Columns: 4

Running LLM-Assisted Reading Layer...
[Schema interpretation...]

Canonical bridge created:
  Original columns: ['קמפיין', 'עלות', 'הכנסה', 'פלטפורמה']
  Canonical columns: ['campaign', 'spend', 'revenue', 'platform']
  ✓ Original DataFrame unchanged

Running Deterministic Insight Engine...
[Engine processes with canonical column names...]
```

## Summary

The canonical bridge provides a safe, immutable mapping layer that:
- Preserves original data completely
- Creates canonicalized view for engine
- Only modifies column names and categorical labels
- Never touches numeric values
- Never deletes fields
- Works with independent copy

This allows the deterministic engine to work with consistent, canonical column names while maintaining complete data immutability.
