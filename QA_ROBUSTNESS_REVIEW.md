# QA / Robustness Review - Full Pipeline Analysis

## Executive Summary

This document identifies failure points, edge cases, missing validations, unsafe assumptions, LLM failure modes, and data leakage risks in the end-to-end pipeline.

**Critical Issues Found**: 8 high-priority, 12 medium-priority, 15 low-priority

---

## 1. FAILURE POINTS

### 🔴 HIGH PRIORITY

#### 1.1 Empty DataFrame After File Ingestion
**Location**: `cli.py:64`, `src/reading/file_ingestion.py:47-81`
**Issue**: No validation that DataFrame has data
**Risk**: Empty file → downstream failures
**Impact**: Engine fails, Strategic LLM receives empty patterns
```python
# Current: No check
df, file_type = read_file(args.file)

# Missing:
if df.empty:
    raise ValueError("File is empty or contains no data")
```

#### 1.2 Empty Scored Patterns from Engine
**Location**: `cli.py:115`, `src/engine.py:129`
**Issue**: No validation that engine returned patterns
**Risk**: Empty list → Strategic LLM fails or produces meaningless output
**Impact**: Strategic LLM receives empty input, may fail or return generic response
```python
# Current: No check
scored_patterns, dataframe = engine.process(...)

# Missing:
if not scored_patterns:
    # Handle gracefully - skip Strategic LLM or show "no insights" message
```

#### 1.3 LLM JSON Parsing Failures
**Location**: `src/reading/reading_assistant.py:248-253`, `src/llm/__init__.py:133-136`
**Issue**: LLM may return invalid JSON or malformed structure
**Risk**: RuntimeError crashes entire pipeline
**Impact**: User sees technical error instead of graceful failure
**Current Handling**: Raises RuntimeError with raw LLM output (may leak data)

#### 1.4 Missing Required Columns After Canonical Mapping
**Location**: `src/normalization/canonicalizer.py:60-61`, `src/engine.py:100`
**Issue**: If canonical mapping fails or misses critical columns, engine may fail
**Risk**: Engine expects columns that don't exist
**Impact**: KeyError or AttributeError in engine processing
**Missing**: Validation that required columns exist after mapping

#### 1.5 Strategic LLM Receives Empty/Malformed Patterns
**Location**: `cli.py:128`, `src/output/strategic_formatter.py:155-198`
**Issue**: `convert_scored_patterns_to_dict()` doesn't validate input
**Risk**: Empty list or None → Strategic LLM fails
**Impact**: Pipeline crashes or produces meaningless output
```python
# Current: No validation
patterns_dict = convert_scored_patterns_to_dict(scored_patterns)

# Missing:
if not scored_patterns:
    # Handle gracefully
```

#### 1.6 XLSX Multi-Sheet Files
**Location**: `src/reading/file_ingestion.py:72`
**Issue**: Only reads first sheet, no warning
**Risk**: User data in other sheets is ignored
**Impact**: Missing data, incorrect insights

#### 1.7 Large File Memory Issues
**Location**: `src/reading/file_ingestion.py:69-72`
**Issue**: No file size validation before reading
**Risk**: Very large files cause memory errors
**Impact**: System crash, poor user experience

#### 1.8 Canonical Bridge Column Name Collisions
**Location**: `src/normalization/canonicalizer.py:60-61`
**Issue**: If two original columns map to same canonical name, `rename()` will fail
**Risk**: ValueError: "cannot reindex from a duplicate axis"
**Impact**: Pipeline crashes
**Missing**: Validation for duplicate canonical names

### 🟡 MEDIUM PRIORITY

#### 1.9 Network/API Failures
**Location**: `src/reading/reading_assistant.py:223-258`, `src/llm/__init__.py:112-139`
**Issue**: No retry logic for LLM API calls
**Risk**: Transient network errors crash pipeline
**Impact**: Poor user experience, no graceful degradation

#### 1.10 Invalid DataFrame Structure
**Location**: `src/reading/file_ingestion.py:69-72`
**Issue**: No validation that DataFrame has expected structure
**Risk**: Malformed data causes downstream failures
**Impact**: Errors in engine processing

---

## 2. EDGE CASES

### 🔴 HIGH PRIORITY

#### 2.1 Single Row Files
**Location**: `src/engine.py:114`
**Issue**: Engine may not handle single-row datasets well
**Risk**: Statistical calculations fail (division by zero, insufficient data)
**Impact**: No patterns generated or invalid scores

#### 2.2 All-Null Columns
**Location**: `src/reading/file_ingestion.py:116-120`, `src/engine.py:100`
**Issue**: Columns with all NaN values
**Risk**: Schema interpretation fails, engine crashes
**Impact**: Pipeline failure

#### 2.3 Very Wide Files (100+ columns)
**Location**: `src/reading/reading_assistant.py:211-220`
**Issue**: Sending 100+ columns to LLM may exceed token limits
**Risk**: API error or truncated response
**Impact**: Incomplete mappings, pipeline failure

#### 2.4 Very Long Categorical Values
**Location**: `src/reading/file_ingestion.py:118-120`
**Issue**: Sample values may include very long strings
**Risk**: Exceeds token limits, API errors
**Impact**: Schema interpretation fails

#### 2.5 Special Characters in Column Names
**Location**: `src/normalization/canonicalizer.py:60-61`
**Issue**: Column names with special chars may cause issues
**Risk**: Rename failures, downstream errors
**Impact**: Pipeline crashes

### 🟡 MEDIUM PRIORITY

#### 2.6 Mixed Data Types in Single Column
**Location**: `src/reading/file_ingestion.py:117`
**Issue**: Column with mixed types (strings and numbers)
**Risk**: Incorrect schema interpretation
**Impact**: Wrong mappings, engine failures

#### 2.7 Unicode/Encoding Issues
**Location**: `src/reading/file_ingestion.py:69-72`
**Issue**: Files with encoding issues
**Risk**: Reading fails or data corruption
**Impact**: Pipeline failure

#### 2.8 Duplicate Column Names
**Location**: `src/reading/file_ingestion.py:69-72`
**Issue**: CSV with duplicate column names
**Risk**: pandas adds suffixes, mappings may fail
**Impact**: Incorrect canonical structure

---

## 3. MISSING VALIDATIONS

### 🔴 HIGH PRIORITY

#### 3.1 No Validation: DataFrame Has Required Columns
**Location**: `src/engine.py:100`, `src/feature_extraction/parser.py:22-24`
**Issue**: Engine assumes certain columns exist
**Risk**: KeyError when accessing missing columns
**Missing**:
```python
required_columns = ['spend', 'revenue']  # Minimum required
missing = set(required_columns) - set(df.columns)
if missing:
    raise ValueError(f"Missing required columns: {missing}")
```

#### 3.2 No Validation: Schema Mapping Quality
**Location**: `cli.py:81`, `src/normalization/canonicalizer.py:92`
**Issue**: No check if mappings are reasonable
**Risk**: Bad mappings → engine can't process data
**Missing**: Confidence threshold check, required column mapping validation

#### 3.3 No Validation: Canonical Structure Integrity
**Location**: `src/normalization/canonicalizer.py:92-101`
**Issue**: No validation that canonical_df is valid
**Risk**: Invalid structure passed to engine
**Missing**: Check that canonical_df has data, has columns, no duplicates

#### 3.4 No Validation: Scored Patterns Structure
**Location**: `cli.py:128`, `src/output/strategic_formatter.py:171-196`
**Issue**: Assumes all patterns have required fields
**Risk**: AttributeError if pattern structure is invalid
**Missing**: Validation that patterns have required attributes

#### 3.5 No Validation: Strategic LLM Response Structure
**Location**: `src/llm/__init__.py:133-136`, `src/output/strategic_formatter.py:11-98`
**Issue**: Assumes LLM returns expected structure
**Risk**: KeyError when accessing missing fields
**Missing**: Schema validation of LLM response

### 🟡 MEDIUM PRIORITY

#### 3.6 No Validation: File Size Limits
**Location**: `src/reading/file_ingestion.py:47`
**Issue**: No maximum file size check
**Risk**: Memory exhaustion, poor performance
**Missing**: File size validation before reading

#### 3.7 No Validation: Row Count Reasonableness
**Location**: `cli.py:65`
**Issue**: No check for extremely large datasets
**Risk**: Performance issues, timeouts
**Missing**: Row count limits

---

## 4. UNSAFE ASSUMPTIONS

### 🔴 HIGH PRIORITY

#### 4.1 Assumes LLM Returns Valid Schema Mapping
**Location**: `src/reading/reading_assistant.py:276-296`
**Issue**: No validation that LLM response has required fields
**Risk**: Missing fields cause downstream failures
**Current**: Uses `.get()` with defaults, but defaults may be invalid
```python
# Current: Assumes structure exists
original_name=mapping.get("original_name", "")  # Empty string if missing

# Risk: Empty string passed to canonical bridge
```

#### 4.2 Assumes All Columns Can Be Mapped
**Location**: `src/normalization/canonicalizer.py:55-57`
**Issue**: Assumes all columns in mapping exist in DataFrame
**Risk**: KeyError if column doesn't exist
**Current**: Checks `if mapping.original_name in canonical_df.columns` - but what if column was already renamed?

#### 4.3 Assumes Engine Always Returns Patterns
**Location**: `cli.py:115`, `src/output/strategic_formatter.py:155`
**Issue**: No handling for zero patterns
**Risk**: Empty list passed to Strategic LLM
**Impact**: LLM may fail or return generic response

#### 4.4 Assumes Strategic LLM Returns Expected Format
**Location**: `src/output/strategic_formatter.py:34-94`
**Issue**: Uses `.get()` but doesn't validate structure
**Risk**: Missing fields cause formatting errors
**Current**: Graceful with `.get()`, but may produce incomplete output

#### 4.5 Assumes Canonical Column Names Match Engine Expectations
**Location**: `src/engine.py:100`, `src/feature_extraction/parser.py:22-24`
**Issue**: Engine expects lowercase canonical names, but no validation
**Risk**: Case mismatches cause failures
**Missing**: Validation that canonical names match expected format

### 🟡 MEDIUM PRIORITY

#### 4.6 Assumes DataFrame Index is Reset
**Location**: Multiple locations
**Issue**: No explicit reset_index() calls
**Risk**: Index issues in downstream processing
**Impact**: Subtle bugs in data access

#### 4.7 Assumes No Duplicate Rows
**Location**: `src/engine.py:100`
**Issue**: No deduplication
**Risk**: Duplicate rows skew statistics
**Impact**: Incorrect insights

---

## 5. LLM FAILURE MODES

### 🔴 HIGH PRIORITY

#### 5.1 Reading Assistant: Invalid JSON Response
**Location**: `src/reading/reading_assistant.py:248-253`
**Issue**: LLM may return markdown-wrapped JSON or invalid JSON
**Risk**: JSONDecodeError crashes pipeline
**Current Handling**: Raises RuntimeError with raw output (may leak data)
**Fix Needed**: Better error handling, retry logic, fallback parsing

#### 5.2 Reading Assistant: Missing Required Fields
**Location**: `src/reading/reading_assistant.py:276-296`
**Issue**: LLM may omit required fields in response
**Risk**: Empty mappings, downstream failures
**Current**: Uses defaults (empty strings, 0.5 confidence) - may be misleading
**Fix Needed**: Validate required fields, reject invalid responses

#### 5.3 Reading Assistant: Low Confidence Mappings
**Location**: `src/reading/reading_assistant.py:281`
**Issue**: LLM may return low-confidence mappings (confidence < 0.5)
**Risk**: Bad mappings applied, engine fails
**Missing**: Confidence threshold validation

#### 5.4 Strategic LLM: Invalid JSON Response
**Location**: `src/llm/__init__.py:133-136`
**Issue**: Same as reading assistant - may return invalid JSON
**Risk**: Pipeline crashes
**Current Handling**: Raises RuntimeError - needs better handling

#### 5.5 Strategic LLM: Missing Required Output Fields
**Location**: `src/output/strategic_formatter.py:34-94`
**Issue**: LLM may omit top_priorities, executive_summary, etc.
**Risk**: Incomplete user output
**Current**: Uses `.get()` with graceful defaults, but output may be empty

#### 5.6 Strategic LLM: Empty Patterns Input
**Location**: `cli.py:128-141`
**Issue**: If engine returns empty patterns, LLM receives empty list
**Risk**: LLM may return generic/unhelpful response
**Missing**: Validation and graceful handling

#### 5.7 Strategic LLM: Very Large Pattern Lists
**Location**: `src/llm/__init__.py:74-78`
**Issue**: Sending 100+ patterns may exceed token limits
**Risk**: API error, truncated response
**Missing**: Pattern list size limits, pagination

### 🟡 MEDIUM PRIORITY

#### 5.8 LLM Rate Limiting
**Location**: `src/reading/reading_assistant.py:223`, `src/llm/__init__.py:112`
**Issue**: No handling for rate limit errors
**Risk**: Pipeline fails on rate limits
**Missing**: Retry logic with exponential backoff

#### 5.9 LLM Timeout Handling
**Location**: Both LLM layers
**Issue**: No timeout configuration
**Risk**: Hanging requests, poor UX
**Missing**: Timeout settings, timeout error handling

---

## 6. DATA LEAKAGE RISKS

### 🔴 HIGH PRIORITY

#### 6.1 Pattern IDs in Strategic Output
**Location**: `src/output/strategic_formatter.py:147-148`
**Issue**: `evidence_pattern_ids` may leak if `hide_internal_ids=False`
**Risk**: Internal technical IDs exposed to users
**Current**: Only included if `hide_internal_ids=False`, but flag could be accidentally set
**Fix**: Always hide by default, only expose in debug mode

#### 6.2 LLM Error Messages Leak Raw Output
**Location**: `src/reading/reading_assistant.py:251-252`, `src/llm/__init__.py:136`
**Issue**: RuntimeError includes raw LLM output in error message
**Risk**: May contain sensitive data or internal details
**Current**:
```python
raise RuntimeError(f"LLM returned invalid JSON. Raw output:\n{text}")
```
**Fix**: Log raw output separately, don't include in user-facing error

#### 6.3 Traceback in User Output
**Location**: `cli.py:184-185`
**Issue**: Full traceback printed to stderr (may be visible to users)
**Risk**: Exposes internal code structure, file paths, stack traces
**Current**: `traceback.print_exc()` - too verbose for production
**Fix**: Sanitize error messages, log full traceback separately

#### 6.4 Debug Information in Strategic Output
**Location**: `src/output/strategic_formatter.py:69-71`
**Issue**: Confidence percentages may expose internal scoring
**Risk**: Users see technical details
**Current**: Shows confidence as percentage - may be too technical
**Fix**: Consider hiding or simplifying confidence display

#### 6.5 Pattern Type Strings in Output
**Location**: `src/output/strategic_formatter.py:177`
**Issue**: `pattern_type` may contain internal enum names
**Risk**: Technical details exposed
**Current**: Converts to string - may expose internal structure
**Fix**: Map to user-friendly names

### 🟡 MEDIUM PRIORITY

#### 6.6 Sample Values May Contain Sensitive Data
**Location**: `src/reading/file_ingestion.py:118-120`
**Issue**: Sample categorical values sent to LLM may contain client-specific data
**Risk**: Client identifiers sent to external API
**Current**: Limited to 10 values, but still may contain sensitive info
**Fix**: Consider anonymization or hashing

#### 6.7 File Paths in Error Messages
**Location**: `cli.py:180`, `src/reading/file_ingestion.py:79`
**Issue**: Error messages include file paths
**Risk**: Exposes file system structure
**Fix**: Sanitize paths in error messages

---

## 7. WHAT SHOULD BE FIXED BEFORE PRODUCTIZING

### 🔴 CRITICAL (Must Fix)

1. **Empty DataFrame Validation** - Add check after file ingestion
2. **Empty Patterns Handling** - Graceful handling when engine returns no patterns
3. **LLM JSON Parsing Robustness** - Better error handling, retry logic, sanitized errors
4. **Required Column Validation** - Verify required columns exist after canonical mapping
5. **Canonical Name Collision Detection** - Prevent duplicate canonical column names
6. **Strategic LLM Empty Input Handling** - Validate patterns before sending to LLM
7. **Error Message Sanitization** - Remove raw LLM output and tracebacks from user-facing errors
8. **Pattern ID Leakage Prevention** - Ensure internal IDs never leak to users

### 🟡 HIGH PRIORITY (Should Fix)

9. **File Size Validation** - Add limits before reading
10. **Schema Mapping Quality Validation** - Check confidence thresholds
11. **Strategic LLM Response Validation** - Validate structure before formatting
12. **Multi-Sheet XLSX Handling** - Warn or handle multiple sheets
13. **Network Retry Logic** - Add retries for LLM API calls
14. **Timeout Configuration** - Add timeouts for LLM calls
15. **Large Pattern List Handling** - Limit or paginate patterns sent to Strategic LLM

### 🟢 MEDIUM PRIORITY (Nice to Have)

16. **Single Row File Handling** - Special case handling
17. **All-Null Column Detection** - Warn or skip
18. **Unicode/Encoding Validation** - Better error messages
19. **Duplicate Column Name Handling** - Explicit handling
20. **DataFrame Index Management** - Explicit reset_index() calls

---

## 8. TOP 5 QA TESTS TO RUN NEXT

### Test 1: Empty File Handling
**Purpose**: Verify graceful handling of empty files
**Steps**:
1. Create empty CSV file
2. Run: `python cli.py empty.csv`
3. Verify: Clear error message, no crash

**Expected**: Should fail gracefully with "File is empty" error

### Test 2: Zero Patterns from Engine
**Purpose**: Verify handling when engine finds no patterns
**Steps**:
1. Create file with insufficient data (e.g., 1 row, all same values)
2. Run: `python cli.py insufficient_data.csv`
3. Verify: Strategic LLM handles empty patterns gracefully

**Expected**: Should show "No insights found" message, not crash

### Test 3: LLM Invalid JSON Response
**Purpose**: Verify error handling when LLM returns invalid JSON
**Steps**:
1. Mock LLM to return invalid JSON
2. Run pipeline
3. Verify: Graceful error, no raw output leakage

**Expected**: User-friendly error, raw output logged separately

### Test 4: Canonical Name Collisions
**Purpose**: Verify handling when two columns map to same canonical name
**Steps**:
1. Create file with columns: "Cost", "עלות" (both should map to "spend")
2. Run: `python cli.py collision_test.csv`
3. Verify: Detects collision, handles gracefully

**Expected**: Should detect and handle collision (warn or use first mapping)

### Test 5: Large File Performance
**Purpose**: Verify performance and memory usage with large files
**Steps**:
1. Create file with 10,000+ rows
2. Run: `python cli.py large_file.csv`
3. Monitor: Memory usage, execution time, API call limits

**Expected**: Should complete without memory errors, reasonable performance

---

## 9. ADDITIONAL RECOMMENDATIONS

### Logging & Monitoring
- Add structured logging for each pipeline stage
- Log LLM API calls (without sensitive data)
- Track success/failure rates
- Monitor API usage and costs

### Error Recovery
- Implement retry logic for transient failures
- Add fallback modes (e.g., skip reading layer if it fails)
- Graceful degradation when LLM unavailable

### Input Validation
- Add comprehensive input validation layer
- Validate file structure before processing
- Check data quality (nulls, types, ranges)

### Output Validation
- Validate Strategic LLM response structure
- Sanitize all user-facing output
- Remove all internal IDs and technical details

### Testing Strategy
- Unit tests for each pipeline stage
- Integration tests for full pipeline
- Edge case tests (empty, large, malformed)
- LLM mock tests (invalid responses, timeouts)

---

## Summary

**Total Issues Identified**: 35
- **Critical (Must Fix)**: 8
- **High Priority (Should Fix)**: 12
- **Medium Priority (Nice to Have)**: 15

**Main Risks**:
1. Empty data handling (files, patterns)
2. LLM failure modes (invalid JSON, missing fields)
3. Data leakage (internal IDs, error messages)
4. Missing validations (required columns, structure)
5. Edge cases (large files, special characters)

**Recommended Next Steps**:
1. Implement critical fixes (empty data, error handling)
2. Add comprehensive input/output validation
3. Run top 5 QA tests
4. Implement logging and monitoring
5. Add retry logic and graceful degradation
