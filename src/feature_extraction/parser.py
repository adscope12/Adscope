"""File parsing for campaign data (CSV and XLSX)."""

import pandas as pd
from pathlib import Path
from typing import Optional
from ..models.feature_set import FeatureSet


def parse_dataframe(df: pd.DataFrame) -> FeatureSet:
    """
    Parse DataFrame and return FeatureSet.
    
    This function works with a DataFrame (typically from canonical structure)
    and extracts features for the insight engine.
    
    Args:
        df: DataFrame to parse (typically canonicalized with renamed columns)
        
    Returns:
        FeatureSet object
    """
    # Normalize column names to lowercase
    df = df.copy()  # Work with copy to avoid modifying input
    df.columns = df.columns.str.lower().str.strip()
    
    # Extract metadata
    metadata = {
        'row_count': len(df),
        'columns': list(df.columns),
        'date_range': None
    }
    
    # Try to detect date range
    date_cols = ['date', 'week', 'month']
    for col in date_cols:
        if col in df.columns:
            try:
                df[col] = pd.to_datetime(df[col])
                metadata['date_range'] = {
                    'start': df[col].min(),
                    'end': df[col].max()
                }
            except:
                pass
            break
    
    return FeatureSet(
        data=df,
        tenant_id="",  # Not used in Phase 1
        metadata=metadata
    )


def parse_csv(file_path: str) -> FeatureSet:
    """
    Parse CSV or XLSX file and return FeatureSet.
    
    Note: This parser is called after the LLM-Assisted Reading Layer has
    interpreted the schema. The reading layer (which runs in CLI before this) handles:
    - Inconsistent column names (e.g., "campaign_name" vs "campaign")
    - Multilingual naming (Hebrew/English) and typos
    - Inconsistent platform/campaign/KPI naming
    
    Currently, mappings are not yet applied - parser works with original file.
    Future: Will use canonical_structure with applied mappings.
    
    Expected columns (case-insensitive, after reading layer normalization):
    - Dimension columns: campaign, device, platform, date
    - Metric columns: spend, revenue, clicks, impressions, conversions
    
    Args:
        file_path: Path to CSV or XLSX file
    """
    # Detect file type and read accordingly
    path = Path(file_path)
    ext = path.suffix.lower()
    
    if ext == ".csv":
        df = pd.read_csv(file_path)
    elif ext in [".xlsx", ".xls"]:
        df = pd.read_excel(file_path, engine='openpyxl')
    else:
        raise ValueError(f"Unsupported file type: {ext}. Expected .csv, .xlsx, or .xls")
    
    # Use parse_dataframe for consistent processing
    return parse_dataframe(df)
