"""
Canonical Structure Preparation Module.

This module creates a canonical bridge between the reading assistant and the
deterministic engine. It provides a canonicalized view of the data without
modifying the original DataFrame.

CRITICAL: Data Immutability
- Original DataFrame remains completely unchanged
- Only column names are renamed (metadata change, not data change)
- Categorical values are remapped (label changes only, not numeric data)
- No numeric values are modified
- No fields are deleted
"""

from typing import Dict, Any, Optional
import pandas as pd
from ..reading.reading_assistant import SchemaMapping


def create_canonical_bridge(
    df: pd.DataFrame,
    schema_mapping: SchemaMapping,
) -> Dict[str, Any]:
    """
    Create a canonical bridge - a canonicalized copy of the DataFrame.
    
    This function:
    - Creates a copy of the original DataFrame (original remains untouched)
    - Renames columns using column mappings (e.g., "עלות" → "spend")
    - Applies categorical value mappings (e.g., "פייסבוק" → "facebook")
    - Preserves all original data values (numeric values unchanged)
    - Preserves all fields (nothing deleted)
    
    CRITICAL: The original DataFrame is never modified. This function only
    creates a canonicalized copy that the engine can use.
    
    Args:
        df: Original DataFrame (will remain unchanged)
        schema_mapping: SchemaMapping from reading assistant
        
    Returns:
        Dictionary with canonical structure:
        - original_df: Reference to original DataFrame (unchanged)
        - canonical_df: Canonicalized copy with renamed columns and mapped values
        - schema_mapping: SchemaMapping object
        - column_mapping_dict: Dict mapping original → canonical column names
        - value_mapping_dicts: Dict of column → value mappings
    """
    # Create a copy of the DataFrame - original remains untouched
    canonical_df = df.copy()
    
    # Build column mapping dictionary
    column_mapping_dict = {}
    for mapping in schema_mapping.column_mappings:
        if mapping.original_name in canonical_df.columns:
            canonical_name = mapping.canonical_name
            
            # CRITICAL FIX #5: Canonical name collision detection
            # Check if this canonical name is already mapped
            if canonical_name in column_mapping_dict.values():
                # Find which original column already maps to this canonical name
                existing_original = next(
                    orig for orig, canon in column_mapping_dict.items()
                    if canon == canonical_name
                )
                raise ValueError(
                    f"Canonical name collision: Both '{mapping.original_name}' and "
                    f"'{existing_original}' map to '{canonical_name}'. "
                    f"Please review schema mappings or adjust column names."
                )
            
            column_mapping_dict[mapping.original_name] = canonical_name
    
    # Rename columns using mappings (only column names, not data values)
    if column_mapping_dict:
        canonical_df = canonical_df.rename(columns=column_mapping_dict)
    
    # Build value mapping dictionaries by column
    value_mapping_dicts = {}
    for value_mapping in schema_mapping.value_mappings:
        col_name = value_mapping.column_name
        
        # Use canonical column name if it was mapped
        canonical_col_name = column_mapping_dict.get(col_name, col_name)
        
        # Only apply value mappings if the column exists in canonical_df
        if canonical_col_name in canonical_df.columns:
            if canonical_col_name not in value_mapping_dicts:
                value_mapping_dicts[canonical_col_name] = {}
            
            # Map original value to canonical value
            value_mapping_dicts[canonical_col_name][value_mapping.original_value] = (
                value_mapping.canonical_value
            )
    
    # Apply categorical value mappings (only for string/categorical columns)
    # This changes labels only, not numeric data
    for col_name, value_map in value_mapping_dicts.items():
        if col_name in canonical_df.columns:
            # Only apply to object/string columns (categorical)
            if canonical_df[col_name].dtype == 'object':
                # Replace values using the mapping
                # This only changes string labels, not numeric data
                canonical_df[col_name] = canonical_df[col_name].replace(value_map)
    
    # CRITICAL FIX #4: Required column validation after canonical mapping
    # Check that canonical DataFrame has minimum required columns for engine
    # Only 'spend' is required; 'revenue' is optional (determines analysis mode)
    required_columns = ['spend']  # Minimum required for KPI calculation
    canonical_columns_lower = [col.lower().strip() for col in canonical_df.columns]
    missing_required = [
        req for req in required_columns
        if req not in canonical_columns_lower
    ]
    
    if missing_required:
        # Check if columns exist with different casing
        found_alternatives = []
        for req in missing_required:
            for col in canonical_df.columns:
                if col.lower().strip() == req:
                    found_alternatives.append(f"'{col}' (maps to '{req}')")
                    break
        
        if found_alternatives:
            raise ValueError(
                f"Required columns not found after canonical mapping: {missing_required}. "
                f"Found similar columns: {', '.join(found_alternatives)}. "
                f"Please check schema mappings."
            )
        else:
            raise ValueError(
                f"Required columns not found after canonical mapping: {missing_required}. "
                f"Available columns: {list(canonical_df.columns)}. "
                f"Please ensure your file contains spend data."
            )
    
    # Detect analysis mode based on revenue presence
    has_revenue = 'revenue' in canonical_columns_lower
    analysis_mode = "full" if has_revenue else "performance"
    
    # Validate canonical_df is not empty
    if canonical_df.empty:
        raise ValueError("Canonical DataFrame is empty after mapping. Cannot process.")
    
    # Build canonical structure
    canonical_structure = {
        "original_df": df,  # Original DataFrame (unchanged)
        "canonical_df": canonical_df,  # Canonicalized copy for engine
        "schema_mapping": schema_mapping,
        "column_mapping_dict": column_mapping_dict,
        "value_mapping_dicts": value_mapping_dicts,
        "mappings_applied": True,
        "analysis_mode": analysis_mode,  # "full" or "performance"
    }
    
    return canonical_structure


def prepare_canonical_structure(
    df: pd.DataFrame,
    schema_mapping: SchemaMapping,
    apply_mappings: bool = True,
) -> Dict[str, Any]:
    """
    Prepare canonical structure from schema mappings.
    
    This function creates a canonical bridge that provides a canonicalized
    view of the data without modifying the original DataFrame.
    
    Args:
        df: Original DataFrame (unchanged)
        schema_mapping: SchemaMapping from reading assistant
        apply_mappings: If True, create canonical bridge with applied mappings.
                       If False, return metadata only.
        
    Returns:
        Dictionary with canonical structure
    """
    if apply_mappings:
        return create_canonical_bridge(df, schema_mapping)
    else:
        # Return metadata only (for logging/debugging)
        return {
            "original_df": df,
            "canonical_df": None,
            "schema_mapping": schema_mapping,
            "column_mapping_dict": {
                mapping.original_name: mapping.canonical_name
                for mapping in schema_mapping.column_mappings
            },
            "value_mapping_dicts": {},
            "mappings_applied": False,
        }


def log_schema_mapping(schema_mapping: SchemaMapping, verbose: bool = True) -> None:
    """
    Log schema mapping results to console.
    
    Args:
        schema_mapping: SchemaMapping to log
        verbose: If True, print detailed information
    """
    if not verbose:
        return
    
    print("\n" + "=" * 70)
    print("LLM-ASSISTED READING LAYER: Schema Interpretation Results")
    print("=" * 70)
    
    if schema_mapping.column_mappings:
        print("\nColumn Mappings:")
        for mapping in schema_mapping.column_mappings:
            print(f"  '{mapping.original_name}' → '{mapping.canonical_name}'")
            print(f"    Type: {mapping.field_type}, Confidence: {mapping.confidence:.2f}")
            if mapping.notes:
                print(f"    Notes: {mapping.notes}")
    
    if schema_mapping.value_mappings:
        print("\nValue Mappings (Categorical):")
        for mapping in schema_mapping.value_mappings:
            print(f"  Column '{mapping.column_name}':")
            print(f"    '{mapping.original_value}' → '{mapping.canonical_value}'")
            print(f"    Confidence: {mapping.confidence:.2f}")
    
    if schema_mapping.uncertain_fields:
        print(f"\nUncertain Fields (require caution): {schema_mapping.uncertain_fields}")
    
    if schema_mapping.additional_fields:
        print(f"\nAdditional Fields (preserved): {schema_mapping.additional_fields}")
    
    if schema_mapping.notes:
        print(f"\nNotes: {schema_mapping.notes}")
    
    print("\n" + "=" * 70)
    print("IMPORTANT: Original data remains unchanged. Mappings are metadata only.")
    print("=" * 70 + "\n")
