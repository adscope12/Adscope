"""Business impact weight calculations."""

import numpy as np
import pandas as pd
from ..models.candidate import InsightCandidate


def calculate_business_impact(candidate: InsightCandidate) -> float:
    """
    Calculate business impact weight (0-1 scale).
    
    Based on revenue/spend magnitude, scale factor, and KPI importance.
    """
    from ..candidate_generation.pattern_types import PatternType
    
    raw_metrics = candidate.raw_metrics
    aggregate = raw_metrics.get('aggregate', {})
    primary = raw_metrics.get('primary', {})
    
    # Check if revenue is available (determines analysis mode)
    has_revenue = 'revenue' in aggregate or 'revenue' in primary
    
    # Special handling for temporal patterns: use aggregate metrics instead of segment metrics
    # Temporal patterns (weekend/weekday, gradual decline, etc.) represent overall dataset trends
    # Using segment metrics would unfairly penalize them
    is_temporal_pattern = (
        candidate.pattern_type == PatternType.TEMPORAL_CHANGE or
        'weekend' in str(candidate.dimensions).lower() or
        'weekday' in str(candidate.dimensions).lower() or
        candidate.pattern_id.startswith(('GRADUAL_DECLINE', 'RECOVERY', 'SPIKE_DROP', 'WEEKEND_WEEKDAY'))
    )
    
    if is_temporal_pattern:
        # For temporal patterns, use aggregate metrics to represent overall impact
        # This ensures temporal insights aren't penalized for having smaller segment sizes
        revenue = aggregate.get('revenue', 0)
        total_revenue = aggregate.get('revenue', 1)
        spend = aggregate.get('spend', 0)
        total_spend = aggregate.get('spend', 1)
        
        # For temporal patterns, assume they affect the entire dataset
        revenue_magnitude = 1.0 if has_revenue and total_revenue > 0 else 0.0
        spend_magnitude = 1.0 if total_spend > 0 else 0.0
        
        # Use total sample size (primary + comparison) for temporal patterns
        total_sample_size = (
            candidate.sample_sizes.get('primary', 0) + 
            candidate.sample_sizes.get('comparison', 0)
        )
        # For temporal patterns, scale factor should reflect dataset coverage
        # If we have at least 4 periods, give good scale factor
        if total_sample_size >= 4:
            scale_factor = min(1.0, total_sample_size / 20.0)  # 20 periods = 1.0
        else:
            scale_factor = min(1.0, total_sample_size / 10.0)
    else:
        # Original logic for non-temporal patterns
        revenue = primary.get('revenue', 0) or aggregate.get('revenue', 0)
        total_revenue = aggregate.get('revenue', 1)
        if has_revenue and total_revenue > 0:
            revenue_magnitude = min(1.0, revenue / total_revenue)
        else:
            revenue_magnitude = 0.0
        
        spend = primary.get('spend', 0) or aggregate.get('spend', 0)
        total_spend = aggregate.get('spend', 1)
        if total_spend > 0:
            spend_magnitude = min(1.0, spend / total_spend)
        else:
            spend_magnitude = 0.0
        
        # Scale factor (20% weight) - based on sample size relative to total
        sample_size = candidate.sample_sizes.get('primary', 0)
        # Estimate total rows (rough approximation)
        total_estimated = sample_size * 10  # Rough estimate
        if total_estimated > 0:
            scale_factor = min(1.0, sample_size / max(10, total_estimated / 5))
        else:
            scale_factor = min(1.0, sample_size / 10)
    
    # KPI importance weight (10% weight in FULL mode, 20% weight in PERFORMANCE mode)
    kpi_weights = {
        'roas': 1.0,
        'revenue': 1.0,
        'spend': 0.9,
        'cpa': 0.8,
        'cpc': 0.7,
        'ctr': 0.6,
        'cvr': 0.6,
        'aov': 0.7,
        'spend/revenue_ratio': 0.8,
        'conversions': 0.8  # Add conversions
    }
    kpi_weight = kpi_weights.get(candidate.metric_name.lower(), 0.5)
    
    # Combine components - adjust weights based on analysis mode
    if has_revenue:
        # FULL mode: revenue 40%, spend 30%, scale 20%, kpi 10%
        impact = (
            revenue_magnitude * 0.4 +
            spend_magnitude * 0.3 +
            scale_factor * 0.2 +
            kpi_weight * 0.1
        )
    else:
        # PERFORMANCE mode: spend 50%, scale 30%, kpi 20%
        impact = (
            spend_magnitude * 0.5 +
            scale_factor * 0.3 +
            kpi_weight * 0.2
        )
    
    return min(1.0, max(0.0, impact))
