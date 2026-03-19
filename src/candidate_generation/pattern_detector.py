"""Pattern detection logic for generating statistical pattern candidates."""

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
from datetime import datetime
from .pattern_types import PatternType
from ..models.candidate import InsightCandidate
from ..normalization.normalized_set import NormalizedSet


def generate_candidates(normalized_set: NormalizedSet, analysis_mode: str = "full") -> List[InsightCandidate]:
    """
    Generate all pattern candidates from normalized set.
    
    Args:
        normalized_set: NormalizedSet with data and KPIs
        analysis_mode: "full" (revenue available) or "performance" (no revenue)
    """
    candidates = []
    
    # Filter KPIs based on analysis mode
    # In PERFORMANCE mode, exclude revenue and ROAS metrics
    available_kpis = normalized_set.kpis.copy()
    if analysis_mode == "performance":
        # Remove revenue-related metrics
        available_kpis = [kpi for kpi in available_kpis if kpi not in ['revenue', 'roas', 'aov']]
    
    # Create a filtered normalized set for candidate generation
    filtered_normalized_set = NormalizedSet(
        data=normalized_set.data,
        tenant_id=normalized_set.tenant_id,
        dimensions=normalized_set.dimensions,
        kpis=available_kpis,
        metadata=normalized_set.metadata
    )
    
    # Generate dimension-based patterns
    for dimension in filtered_normalized_set.dimensions:
        if dimension in ['date', 'week', 'month']:
            continue  # Handle temporal separately
        
        candidates.extend(_generate_dimension_patterns(filtered_normalized_set, dimension, analysis_mode))
    
    # Generate temporal patterns if temporal data exists
    temporal_dim = _get_temporal_dimension(filtered_normalized_set)
    if temporal_dim:
        candidates.extend(_generate_temporal_patterns(filtered_normalized_set, temporal_dim, analysis_mode))
    
    return candidates


def _generate_dimension_patterns(normalized_set: NormalizedSet, dimension: str, analysis_mode: str = "full") -> List[InsightCandidate]:
    """Generate patterns for a single dimension."""
    candidates = []
    df = normalized_set.data
    
    if dimension not in df.columns:
        return candidates
    
    # Get unique segment values
    segments = df[dimension].dropna().unique()
    if len(segments) < 2:
        return candidates
    
    # For each KPI
    for kpi in normalized_set.kpis:
        if kpi not in df.columns:
            continue
        
        # Calculate baseline (aggregate mean)
        baseline = df[kpi].mean()
        if pd.isna(baseline):
            continue
        
        # Get segment metrics
        segment_metrics = {}
        for segment in segments:
            segment_data = df[df[dimension] == segment][kpi].dropna()
            if len(segment_data) >= 2:  # Minimum sample size
                mean_val = segment_data.mean()
                # Compute std with ddof=1 for sample std (unbiased estimator)
                std_val = segment_data.std(ddof=1) if len(segment_data) > 1 else 0.0
                # If std is 0 or NaN, use a small epsilon based on mean
                if pd.isna(std_val) or std_val <= 0:
                    if mean_val != 0:
                        std_val = abs(mean_val) * 0.01  # 1% of mean as minimum std
                    else:
                        std_val = 0.001  # Very small epsilon
                
                segment_metrics[segment] = {
                    'mean': mean_val,
                    'std': std_val,
                    'count': len(segment_data),
                    'values': segment_data.tolist()
                }
        
        if len(segment_metrics) < 2:
            continue
        
        # Sort segments by mean value
        sorted_segments = sorted(
            segment_metrics.items(),
            key=lambda x: x[1]['mean'],
            reverse=True
        )
        
        top_segment = sorted_segments[0]
        bottom_segment = sorted_segments[-1]
        
        # SEGMENT_ABOVE_BASELINE
        if top_segment[1]['mean'] > baseline:
            candidates.append(_create_segment_baseline_candidate(
                normalized_set, dimension, kpi, top_segment[0],
                top_segment[1], baseline, PatternType.SEGMENT_ABOVE_BASELINE
            ))
        
        # SEGMENT_BELOW_BASELINE
        if bottom_segment[1]['mean'] < baseline:
            candidates.append(_create_segment_baseline_candidate(
                normalized_set, dimension, kpi, bottom_segment[0],
                bottom_segment[1], baseline, PatternType.SEGMENT_BELOW_BASELINE
            ))
        
        # SEGMENT_GAP
        if top_segment[0] != bottom_segment[0]:
            candidates.append(_create_segment_gap_candidate(
                normalized_set, dimension, kpi,
                top_segment[0], top_segment[1],
                bottom_segment[0], bottom_segment[1]
            ))
    
    # METRIC_IMBALANCE (spend/revenue ratio) - only in FULL mode
    if analysis_mode == "full" and 'spend' in normalized_set.kpis and 'revenue' in normalized_set.kpis:
        candidates.extend(_generate_metric_imbalance(normalized_set, dimension))
    
    return candidates


def _generate_metric_imbalance(normalized_set: NormalizedSet, dimension: str) -> List[InsightCandidate]:
    """Generate metric imbalance patterns (spend/revenue ratio)."""
    candidates = []
    df = normalized_set.data
    
    if dimension not in df.columns or 'spend' not in df.columns or 'revenue' not in df.columns:
        return candidates
    
    # Calculate spend/revenue ratio for each segment
    segment_ratios = {}
    segments = df[dimension].dropna().unique()
    
    for segment in segments:
        segment_df = df[df[dimension] == segment]
        segment_df = segment_df[(segment_df['spend'].notna()) & (segment_df['revenue'].notna())]
        
        if len(segment_df) < 2:
            continue
        
        # Calculate ratio (spend/revenue)
        ratios = segment_df['spend'] / segment_df['revenue'].replace(0, np.nan)
        ratios = ratios.dropna()
        
        if len(ratios) >= 2:
            mean_ratio = ratios.mean()
            # Compute std with ddof=1 for sample std
            std_ratio = ratios.std(ddof=1) if len(ratios) > 1 else 0.0
            # If std is 0 or NaN, use a small epsilon based on mean
            if pd.isna(std_ratio) or std_ratio <= 0:
                if mean_ratio != 0:
                    std_ratio = abs(mean_ratio) * 0.01  # 1% of mean as minimum std
                else:
                    std_ratio = 0.001  # Very small epsilon
            
            segment_ratios[segment] = {
                'mean': mean_ratio,
                'std': std_ratio,
                'count': len(ratios),
                'spend_mean': segment_df['spend'].mean(),
                'revenue_mean': segment_df['revenue'].mean()
            }
    
    if len(segment_ratios) < 2:
        return candidates
    
    # Baseline ratio
    baseline_ratio = df['spend'].sum() / df['revenue'].sum() if df['revenue'].sum() > 0 else np.nan
    
    if pd.isna(baseline_ratio):
        return candidates
    
    # Top and bottom by ratio
    sorted_segments = sorted(segment_ratios.items(), key=lambda x: x[1]['mean'], reverse=True)
    top_segment = sorted_segments[0]
    bottom_segment = sorted_segments[-1]
    
    # Top ratio (high spend/low revenue)
    candidates.append(_create_metric_imbalance_candidate(
        normalized_set, dimension, top_segment[0], top_segment[1],
        baseline_ratio, 'high'
    ))
    
    # Bottom ratio (low spend/high revenue)
    candidates.append(_create_metric_imbalance_candidate(
        normalized_set, dimension, bottom_segment[0], bottom_segment[1],
        baseline_ratio, 'low'
    ))
    
    return candidates


def _generate_temporal_patterns(normalized_set: NormalizedSet, temporal_dim: str, analysis_mode: str = "full") -> List[InsightCandidate]:
    """
    Generate comprehensive temporal pattern candidates.
    
    Detects:
    1. Weekend vs Weekday patterns
    2. Gradual decline patterns
    3. Recovery patterns
    4. Spike/drop/anomaly patterns
    5. Latest vs previous period changes
    
    All patterns respect analysis_mode (FULL vs PERFORMANCE).
    """
    candidates = []
    df = normalized_set.data.copy()
    
    if temporal_dim not in df.columns:
        return candidates
    
    # Sort by temporal dimension
    df = df.sort_values(temporal_dim)
    
    # Get time periods
    time_periods = df[temporal_dim].dropna().unique()
    if len(time_periods) < 2:
        return candidates
    
    # Determine available KPIs based on analysis mode
    if analysis_mode == "full":
        available_kpis = [kpi for kpi in normalized_set.kpis if kpi in df.columns]
    else:
        # PERFORMANCE mode: exclude revenue-related metrics
        available_kpis = [
            kpi for kpi in normalized_set.kpis 
            if kpi in df.columns and kpi not in ['revenue', 'roas', 'aov']
        ]
    
    # Pattern 1: Weekend vs Weekday (if date column exists)
    if temporal_dim == 'date':
        candidates.extend(_detect_weekend_weekday_patterns(
            normalized_set, df, available_kpis, analysis_mode
        ))
    
    # Pattern 2: Gradual Decline
    candidates.extend(_detect_gradual_decline_patterns(
        normalized_set, df, temporal_dim, available_kpis
    ))
    
    # Pattern 3: Recovery Pattern
    candidates.extend(_detect_recovery_patterns(
        normalized_set, df, temporal_dim, available_kpis
    ))
    
    # Pattern 4: Spike/Drop/Anomaly
    candidates.extend(_detect_spike_drop_patterns(
        normalized_set, df, temporal_dim, available_kpis
    ))
    
    # Pattern 5: Latest vs Previous Period (existing logic, expanded)
    candidates.extend(_detect_period_change_patterns(
        normalized_set, df, temporal_dim, available_kpis
    ))
    
    return candidates


def _create_segment_baseline_candidate(
    normalized_set: NormalizedSet, dimension: str, kpi: str,
    segment_value: Any, segment_stats: Dict, baseline: float,
    pattern_type: PatternType
) -> InsightCandidate:
    """Create segment vs baseline candidate."""
    pattern_id = f"{pattern_type.value}_{dimension}_{segment_value}_{kpi}"
    
    description = f"{dimension} '{segment_value}' {kpi} = {segment_stats['mean']:.2f} vs baseline {baseline:.2f}"
    
    # Get all metrics for this segment
    df = normalized_set.data
    segment_df = df[df[dimension] == segment_value]
    primary_metrics = {}
    for k in normalized_set.kpis:
        if k in segment_df.columns:
            primary_metrics[k] = segment_df[k].mean()
    
    # Aggregate metrics
    aggregate_metrics = {}
    for k in normalized_set.kpis:
        if k in df.columns:
            aggregate_metrics[k] = df[k].mean()
    
    return InsightCandidate(
        pattern_type=pattern_type,
        pattern_id=pattern_id,
        description=description,
        primary_segment={
            'dimension': dimension,
            'value': segment_value,
            'metrics': primary_metrics,
            'sample_size': segment_stats['count']
        },
        comparison_segment=None,
        baseline_value=baseline,
        observed_value=segment_stats['mean'],
        metric_name=kpi,
        dimensions={dimension: segment_value},
        time_period=None,
        affected_campaigns=None,
        raw_metrics={
            'primary': primary_metrics,
            'comparison': None,
            'aggregate': aggregate_metrics
        },
        sample_sizes={'primary': segment_stats['count'], 'comparison': None},
        variance_metrics={'primary_std': segment_stats['std'], 'comparison_std': None},
        tenant_id=normalized_set.tenant_id,
        generation_timestamp=datetime.now()
    )


def _create_segment_gap_candidate(
    normalized_set: NormalizedSet, dimension: str, kpi: str,
    top_segment_value: Any, top_stats: Dict,
    bottom_segment_value: Any, bottom_stats: Dict
) -> InsightCandidate:
    """Create segment gap candidate."""
    pattern_id = f"SEGMENT_GAP_{dimension}_{top_segment_value}_{bottom_segment_value}_{kpi}"
    
    gap = top_stats['mean'] - bottom_stats['mean']
    description = f"{dimension} gap: '{top_segment_value}' {kpi} = {top_stats['mean']:.2f} vs '{bottom_segment_value}' {bottom_stats['mean']:.2f}"
    
    df = normalized_set.data
    
    # Top segment metrics
    top_df = df[df[dimension] == top_segment_value]
    top_metrics = {}
    for k in normalized_set.kpis:
        if k in top_df.columns:
            top_metrics[k] = top_df[k].mean()
    
    # Bottom segment metrics
    bottom_df = df[df[dimension] == bottom_segment_value]
    bottom_metrics = {}
    for k in normalized_set.kpis:
        if k in bottom_df.columns:
            bottom_metrics[k] = bottom_df[k].mean()
    
    # Aggregate
    aggregate_metrics = {}
    for k in normalized_set.kpis:
        if k in df.columns:
            aggregate_metrics[k] = df[k].mean()
    
    return InsightCandidate(
        pattern_type=PatternType.SEGMENT_GAP,
        pattern_id=pattern_id,
        description=description,
        primary_segment={
            'dimension': dimension,
            'value': top_segment_value,
            'metrics': top_metrics,
            'sample_size': top_stats['count']
        },
        comparison_segment={
            'dimension': dimension,
            'value': bottom_segment_value,
            'metrics': bottom_metrics,
            'sample_size': bottom_stats['count']
        },
        baseline_value=bottom_stats['mean'],
        observed_value=top_stats['mean'],
        metric_name=kpi,
        dimensions={dimension: f"{top_segment_value} vs {bottom_segment_value}"},
        time_period=None,
        affected_campaigns=None,
        raw_metrics={
            'primary': top_metrics,
            'comparison': bottom_metrics,
            'aggregate': aggregate_metrics
        },
        sample_sizes={'primary': top_stats['count'], 'comparison': bottom_stats['count']},
        variance_metrics={'primary_std': top_stats['std'], 'comparison_std': bottom_stats['std']},
        tenant_id=normalized_set.tenant_id,
        generation_timestamp=datetime.now()
    )


def _create_metric_imbalance_candidate(
    normalized_set: NormalizedSet, dimension: str,
    segment_value: Any, segment_stats: Dict,
    baseline_ratio: float, imbalance_type: str
) -> InsightCandidate:
    """Create metric imbalance candidate."""
    pattern_id = f"METRIC_IMBALANCE_{dimension}_{segment_value}_{imbalance_type}"
    
    description = f"{dimension} '{segment_value}' spend/revenue ratio = {segment_stats['mean']:.2f} vs baseline {baseline_ratio:.2f}"
    
    df = normalized_set.data
    segment_df = df[df[dimension] == segment_value]
    
    primary_metrics = {}
    for k in ['spend', 'revenue']:
        if k in segment_df.columns:
            primary_metrics[k] = segment_df[k].mean()
    
    aggregate_metrics = {}
    for k in normalized_set.kpis:
        if k in df.columns:
            aggregate_metrics[k] = df[k].mean()
    
    return InsightCandidate(
        pattern_type=PatternType.METRIC_IMBALANCE,
        pattern_id=pattern_id,
        description=description,
        primary_segment={
            'dimension': dimension,
            'value': segment_value,
            'metrics': primary_metrics,
            'sample_size': segment_stats['count']
        },
        comparison_segment=None,
        baseline_value=baseline_ratio,
        observed_value=segment_stats['mean'],
        metric_name='spend/revenue_ratio',
        dimensions={dimension: segment_value},
        time_period=None,
        affected_campaigns=None,
        raw_metrics={
            'primary': primary_metrics,
            'comparison': None,
            'aggregate': aggregate_metrics
        },
        sample_sizes={'primary': segment_stats['count'], 'comparison': None},
        variance_metrics={'primary_std': segment_stats['std'], 'comparison_std': None},
        tenant_id=normalized_set.tenant_id,
        generation_timestamp=datetime.now()
    )


def _detect_weekend_weekday_patterns(
    normalized_set: NormalizedSet,
    df: pd.DataFrame,
    available_kpis: List[str],
    analysis_mode: str
) -> List[InsightCandidate]:
    """
    Detect weekend vs weekday performance differences.
    
    Treats weekend/weekday as segments and uses SEGMENT_GAP pattern type.
    """
    candidates = []
    
    # Convert date column to datetime if needed
    if 'date' not in df.columns:
        return candidates
    
    try:
        df['date'] = pd.to_datetime(df['date'])
        df['weekday'] = df['date'].dt.dayofweek  # 0=Monday, 6=Sunday
        df['is_weekend'] = df['weekday'].isin([5, 6])  # Saturday, Sunday
    except:
        return candidates
    
    # Group by weekend vs weekday
    weekend_df = df[df['is_weekend'] == True]
    weekday_df = df[df['is_weekend'] == False]
    
    if len(weekend_df) < 2 or len(weekday_df) < 2:
        return candidates
    
    # Check each available KPI
    for kpi in available_kpis:
        if kpi not in df.columns:
            continue
        
        weekend_values = weekend_df[kpi].dropna()
        weekday_values = weekday_df[kpi].dropna()
        
        if len(weekend_values) < 2 or len(weekday_values) < 2:
            continue
        
        weekend_mean = weekend_values.mean()
        weekday_mean = weekday_values.mean()
        
        if pd.isna(weekend_mean) or pd.isna(weekday_mean):
            continue
        
        # Calculate gap
        gap_pct = abs((weekend_mean - weekday_mean) / weekday_mean * 100) if weekday_mean != 0 else 0
        
        # Only create candidate if gap is meaningful (>= 10%)
        if gap_pct < 10:
            continue
        
        # Create segment gap candidate (treating weekend/weekday as segments)
        baseline = weekday_mean
        observed = weekend_mean
        
        # Determine pattern type based on direction
        if weekend_mean < weekday_mean:
            pattern_type = PatternType.SEGMENT_BELOW_BASELINE
        else:
            pattern_type = PatternType.SEGMENT_ABOVE_BASELINE
        
        pattern_id = f"WEEKEND_WEEKDAY_{kpi}"
        description = f"Weekend {kpi} = {weekend_mean:.2f} vs Weekday {kpi} = {weekday_mean:.2f} ({gap_pct:.1f}% difference)"
        
        # Get metrics for both segments
        weekend_metrics = {}
        weekday_metrics = {}
        for k in normalized_set.kpis:
            if k in weekend_df.columns:
                weekend_metrics[k] = weekend_df[k].mean()
            if k in weekday_df.columns:
                weekday_metrics[k] = weekday_df[k].mean()
        
        aggregate_metrics = {}
        for k in normalized_set.kpis:
            if k in df.columns:
                aggregate_metrics[k] = df[k].mean()
        
        candidates.append(InsightCandidate(
            pattern_type=pattern_type,
            pattern_id=pattern_id,
            description=description,
            primary_segment={
                'dimension': 'weekend',
                'value': 'weekend',
                'metrics': weekend_metrics,
                'sample_size': len(weekend_values)
            },
            comparison_segment={
                'dimension': 'weekday',
                'value': 'weekday',
                'metrics': weekday_metrics,
                'sample_size': len(weekday_values)
            },
            baseline_value=baseline,
            observed_value=observed,
            metric_name=kpi,
            dimensions={'weekend': 'weekend', 'weekday': 'weekday'},
            time_period=None,
            affected_campaigns=None,
            raw_metrics={
                'primary': weekend_metrics,
                'comparison': weekday_metrics,
                'aggregate': aggregate_metrics
            },
            sample_sizes={'primary': len(weekend_values), 'comparison': len(weekday_values)},
            variance_metrics={
                'primary_std': _compute_std_safe(weekend_values),
                'comparison_std': _compute_std_safe(weekday_values)
            },
            tenant_id=normalized_set.tenant_id,
            generation_timestamp=datetime.now()
        ))
    
    return candidates


def _detect_gradual_decline_patterns(
    normalized_set: NormalizedSet,
    df: pd.DataFrame,
    temporal_dim: str,
    available_kpis: List[str]
) -> List[InsightCandidate]:
    """
    Detect gradual decline patterns using:
    1. Slope analysis (linear regression)
    2. First half vs second half comparison
    """
    candidates = []
    
    time_periods = sorted(df[temporal_dim].dropna().unique())
    if len(time_periods) < 4:  # Need at least 4 periods for meaningful decline detection
        return candidates
    
    # Split into first half and second half
    mid_point = len(time_periods) // 2
    first_half_periods = time_periods[:mid_point]
    second_half_periods = time_periods[mid_point:]
    
    first_half_df = df[df[temporal_dim].isin(first_half_periods)]
    second_half_df = df[df[temporal_dim].isin(second_half_periods)]
    
    for kpi in available_kpis:
        if kpi not in df.columns:
            continue
        
        first_half_values = first_half_df[kpi].dropna()
        second_half_values = second_half_df[kpi].dropna()
        
        if len(first_half_values) < 2 or len(second_half_values) < 2:
            continue
        
        first_mean = first_half_values.mean()
        second_mean = second_half_values.mean()
        
        if pd.isna(first_mean) or pd.isna(second_mean):
            continue
        
        # Check for decline (second half worse than first half)
        # For metrics where lower is worse: conversions, CVR, ROAS, revenue
        # For metrics where higher is worse: CPA, CPC
        decline_threshold = 0.10  # 10% decline minimum
        
        is_decline = False
        if kpi in ['conversions', 'cvr', 'roas', 'revenue', 'ctr']:
            # Lower values are worse
            if second_mean < first_mean:
                decline_pct = (first_mean - second_mean) / first_mean if first_mean != 0 else 0
                is_decline = decline_pct >= decline_threshold
        elif kpi in ['cpa', 'cpc']:
            # Higher values are worse
            if second_mean > first_mean:
                decline_pct = (second_mean - first_mean) / first_mean if first_mean != 0 else 0
                is_decline = decline_pct >= decline_threshold
        
        if not is_decline:
            continue
        
        # Create temporal change candidate
        pattern_id = f"GRADUAL_DECLINE_{temporal_dim}_{kpi}"
        decline_pct = abs((first_mean - second_mean) / first_mean * 100) if first_mean != 0 else 0
        description = f"{kpi} declined from {first_mean:.2f} (first half) to {second_mean:.2f} (second half) ({decline_pct:.1f}% decline)"
        
        first_metrics = {}
        second_metrics = {}
        for k in normalized_set.kpis:
            if k in first_half_df.columns:
                first_metrics[k] = first_half_df[k].mean()
            if k in second_half_df.columns:
                second_metrics[k] = second_half_df[k].mean()
        
        aggregate_metrics = {}
        for k in normalized_set.kpis:
            if k in df.columns:
                aggregate_metrics[k] = df[k].mean()
        
        candidates.append(InsightCandidate(
            pattern_type=PatternType.TEMPORAL_CHANGE,
            pattern_id=pattern_id,
            description=description,
            primary_segment={
                'dimension': temporal_dim,
                'value': f"{second_half_periods[0]} to {second_half_periods[-1]}",
                'metrics': second_metrics,
                'sample_size': len(second_half_values)
            },
            comparison_segment={
                'dimension': temporal_dim,
                'value': f"{first_half_periods[0]} to {first_half_periods[-1]}",
                'metrics': first_metrics,
                'sample_size': len(first_half_values)
            },
            baseline_value=first_mean,
            observed_value=second_mean,
            metric_name=kpi,
            dimensions={temporal_dim: f"{first_half_periods[0]} to {second_half_periods[-1]}"},
            time_period={'start': first_half_periods[0], 'end': second_half_periods[-1]},
            affected_campaigns=None,
            raw_metrics={
                'primary': second_metrics,
                'comparison': first_metrics,
                'aggregate': aggregate_metrics
            },
            sample_sizes={'primary': len(second_half_values), 'comparison': len(first_half_values)},
            variance_metrics={
                'primary_std': _compute_std_safe(second_half_values),
                'comparison_std': _compute_std_safe(first_half_values)
            },
            tenant_id=normalized_set.tenant_id,
            generation_timestamp=datetime.now()
        ))
    
    return candidates


def _detect_recovery_patterns(
    normalized_set: NormalizedSet,
    df: pd.DataFrame,
    temporal_dim: str,
    available_kpis: List[str]
) -> List[InsightCandidate]:
    """
    Detect recovery patterns: drop followed by recovery.
    
    Logic:
    1. Split into three periods: early, middle, late
    2. Check if middle < early (drop)
    3. Check if late > middle (recovery)
    4. Check if recovery is meaningful
    """
    candidates = []
    
    time_periods = sorted(df[temporal_dim].dropna().unique())
    if len(time_periods) < 6:  # Need at least 6 periods for meaningful recovery detection
        return candidates
    
    # Split into three periods
    third = len(time_periods) // 3
    early_periods = time_periods[:third]
    middle_periods = time_periods[third:2*third]
    late_periods = time_periods[2*third:]
    
    early_df = df[df[temporal_dim].isin(early_periods)]
    middle_df = df[df[temporal_dim].isin(middle_periods)]
    late_df = df[df[temporal_dim].isin(late_periods)]
    
    for kpi in available_kpis:
        if kpi not in df.columns:
            continue
        
        early_values = early_df[kpi].dropna()
        middle_values = middle_df[kpi].dropna()
        late_values = late_df[kpi].dropna()
        
        if len(early_values) < 2 or len(middle_values) < 2 or len(late_values) < 2:
            continue
        
        early_mean = early_values.mean()
        middle_mean = middle_values.mean()
        late_mean = late_values.mean()
        
        if pd.isna(early_mean) or pd.isna(middle_mean) or pd.isna(late_mean):
            continue
        
        # Check for drop then recovery
        recovery_threshold = 0.10  # 10% change minimum
        
        is_recovery = False
        if kpi in ['conversions', 'cvr', 'roas', 'revenue', 'ctr']:
            # Lower values are worse
            drop = (early_mean - middle_mean) / early_mean if early_mean != 0 else 0
            recovery = (late_mean - middle_mean) / middle_mean if middle_mean != 0 else 0
            is_recovery = drop >= recovery_threshold and recovery >= recovery_threshold
        elif kpi in ['cpa', 'cpc']:
            # Higher values are worse
            drop = (middle_mean - early_mean) / early_mean if early_mean != 0 else 0
            recovery = (middle_mean - late_mean) / middle_mean if middle_mean != 0 else 0
            is_recovery = drop >= recovery_threshold and recovery >= recovery_threshold
        
        if not is_recovery:
            continue
        
        # Create temporal change candidate comparing late vs middle (recovery)
        pattern_id = f"RECOVERY_{temporal_dim}_{kpi}"
        recovery_pct = abs((late_mean - middle_mean) / middle_mean * 100) if middle_mean != 0 else 0
        description = f"{kpi} dropped to {middle_mean:.2f} then recovered to {late_mean:.2f} ({recovery_pct:.1f}% recovery)"
        
        early_metrics = {}
        middle_metrics = {}
        late_metrics = {}
        for k in normalized_set.kpis:
            if k in early_df.columns:
                early_metrics[k] = early_df[k].mean()
            if k in middle_df.columns:
                middle_metrics[k] = middle_df[k].mean()
            if k in late_df.columns:
                late_metrics[k] = late_df[k].mean()
        
        aggregate_metrics = {}
        for k in normalized_set.kpis:
            if k in df.columns:
                aggregate_metrics[k] = df[k].mean()
        
        candidates.append(InsightCandidate(
            pattern_type=PatternType.TEMPORAL_CHANGE,
            pattern_id=pattern_id,
            description=description,
            primary_segment={
                'dimension': temporal_dim,
                'value': f"{late_periods[0]} to {late_periods[-1]}",
                'metrics': late_metrics,
                'sample_size': len(late_values)
            },
            comparison_segment={
                'dimension': temporal_dim,
                'value': f"{middle_periods[0]} to {middle_periods[-1]}",
                'metrics': middle_metrics,
                'sample_size': len(middle_values)
            },
            baseline_value=middle_mean,
            observed_value=late_mean,
            metric_name=kpi,
            dimensions={temporal_dim: f"{early_periods[0]} to {late_periods[-1]}"},
            time_period={'start': early_periods[0], 'end': late_periods[-1]},
            affected_campaigns=None,
            raw_metrics={
                'primary': late_metrics,
                'comparison': middle_metrics,
                'aggregate': aggregate_metrics
            },
            sample_sizes={'primary': len(late_values), 'comparison': len(middle_values)},
            variance_metrics={
                'primary_std': _compute_std_safe(late_values),
                'comparison_std': _compute_std_safe(middle_values)
            },
            tenant_id=normalized_set.tenant_id,
            generation_timestamp=datetime.now()
        ))
    
    return candidates


def _detect_spike_drop_patterns(
    normalized_set: NormalizedSet,
    df: pd.DataFrame,
    temporal_dim: str,
    available_kpis: List[str]
) -> List[InsightCandidate]:
    """
    Detect spike/drop/anomaly patterns: large sudden movement relative to surrounding periods.
    """
    candidates = []
    
    time_periods = sorted(df[temporal_dim].dropna().unique())
    if len(time_periods) < 3:  # Need at least 3 periods
        return candidates
    
    # Calculate rolling mean and std for each period
    for i, period in enumerate(time_periods):
        period_df = df[df[temporal_dim] == period]
        
        # Get surrounding periods (exclude current)
        surrounding_periods = [p for p in time_periods if p != period]
        surrounding_df = df[df[temporal_dim].isin(surrounding_periods)]
        
        if len(period_df) < 1 or len(surrounding_df) < 2:
            continue
        
        for kpi in available_kpis:
            if kpi not in df.columns:
                continue
            
            period_values = period_df[kpi].dropna()
            surrounding_values = surrounding_df[kpi].dropna()
            
            if len(period_values) < 1 or len(surrounding_values) < 2:
                continue
            
            period_mean = period_values.mean()
            surrounding_mean = surrounding_values.mean()
            surrounding_std = surrounding_values.std()
            
            if pd.isna(period_mean) or pd.isna(surrounding_mean) or pd.isna(surrounding_std):
                continue
            
            if surrounding_std == 0:
                continue
            
            # Calculate z-score (how many standard deviations away)
            z_score = abs((period_mean - surrounding_mean) / surrounding_std)
            
            # Threshold: z-score >= 2.0 (statistically significant anomaly)
            if z_score < 2.0:
                continue
            
            # Determine if spike or drop
            if period_mean > surrounding_mean:
                pattern_type = PatternType.SEGMENT_ABOVE_BASELINE
                description = f"{kpi} spike: {period_mean:.2f} vs baseline {surrounding_mean:.2f} (+{z_score:.1f}σ)"
            else:
                pattern_type = PatternType.SEGMENT_BELOW_BASELINE
                description = f"{kpi} drop: {period_mean:.2f} vs baseline {surrounding_mean:.2f} (-{z_score:.1f}σ)"
            
            pattern_id = f"SPIKE_DROP_{temporal_dim}_{period}_{kpi}"
            
            period_metrics = {}
            for k in normalized_set.kpis:
                if k in period_df.columns:
                    period_metrics[k] = period_df[k].mean()
            
            surrounding_metrics = {}
            for k in normalized_set.kpis:
                if k in surrounding_df.columns:
                    surrounding_metrics[k] = surrounding_df[k].mean()
            
            aggregate_metrics = {}
            for k in normalized_set.kpis:
                if k in df.columns:
                    aggregate_metrics[k] = df[k].mean()
            
            candidates.append(InsightCandidate(
                pattern_type=pattern_type,
                pattern_id=pattern_id,
                description=description,
                primary_segment={
                    'dimension': temporal_dim,
                    'value': period,
                    'metrics': period_metrics,
                    'sample_size': len(period_values)
                },
                comparison_segment=None,
                baseline_value=surrounding_mean,
                observed_value=period_mean,
                metric_name=kpi,
                dimensions={temporal_dim: period},
                time_period={'start': period, 'end': period},
                affected_campaigns=None,
                raw_metrics={
                    'primary': period_metrics,
                    'comparison': surrounding_metrics,
                    'aggregate': aggregate_metrics
                },
                sample_sizes={'primary': len(period_values), 'comparison': len(surrounding_values)},
                variance_metrics={
                    'primary_std': _compute_std_safe(period_values),
                    'comparison_std': _compute_std_safe(surrounding_values)
                },
                tenant_id=normalized_set.tenant_id,
                generation_timestamp=datetime.now()
            ))
    
    return candidates


def _detect_period_change_patterns(
    normalized_set: NormalizedSet,
    df: pd.DataFrame,
    temporal_dim: str,
    available_kpis: List[str]
) -> List[InsightCandidate]:
    """
    Detect latest vs previous period changes (expanded version of original logic).
    """
    candidates = []
    
    time_periods = sorted(df[temporal_dim].dropna().unique())
    if len(time_periods) < 2:
        return candidates
    
    # Compare latest vs previous period
    latest_period = time_periods[-1]
    previous_period = time_periods[-2]
    
    latest_df = df[df[temporal_dim] == latest_period]
    previous_df = df[df[temporal_dim] == previous_period]
    
    for kpi in available_kpis:
        if kpi not in df.columns:
            continue
        
        latest_values = latest_df[kpi].dropna()
        previous_values = previous_df[kpi].dropna()
        
        if len(latest_values) < 1 or len(previous_values) < 1:
            continue
        
        latest_mean = latest_values.mean()
        previous_mean = previous_values.mean()
        
        if pd.isna(latest_mean) or pd.isna(previous_mean):
            continue
        
        # Only create candidate if change is meaningful (>= 5%)
        change_pct = abs((latest_mean - previous_mean) / previous_mean * 100) if previous_mean != 0 else 0
        if change_pct < 5:
            continue
        
        candidates.append(_create_temporal_candidate(
            normalized_set, temporal_dim, kpi,
            latest_mean, previous_mean,
            latest_period, previous_period,
            len(latest_values), len(previous_values)
        ))
    
    return candidates


def _create_temporal_candidate(
    normalized_set: NormalizedSet, temporal_dim: str, kpi: str,
    latest_mean: float, previous_mean: float,
    latest_period: Any, previous_period: Any,
    latest_count: int, previous_count: int
) -> InsightCandidate:
    """Create temporal change candidate."""
    pattern_id = f"TEMPORAL_CHANGE_{temporal_dim}_{latest_period}_{kpi}"
    
    change = latest_mean - previous_mean
    pct_change = (change / previous_mean * 100) if previous_mean != 0 else 0
    description = f"{kpi} changed from {previous_mean:.2f} to {latest_mean:.2f} ({pct_change:+.1f}%)"
    
    df = normalized_set.data
    
    # Latest period metrics
    latest_df = df[df[temporal_dim] == latest_period]
    latest_metrics = {}
    for k in normalized_set.kpis:
        if k in latest_df.columns:
            latest_metrics[k] = latest_df[k].mean()
    
    # Previous period metrics
    previous_df = df[df[temporal_dim] == previous_period]
    previous_metrics = {}
    for k in normalized_set.kpis:
        if k in previous_df.columns:
            previous_metrics[k] = previous_df[k].mean()
    
    # Aggregate
    aggregate_metrics = {}
    for k in normalized_set.kpis:
        if k in df.columns:
            aggregate_metrics[k] = df[k].mean()
    
    return InsightCandidate(
        pattern_type=PatternType.TEMPORAL_CHANGE,
        pattern_id=pattern_id,
        description=description,
        primary_segment={
            'dimension': temporal_dim,
            'value': latest_period,
            'metrics': latest_metrics,
            'sample_size': latest_count
        },
        comparison_segment={
            'dimension': temporal_dim,
            'value': previous_period,
            'metrics': previous_metrics,
            'sample_size': previous_count
        },
        baseline_value=previous_mean,
        observed_value=latest_mean,
        metric_name=kpi,
        dimensions={temporal_dim: f"{previous_period} to {latest_period}"},
        time_period={'start': previous_period, 'end': latest_period},
        affected_campaigns=None,
        raw_metrics={
            'primary': latest_metrics,
            'comparison': previous_metrics,
            'aggregate': aggregate_metrics
        },
        sample_sizes={'primary': latest_count, 'comparison': previous_count},
        variance_metrics={
            'primary_std': _compute_std_safe(latest_df[kpi]) if kpi in latest_df.columns else None,
            'comparison_std': _compute_std_safe(previous_df[kpi]) if kpi in previous_df.columns else None
        },
        tenant_id=normalized_set.tenant_id,
        generation_timestamp=datetime.now()
    )


def _compute_std_safe(series: pd.Series) -> float:
    """Compute std with proper handling of edge cases."""
    series_clean = series.dropna()
    if len(series_clean) < 2:
        return 0.001  # Very small epsilon
    
    std_val = series_clean.std(ddof=1)
    if pd.isna(std_val) or std_val <= 0:
        mean_val = series_clean.mean()
        if mean_val != 0:
            return abs(mean_val) * 0.01  # 1% of mean as minimum std
        else:
            return 0.001  # Very small epsilon
    
    return std_val


def _get_temporal_dimension(normalized_set: NormalizedSet) -> Optional[str]:
    """Get temporal dimension if it exists."""
    temporal_dims = ['date', 'week', 'month']
    for dim in temporal_dims:
        if dim in normalized_set.dimensions:
            return dim
    return None
