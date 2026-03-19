"""
File ingestion module for reading CSV and XLSX files.

This module provides file reading capabilities without modifying the data.
It only reads the file structure and returns a pandas DataFrame.
"""

import pandas as pd
from pathlib import Path
from enum import Enum
from typing import Tuple, Optional


class FileType(Enum):
    """Supported file types."""
    CSV = "csv"
    XLSX = "xlsx"


def detect_file_type(file_path: str) -> FileType:
    """
    Detect file type from file extension.
    
    Args:
        file_path: Path to the file
        
    Returns:
        FileType enum value
        
    Raises:
        ValueError: If file type is not supported
    """
    path = Path(file_path)
    ext = path.suffix.lower()
    
    if ext == ".csv":
        return FileType.CSV
    elif ext in [".xlsx", ".xls"]:
        return FileType.XLSX
    else:
        raise ValueError(
            f"Unsupported file type: {ext}. "
            f"Supported types: .csv, .xlsx, .xls"
        )


def read_file(file_path: str) -> Tuple[pd.DataFrame, FileType]:
    """
    Read a file (CSV or XLSX) and return DataFrame with file type.
    
    This function only reads the file - it does NOT modify any data values.
    The original data remains untouched.
    
    Args:
        file_path: Path to the CSV or XLSX file
        
    Returns:
        Tuple of (DataFrame, FileType)
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file type is not supported
        Exception: If file cannot be read
    """
    file_type = detect_file_type(file_path)
    
    try:
        if file_type == FileType.CSV:
            df = pd.read_csv(file_path)
        elif file_type == FileType.XLSX:
            # Read first sheet by default
            df = pd.read_excel(file_path, engine='openpyxl')
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
            
        return df, file_type
        
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {file_path}")
    except Exception as e:
        raise Exception(f"Error reading file {file_path}: {str(e)}")


def get_schema_info(df: pd.DataFrame) -> dict:
    """
    Extract schema information from DataFrame without exposing data values.
    
    This function only extracts metadata about the schema:
    - Column names
    - Data types
    - Sample unique values (for categorical columns only, limited count)
    - Row count
    
    It does NOT return actual data values or full datasets.
    
    Args:
        df: DataFrame to analyze
        
    Returns:
        Dictionary with schema information:
        - columns: List of column names
        - dtypes: Dictionary of column name -> data type
        - sample_values: Dictionary of column name -> list of sample unique values (max 10)
        - row_count: Number of rows
    """
    schema = {
        "columns": list(df.columns),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "sample_values": {},
        "row_count": len(df),
    }
    
    # For each column, get sample unique values (max 10) for schema interpretation
    # This helps the LLM understand what kind of data is in each column
    # but we limit it to avoid sending too much data
    for col in df.columns:
        if df[col].dtype == "object":  # String/categorical columns
            unique_vals = df[col].dropna().unique()
            # Limit to 10 sample values to avoid sending too much data
            schema["sample_values"][col] = list(unique_vals[:10])
        else:
            # For numeric columns, we don't send sample values
            # The LLM only needs to know it's numeric
            schema["sample_values"][col] = []
    
    return schema
