"""KPI calculation from raw campaign metrics."""

import pandas as pd
import numpy as np
from typing import Dict


def calculate_kpis(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate KPIs from raw metrics.
    
    Handles missing values gracefully - missing inputs result in NaN KPIs.
    """
    df = df.copy()
    
    # Normalize column names
    col_map = {col: col.lower().strip() for col in df.columns}
    df = df.rename(columns=col_map)
    
    # Calculate CTR (Click-Through Rate)
    if 'clicks' in df.columns and 'impressions' in df.columns:
        df['ctr'] = np.where(
            df['impressions'] > 0,
            df['clicks'] / df['impressions'],
            np.nan
        )
    
    # Calculate CVR (Conversion Rate)
    if 'conversions' in df.columns and 'clicks' in df.columns:
        df['cvr'] = np.where(
            df['clicks'] > 0,
            df['conversions'] / df['clicks'],
            np.nan
        )
    
    # Calculate CPC (Cost Per Click)
    if 'spend' in df.columns and 'clicks' in df.columns:
        df['cpc'] = np.where(
            df['clicks'] > 0,
            df['spend'] / df['clicks'],
            np.nan
        )
    
    # Calculate CPA (Cost Per Acquisition)
    if 'spend' in df.columns and 'conversions' in df.columns:
        df['cpa'] = np.where(
            df['conversions'] > 0,
            df['spend'] / df['conversions'],
            np.nan
        )
    
    # Calculate AOV (Average Order Value)
    if 'revenue' in df.columns and 'conversions' in df.columns:
        df['aov'] = np.where(
            df['conversions'] > 0,
            df['revenue'] / df['conversions'],
            np.nan
        )
    
    # Calculate ROAS (Return on Ad Spend)
    if 'revenue' in df.columns and 'spend' in df.columns:
        df['roas'] = np.where(
            df['spend'] > 0,
            df['revenue'] / df['spend'],
            np.nan
        )
    
    return df
