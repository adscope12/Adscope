"""Normalized feature set structure."""

from dataclasses import dataclass
from typing import List, Dict
import pandas as pd
from ..models.feature_set import FeatureSet
from .metric_normalizer import normalize_metrics


@dataclass
class NormalizedSet:
    """Normalized feature set with standardized metrics."""
    
    data: pd.DataFrame
    tenant_id: str
    dimensions: List[str]
    kpis: List[str]
    metadata: Dict
    
    @classmethod
    def from_feature_set(cls, feature_set: FeatureSet) -> 'NormalizedSet':
        """Create normalized set from feature set."""
        dimensions = feature_set.get_dimensions()
        kpis = feature_set.get_kpis()
        
        # Normalize metrics
        normalized_df = normalize_metrics(feature_set.data, kpis)
        
        return cls(
            data=normalized_df,
            tenant_id=feature_set.tenant_id,
            dimensions=dimensions,
            kpis=kpis,
            metadata=feature_set.metadata
        )
