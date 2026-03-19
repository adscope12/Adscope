"""Quality-gated Insight selection to avoid bluffing."""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from ..models.insight import ScoredPatternCandidate
from ..scoring.composite_scorer import MIN_EFFECT_SIZE
from .diversity_selector import _select_with_constraints
from .segment_deduplicator import deduplicate_by_segment_id
from .selection_utils import extract_segment_id


# Quality gate thresholds (configurable)
MIN_COMPOSITE_SCORE = 0.15
MIN_SUPPORT = 0.35
# MIN_EFFECT_SIZE imported from composite_scorer (0.02)


@dataclass
class RejectionInfo:
    """Information about why a candidate was rejected."""
    candidate: ScoredPatternCandidate
    failed_gate: str  # 'composite', 'support', 'effect', 'segment_dup', 'diversity'


@dataclass
class SelectionResult:
    """Result of quality-gated selection with debug statistics."""
    selected: List[ScoredPatternCandidate]
    total_considered: int
    rejected_by_composite: int
    rejected_by_support: int
    rejected_by_effect: int
    rejected_by_segment_dup: int
    rejected_by_diversity_conflict: int
    quality_gate_only_rejections: List[RejectionInfo]  # Top candidates rejected only by quality gates
    selected_per_stage: Dict[int, int] = field(default_factory=dict)  # Stage -> count of insights selected in that stage


def select_quality_gated_insights(
    ranked_patterns: List[ScoredPatternCandidate],
    target_n: int = 4,
    debug: bool = False
) -> SelectionResult:
    """
    Select insights with quality gates and diversity constraints.
    
    Selection process:
    1. Apply hard quality gates (must pass all):
       - composite_score >= MIN_COMPOSITE_SCORE
       - statistical_support >= MIN_SUPPORT
       - effect_size >= MIN_EFFECT_SIZE
    2. Apply diversity constraints (max 1 per metric/dimension, max 2 per segment/pattern_type)
    3. Apply segment deduplication (max 1 per segment_id)
    4. Return up to target_n, but only if they pass quality gates
    
    Quality gates are NEVER relaxed.
    Diversity constraints may be relaxed if eligible candidates remain.
    Segment uniqueness is NEVER relaxed.
    
    Args:
        ranked_patterns: Patterns sorted by composite_score (descending)
        target_n: Target number of insights (default 4)
        debug: If True, return debug statistics
        
    Returns:
        SelectionResult with selected insights and debug statistics
    """
    if not ranked_patterns:
        return SelectionResult(
            selected=[],
            total_considered=0,
            rejected_by_composite=0,
            rejected_by_support=0,
            rejected_by_effect=0,
            rejected_by_segment_dup=0,
            rejected_by_diversity_conflict=0,
            quality_gate_only_rejections=[],
            selected_per_stage={}
        )
    
    # Initialize rejection counters
    rejected_by_composite = 0
    rejected_by_support = 0
    rejected_by_effect = 0
    quality_gate_rejections = []  # Track candidates rejected only by quality gates
    
    # Step 1: Apply hard quality gates and track rejections
    eligible_patterns = []
    for sp in ranked_patterns:
        gate_result = _check_quality_gates(sp)
        if gate_result is None:
            # Passed all gates
            eligible_patterns.append(sp)
        else:
            # Failed a gate - track which one
            failed_gate = gate_result
            if failed_gate == 'composite':
                rejected_by_composite += 1
            elif failed_gate == 'support':
                rejected_by_support += 1
            elif failed_gate == 'effect':
                rejected_by_effect += 1
            
            # Track for quality-gate-only rejections (top candidates)
            if len(quality_gate_rejections) < 20:  # Keep more than top 5 for filtering
                quality_gate_rejections.append(RejectionInfo(
                    candidate=sp,
                    failed_gate=failed_gate
                ))
    
    if not eligible_patterns:
        # All rejected by quality gates
        top_5_quality_rejections = sorted(
            quality_gate_rejections,
            key=lambda x: x.candidate.composite_score,
            reverse=True
        )[:5]
        return SelectionResult(
            selected=[],
            total_considered=len(ranked_patterns),
            rejected_by_composite=rejected_by_composite,
            rejected_by_support=rejected_by_support,
            rejected_by_effect=rejected_by_effect,
            rejected_by_segment_dup=0,
            rejected_by_diversity_conflict=0,
            quality_gate_only_rejections=top_5_quality_rejections,
            selected_per_stage={}
        )
    
    # Step 2: Apply staged diversity selection with segment deduplication
    # This will try to fill up to target_n by progressing through stages
    selected, selected_per_stage, rejected_by_diversity_conflict, rejected_by_segment_dup = _staged_diversity_selection(
        eligible_patterns,
        target_n=target_n
    )
    
    # Get top 5 quality-gate-only rejections (sorted by composite_score)
    top_5_quality_rejections = sorted(
        quality_gate_rejections,
        key=lambda x: x.candidate.composite_score,
        reverse=True
    )[:5]
    
    return SelectionResult(
        selected=selected,
        total_considered=len(ranked_patterns),
        rejected_by_composite=rejected_by_composite,
        rejected_by_support=rejected_by_support,
        rejected_by_effect=rejected_by_effect,
        rejected_by_segment_dup=rejected_by_segment_dup,
        rejected_by_diversity_conflict=rejected_by_diversity_conflict,
        quality_gate_only_rejections=top_5_quality_rejections,
        selected_per_stage=selected_per_stage
    )


def _passes_quality_gates(scored_pattern: ScoredPatternCandidate) -> bool:
    """
    Check if a scored pattern passes all hard quality gates.
    
    Args:
        scored_pattern: Scored pattern candidate to check
        
    Returns:
        True if passes all gates, False otherwise
    """
    return _check_quality_gates(scored_pattern) is None


def _check_quality_gates(scored_pattern: ScoredPatternCandidate) -> Optional[str]:
    """
    Check which quality gate a pattern fails, if any.
    
    Args:
        scored_pattern: Scored pattern candidate to check
        
    Returns:
        None if passes all gates, otherwise the name of the failed gate:
        'composite', 'support', or 'effect'
    """
    if scored_pattern.composite_score < MIN_COMPOSITE_SCORE:
        return 'composite'
    if scored_pattern.statistical_support < MIN_SUPPORT:
        return 'support'
    if scored_pattern.effect_size < MIN_EFFECT_SIZE:
        return 'effect'
    return None


def _staged_diversity_selection(
    eligible_patterns: List[ScoredPatternCandidate],
    target_n: int
) -> Tuple[List[ScoredPatternCandidate], Dict[int, int], int, int]:
    """
    Apply staged diversity selection with segment deduplication.
    
    Stages:
    - Stage 0 (strict): max 1 per metric, max 1 per dimension, max 2 per pattern_type
    - Stage 1 (relax metric): allow 2 per metric
    - Stage 2 (relax dimension): allow 2 per dimension
    - Stage 3 (final): disable metric+dimension caps (keep pattern_type + segment unique)
    
    Segment uniqueness (max 1 per segment_id) is ALWAYS enforced.
    
    Args:
        eligible_patterns: Patterns that passed quality gates
        target_n: Target number of insights
        
    Returns:
        Tuple of (selected_patterns, selected_per_stage, rejected_by_diversity, rejected_by_segment_dup)
    """
    if not eligible_patterns:
        return [], {}, 0, 0
    
    selected = []
    selected_per_stage = {0: 0, 1: 0, 2: 0, 3: 0}
    remaining_patterns = eligible_patterns.copy()
    used_segment_ids = set()
    
    # Stage 0: Strict constraints (max 1 per metric, max 1 per dimension, max 2 per pattern_type)
    stage0_selected, remaining_patterns = _select_stage(
        remaining_patterns, target_n, used_segment_ids,
        max_per_metric=1, max_per_dimension=1, max_per_pattern_type=2
    )
    selected.extend(stage0_selected)
    selected_per_stage[0] = len(stage0_selected)
    
    # Only proceed to next stages if we have at least 2 insights and need more
    if len(selected) >= 2 and len(selected) < target_n:
        # Stage 1: Relax metric constraint (allow 2 per metric)
        stage1_selected, remaining_patterns = _select_stage(
            remaining_patterns, target_n - len(selected), used_segment_ids,
            max_per_metric=2, max_per_dimension=1, max_per_pattern_type=2
        )
        selected.extend(stage1_selected)
        selected_per_stage[1] = len(stage1_selected)
    
    if len(selected) >= 2 and len(selected) < target_n:
        # Stage 2: Relax dimension constraint (allow 2 per dimension)
        stage2_selected, remaining_patterns = _select_stage(
            remaining_patterns, target_n - len(selected), used_segment_ids,
            max_per_metric=2, max_per_dimension=2, max_per_pattern_type=2
        )
        selected.extend(stage2_selected)
        selected_per_stage[2] = len(stage2_selected)
    
    if len(selected) >= 2 and len(selected) < target_n:
        # Stage 3: Final - disable metric+dimension caps (keep pattern_type + segment unique)
        stage3_selected, remaining_patterns = _select_stage(
            remaining_patterns, target_n - len(selected), used_segment_ids,
            max_per_metric=None, max_per_dimension=None, max_per_pattern_type=2
        )
        selected.extend(stage3_selected)
        selected_per_stage[3] = len(stage3_selected)
    
    # Count rejections
    total_eligible = len(eligible_patterns)
    selected_count = len(selected)
    
    # Rejected by diversity = patterns that passed quality gates but didn't get selected
    # (excluding those rejected by segment dup, which we track separately)
    rejected_by_diversity_conflict = total_eligible - selected_count
    
    # Segment dup rejections are handled within _select_stage, so we estimate:
    # If we selected fewer than eligible, some may have been segment dup
    # But we can't easily separate diversity vs segment dup without more tracking
    # For now, we'll count segment dup as patterns that would have been selected
    # but were filtered by segment uniqueness
    rejected_by_segment_dup = 0  # This is approximate - segment dup happens within stages
    
    return selected, selected_per_stage, rejected_by_diversity_conflict, rejected_by_segment_dup


def _select_stage(
    remaining_patterns: List[ScoredPatternCandidate],
    target_count: int,
    used_segment_ids: set,
    max_per_metric: Optional[int],
    max_per_dimension: Optional[int],
    max_per_pattern_type: Optional[int]
) -> Tuple[List[ScoredPatternCandidate], List[ScoredPatternCandidate]]:
    """
    Select patterns for a stage with given constraints, enforcing segment uniqueness.
    
    Args:
        remaining_patterns: Patterns to select from
        target_count: How many to select
        used_segment_ids: Set of segment_ids already used (updated in place)
        max_per_metric: Max per metric (None = unlimited)
        max_per_dimension: Max per dimension (None = unlimited)
        max_per_pattern_type: Max per pattern_type (None = unlimited)
        
    Returns:
        Tuple of (selected_patterns, remaining_patterns)
    """
    if not remaining_patterns or target_count <= 0:
        return [], remaining_patterns
    
    selected = []
    metric_counts = {}
    dimension_counts = {}
    pattern_type_counts = {}
    remaining = []
    
    for sp in remaining_patterns:
        if len(selected) >= target_count:
            remaining.append(sp)
            continue
        
        candidate = sp.candidate
        metric = candidate.metric_name
        dimension = list(candidate.dimensions.keys())[0] if candidate.dimensions else "unknown"
        segment_id = extract_segment_id(candidate)
        pattern_type = candidate.pattern_type
        
        # Always enforce segment uniqueness
        if segment_id in used_segment_ids:
            remaining.append(sp)
            continue
        
        # Check metric constraint
        metric_ok = True
        if max_per_metric is not None:
            metric_count = metric_counts.get(metric, 0)
            metric_ok = metric_count < max_per_metric
        
        # Check dimension constraint
        dimension_ok = True
        if max_per_dimension is not None:
            dimension_count = dimension_counts.get(dimension, 0)
            dimension_ok = dimension_count < max_per_dimension
        
        # Check pattern_type constraint
        pattern_type_ok = True
        if max_per_pattern_type is not None:
            pattern_type_count = pattern_type_counts.get(pattern_type, 0)
            pattern_type_ok = pattern_type_count < max_per_pattern_type
        
        # Check if we can add this pattern
        if metric_ok and dimension_ok and pattern_type_ok:
            selected.append(sp)
            used_segment_ids.add(segment_id)
            metric_counts[metric] = metric_counts.get(metric, 0) + 1
            dimension_counts[dimension] = dimension_counts.get(dimension, 0) + 1
            pattern_type_counts[pattern_type] = pattern_type_counts.get(pattern_type, 0) + 1
        else:
            remaining.append(sp)
    
    return selected, remaining
