"""Pattern candidate data structure."""

from dataclasses import dataclass
from typing import Dict, Optional, Any, List
from datetime import datetime

# Import PatternType - using string annotation to avoid circular import issues
try:
    from ..candidate_generation.pattern_types import PatternType
except ImportError:
    # Fallback for type checking
    PatternType = None


@dataclass
class InsightCandidate:
    """Statistical pattern candidate."""
    
    # Required fields (no defaults) - must come first
    pattern_type: Any  # PatternType from candidate_generation.pattern_types
    pattern_id: str
    description: str
    primary_segment: Dict[str, Any]  # {dimension: value, metrics: {...}, sample_size: int}
    observed_value: float
    metric_name: str
    dimensions: Dict[str, str]  # {device: "mobile", campaign: "X", ...}
    raw_metrics: Dict[str, Dict[str, float]]
    sample_sizes: Dict[str, int]
    variance_metrics: Dict[str, Optional[float]]
    tenant_id: str
    generation_timestamp: datetime
    
    # Optional fields (with defaults) - must come after required fields
    comparison_segment: Optional[Dict[str, Any]] = None
    baseline_value: Optional[float] = None
    time_period: Optional[Dict[str, Any]] = None
    affected_campaigns: Optional[List[str]] = None