"""Statistical support strength calculations using pragmatic confidence proxy."""

import numpy as np
import pandas as pd
from typing import Optional
from ..models.candidate import InsightCandidate


def calculate_statistical_support(candidate: InsightCandidate) -> float:
    """
    Calculate statistical support strength (0-1 scale) using pragmatic confidence proxy.
    
    Method:
    1. effect = abs(observed_value - baseline_value)
    2. relative_effect = effect / (abs(baseline_value) + 1e-9)
    3. volume_factor = min(1.0, log(1 + sample_size) / log(1000))
    4. raw_support = relative_effect * volume_factor
    5. support = 1 - exp(-5 * raw_support)
    6. Clamp to [0, 1]
    
    This ensures:
    - Small effect + small volume → low support
    - Large effect + large volume → high support
    - No extreme 0.999 saturation for most patterns
    
    Returns:
        Statistical support score between 0 and 1
    """
    from ..candidate_generation.pattern_types import PatternType
    
    # Check if we have baseline for comparison
    if candidate.baseline_value is None:
        # No baseline - cannot compute relative effect, return low support
        return 0.0
    
    # Detect temporal patterns
    is_temporal_pattern = (
        candidate.pattern_type == PatternType.TEMPORAL_CHANGE or
        'weekend' in str(candidate.dimensions).lower() or
        'weekday' in str(candidate.dimensions).lower() or
        candidate.pattern_id.startswith(('GRADUAL_DECLINE', 'RECOVERY', 'SPIKE_DROP', 'WEEKEND_WEEKDAY'))
    )
    
    # Get required data
    # For temporal patterns, use total sample size (primary + comparison)
    # This prevents penalizing temporal patterns for having smaller segment sizes
    if is_temporal_pattern:
        sample_size = (
            candidate.sample_sizes.get('primary', 0) + 
            candidate.sample_sizes.get('comparison', 0)
        )
    else:
        sample_size = candidate.sample_sizes.get('primary', 0)
    
    observed_value = candidate.observed_value
    baseline_value = candidate.baseline_value
    
    # Guardrail: if n < 1 -> support = 0
    if sample_size < 1:
        return 0.0
    
    # 1. Define effect
    effect = abs(observed_value - baseline_value)
    
    # 2. Define relative_effect
    # Use small epsilon to avoid division by zero
    relative_effect = effect / (abs(baseline_value) + 1e-9)
    
    # 3. Define volume_factor
    # For temporal patterns, use more lenient scaling since they represent trends
    # Logarithmic scaling: log(1 + n) / log(1000)
    # This gives: n=1 → ~0.15, n=10 → ~0.50, n=100 → ~0.83, n=1000 → 1.0
    # For temporal patterns, adjust denominator to be more lenient
    if is_temporal_pattern:
        # More lenient: log(1 + n) / log(100) instead of log(1000)
        # This gives: n=4 → ~0.47, n=10 → ~0.70, n=20 → ~0.87
        volume_factor = min(1.0, np.log(1 + sample_size) / np.log(100))
    else:
        volume_factor = min(1.0, np.log(1 + sample_size) / np.log(1000))
    
    # 4. Combine: raw_support
    raw_support = relative_effect * volume_factor
    
    # 5. Normalize support into 0-1 range using exponential
    # support = 1 - exp(-5 * raw_support)
    # This maps: raw_support=0 → support=0, raw_support=0.2 → support≈0.63, raw_support=1.0 → support≈0.993
    support = 1 - np.exp(-5 * raw_support)
    
    # 6. Clamp support to [0, 1]
    support = max(0.0, min(1.0, support))
    
    return support
