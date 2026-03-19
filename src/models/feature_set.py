"""Feature set data structure for raw campaign data with computed KPIs."""

from dataclasses import dataclass
from typing import Dict, List, Optional
import pandas as pd


@dataclass
class FeatureSet:
    """Raw feature set with computed KPIs."""
    
    data: pd.DataFrame  # Campaign data with computed KPIs
    tenant_id: str
    metadata: Dict  # Date ranges, dimensions, etc.
    
    def get_dimensions(self) -> List[str]:
        """Get available dimension columns."""
        # Common dimension columns
        dimension_candidates = ['campaign', 'device', 'platform', 'date', 'week', 'month']
        return [col for col in dimension_candidates if col in self.data.columns]
    
    def get_kpis(self) -> List[str]:
        """Get available KPI columns."""
        kpi_candidates = [
            'spend', 'revenue', 'clicks', 'impressions', 'conversions',
            'ctr', 'cvr', 'cpc', 'cpa', 'aov', 'roas'
        ]
        return [col for col in kpi_candidates if col in self.data.columns]
