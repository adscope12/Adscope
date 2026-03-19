"""Build Insight objects from ScoredPatternCandidate objects."""

from dataclasses import dataclass
from typing import List
from ..models.insight import ScoredPatternCandidate
from ..candidate_generation.pattern_types import PatternType
from ..selection.selection_utils import extract_segment_id


@dataclass
class Insight:
    """Structured insight object for human-readable output."""
    
    title: str
    pattern_type: str
    dimension: str
    segment_id: str
    metric: str
    observed_value: float
    baseline_value: float
    absolute_delta: float
    relative_delta_pct: float
    importance_score: float
    confidence: float
    why_it_matters: str


def build_insight(scored_candidate: ScoredPatternCandidate) -> Insight:
    """
    Transform a ScoredPatternCandidate into an Insight object.
    
    Args:
        scored_candidate: Scored pattern candidate to transform
        
    Returns:
        Insight object with human-readable fields
    """
    candidate = scored_candidate.candidate
    
    # Extract basic fields
    pattern_type = candidate.pattern_type.value
    dimension = list(candidate.dimensions.keys())[0] if candidate.dimensions else "unknown"
    segment_id = extract_segment_id(candidate)
    metric = candidate.metric_name
    observed_value = candidate.observed_value
    baseline_value = candidate.baseline_value if candidate.baseline_value is not None else 0.0
    
    # Compute deltas
    absolute_delta = observed_value - baseline_value
    relative_delta_pct = (absolute_delta / (abs(baseline_value) + 1e-9)) * 100
    
    # Extract scores
    importance_score = scored_candidate.composite_score
    confidence = scored_candidate.statistical_support
    
    # Generate title based on pattern_type
    title = _generate_title(pattern_type, segment_id, metric)
    
    # Generate why_it_matters text
    why_it_matters = f"If sustained, this difference may impact overall {metric} efficiency and allocation dynamics."
    
    return Insight(
        title=title,
        pattern_type=pattern_type,
        dimension=dimension,
        segment_id=segment_id,
        metric=metric,
        observed_value=observed_value,
        baseline_value=baseline_value,
        absolute_delta=absolute_delta,
        relative_delta_pct=relative_delta_pct,
        importance_score=importance_score,
        confidence=confidence,
        why_it_matters=why_it_matters
    )


def _generate_title(pattern_type: str, segment_id: str, metric: str) -> str:
    """Generate title based on pattern type."""
    if pattern_type == PatternType.SEGMENT_GAP.value:
        return f"{segment_id} shows a significant gap in {metric}"
    elif pattern_type == PatternType.SEGMENT_ABOVE_BASELINE.value:
        return f"{segment_id} performs above baseline on {metric}"
    elif pattern_type == PatternType.SEGMENT_BELOW_BASELINE.value:
        return f"{segment_id} underperforms baseline on {metric}"
    elif pattern_type == PatternType.METRIC_IMBALANCE.value:
        return f"{segment_id} shows imbalance in {metric}"
    elif pattern_type == PatternType.TEMPORAL_CHANGE.value:
        return f"{segment_id} shows temporal shift in {metric}"
    else:
        return f"{segment_id} shows pattern in {metric}"


def build_insights(scored_candidates: List[ScoredPatternCandidate]) -> List[Insight]:
    """
    Transform a list of ScoredPatternCandidate objects into Insight objects.
    
    Args:
        scored_candidates: List of scored pattern candidates
        
    Returns:
        List of Insight objects
    """
    return [build_insight(sc) for sc in scored_candidates]
