"""KPI calculation from raw campaign metrics."""

import pandas as pd
import numpy as np
from typing import Dict


def _apply_column_aliases(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply deterministic alias mapping for common marketing schemas.
    Keeps architecture unchanged; only normalizes column names.
    """
    alias_map = {
        "campaign_type": "campaign",
        "campaignname": "campaign",
        "channel_used": "platform",
        "channel": "platform",
        "customer_segment": "segment",
        "segment_name": "segment",
        "conversion_rate": "cvr",
        "conv_rate": "cvr",
        "acquisition_cost": "cpa",
        "cost_per_acquisition": "cpa",
        "roi": "roas",
        "engagement_score": "engagement_score",
    }

    rename_map = {}
    existing = set(df.columns)
    for col in list(df.columns):
        canonical = alias_map.get(col)
        # Avoid destructive collisions; keep existing canonical column if present.
        if canonical and (canonical not in existing or canonical == col):
            rename_map[col] = canonical
            existing.add(canonical)

    if rename_map:
        df = df.rename(columns=rename_map)
    return df


def calculate_kpis(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate KPIs from raw metrics.
    
    Handles missing values gracefully - missing inputs result in NaN KPIs.
    """
    df = df.copy()
    
    # Normalize column names
    col_map = {col: col.lower().strip() for col in df.columns}
    df = df.rename(columns=col_map)
    df = _apply_column_aliases(df)

    # If cvr exists but conversions is missing, backfill conversions from clicks * cvr.
    # This allows downstream conversion-based patterns without inventing new metrics.
    if 'conversions' not in df.columns and 'cvr' in df.columns and 'clicks' in df.columns:
        df['conversions'] = np.where(
            df['clicks'].notna() & df['cvr'].notna(),
            df['clicks'] * df['cvr'],
            np.nan
        )
    
    # Calculate CTR (Click-Through Rate)
    if 'clicks' in df.columns and 'impressions' in df.columns:
        df['ctr'] = np.where(
            df['impressions'] > 0,
            df['clicks'] / df['impressions'],
            np.nan
        )
    
    # Calculate CVR (Conversion Rate)
    if 'cvr' not in df.columns and 'conversions' in df.columns and 'clicks' in df.columns:
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
    
    # Calculate ROAS (Return on Ad Spend) when not already provided (e.g., ROI mapped to roas)
    if 'roas' not in df.columns and 'revenue' in df.columns and 'spend' in df.columns:
        df['roas'] = np.where(
            df['spend'] > 0,
            df['revenue'] / df['spend'],
            np.nan
        )
    
    return df
