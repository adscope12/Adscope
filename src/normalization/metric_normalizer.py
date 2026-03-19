"""Normalize KPIs to comparable scales."""

import pandas as pd
import numpy as np
from typing import List


def normalize_metrics(df: pd.DataFrame, kpi_columns: List[str]) -> pd.DataFrame:
    """
    Normalize KPIs using z-scores for pattern detection.
    
    Handles missing values - they remain NaN and are excluded from normalization.
    """
    df = df.copy()
    
    for kpi in kpi_columns:
        if kpi not in df.columns:
            continue
        
        col_data = df[kpi].dropna()
        
        if len(col_data) < 2:
            # Not enough data to normalize
            continue
        
        mean_val = col_data.mean()
        std_val = col_data.std()
        
        if std_val > 0:
            # Z-score normalization
            df[f'{kpi}_normalized'] = (df[kpi] - mean_val) / std_val
        else:
            # Constant values - set normalized to 0
            df[f'{kpi}_normalized'] = 0.0
    
    return df
