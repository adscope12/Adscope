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
import logging
import re
import pandas as pd
from ..reading.reading_assistant import SchemaMapping

logger = logging.getLogger(__name__)


def _is_id_like_column(name: str) -> bool:
    """Detect identifier-like column names (campaign_id, id, identifier, etc.)."""
    n = (name or "").strip().lower()
    if not n:
        return False
    return (
        n == "id"
        or n.endswith("_id")
        or "identifier" in n
        or re.search(r"\bid\b", n) is not None
    )


def _slugify_column_name(name: str) -> str:
    """Create a safe suffix from original column name."""
    s = (name or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s or "field"


def _unique_canonical_name(base: str, used: set[str]) -> str:
    """Return a unique canonical name by appending numeric suffixes when needed."""
    candidate = base
    i = 2
    while candidate in used:
        candidate = f"{base}_{i}"
        i += 1
    return candidate


def _disambiguate_collision_name(
    original_name: str,
    canonical_name: str,
    used: set[str],
) -> str:
    """
    Deterministically resolve canonical-name collisions:
    - ID-like fields -> <canonical>_id
    - Others -> <canonical>_<original_slug>
    """
    base = (canonical_name or "").strip().lower() or "field"
    if _is_id_like_column(original_name):
        if not base.endswith("_id"):
            base = f"{base}_id"
    else:
        base = f"{base}_{_slugify_column_name(original_name)}"
    return _unique_canonical_name(base, used)


def _apply_builtin_aliases(canonical_df: pd.DataFrame) -> pd.DataFrame:
    """
    Deterministic fallback aliases for common campaign datasets.
    Used to stabilize cases where LLM mapping is partial.
    """
    alias_map = {
        "campaign_type": "campaign",
        "channel_used": "platform",
        "channel": "platform",
        "conversion_rate": "cvr",
        "acquisition_cost": "cpa",
        "roi": "roas",
        "customer_segment": "segment",
        "segment_name": "segment",
        "engagement_score": "engagement_score",
    }
    cols = {c.lower().strip(): c for c in canonical_df.columns}
    rename_map = {}
    for src, dst in alias_map.items():
        src_actual = cols.get(src)
        dst_actual = cols.get(dst)
        if src_actual and not dst_actual:
            rename_map[src_actual] = dst
    if rename_map:
        canonical_df = canonical_df.rename(columns=rename_map)
    return canonical_df


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
            # Check if this canonical name is already mapped.
            # Resolve deterministically instead of hard-failing the whole analysis.
            if canonical_name in column_mapping_dict.values():
                # Find which original column already maps to this canonical name
                existing_original = next(
                    orig for orig, canon in column_mapping_dict.items()
                    if canon == canonical_name
                )
                used_names = set(column_mapping_dict.values())

                # Prefer non-ID field for business dimension; move ID-like field to *_id.
                existing_is_id = _is_id_like_column(existing_original)
                new_is_id = _is_id_like_column(mapping.original_name)

                if existing_is_id and not new_is_id:
                    # Existing mapping is id-like, new one is business-like.
                    # Keep new at canonical base, move existing to disambiguated name.
                    replacement = _disambiguate_collision_name(
                        existing_original, canonical_name, used_names - {canonical_name}
                    )
                    column_mapping_dict[existing_original] = replacement
                    used_names = set(column_mapping_dict.values())
                    column_mapping_dict[mapping.original_name] = _unique_canonical_name(
                        canonical_name, used_names - {canonical_name}
                    )
                    logger.warning(
                        "Canonical collision resolved: '%s' moved to '%s'; '%s' kept as '%s'",
                        existing_original, replacement, mapping.original_name, canonical_name
                    )
                    continue

                # Otherwise disambiguate the incoming colliding field.
                resolved_name = _disambiguate_collision_name(
                    mapping.original_name, canonical_name, used_names
                )
                column_mapping_dict[mapping.original_name] = resolved_name
                logger.warning(
                    "Canonical collision resolved: '%s' mapped to '%s' (original target '%s' used by '%s')",
                    mapping.original_name, resolved_name, canonical_name, existing_original
                )
                continue
            
            column_mapping_dict[mapping.original_name] = canonical_name
    
    # Rename columns using mappings (only column names, not data values)
    if column_mapping_dict:
        canonical_df = canonical_df.rename(columns=column_mapping_dict)

    # Deterministic alias fallback for common schemas
    canonical_df = _apply_builtin_aliases(canonical_df)
    
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
    
    # Flexible minimum metric validation for broader campaign datasets.
    canonical_columns_lower = [col.lower().strip() for col in canonical_df.columns]
    supported_metric_keys = {
        "spend", "revenue", "clicks", "impressions", "conversions",
        "cvr", "cpa", "cpc", "roas", "roi", "engagement_score"
    }
    available_metrics = [c for c in canonical_columns_lower if c in supported_metric_keys]
    if not available_metrics:
        raise ValueError(
            "No supported marketing metrics found after canonical mapping. "
            f"Available columns: {list(canonical_df.columns)}. "
            "Expected at least one of spend/revenue/clicks/impressions/conversions/"
            "cvr/cpa/cpc/roas/roi/engagement_score."
        )
    
    # Detect analysis mode based on revenue/return signal presence
    has_revenue = 'revenue' in canonical_columns_lower or 'roas' in canonical_columns_lower or 'roi' in canonical_columns_lower
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
