"""Feature set operations."""

from ..models.feature_set import FeatureSet
from .kpi_calculator import calculate_kpis


def process_feature_set(feature_set: FeatureSet) -> FeatureSet:
    """Process feature set by calculating KPIs."""
    df_with_kpis = calculate_kpis(feature_set.data)
    
    return FeatureSet(
        data=df_with_kpis,
        tenant_id=feature_set.tenant_id,
        metadata=feature_set.metadata
    )
