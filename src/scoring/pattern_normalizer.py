"""Pattern-type normalized scoring to prevent type dominance."""

from typing import List, Dict
from ..models.insight import ScoredPatternCandidate
from ..candidate_generation.pattern_types import PatternType


def apply_pattern_type_normalization(scored_patterns: List[ScoredPatternCandidate]) -> List[ScoredPatternCandidate]:
    """
    Apply pattern-type normalization to prevent one type from dominating ranking.
    
    Method:
    1. Group candidates by pattern_type
    2. For each group, compute max_score_in_type
    3. Compute normalized_score = composite_score / max_score_in_type
    4. final_score = 0.7 * composite_score + 0.3 * normalized_score
    
    Args:
        scored_patterns: List of scored patterns with composite_score
        
    Returns:
        List of scored patterns with final_score added
    """
    if not scored_patterns:
        return scored_patterns
    
    # Group by pattern_type
    patterns_by_type: Dict[PatternType, List[ScoredPatternCandidate]] = {}
    for sp in scored_patterns:
        pattern_type = sp.candidate.pattern_type
        if pattern_type not in patterns_by_type:
            patterns_by_type[pattern_type] = []
        patterns_by_type[pattern_type].append(sp)
    
    # Compute max_score_in_type for each pattern type
    max_scores_by_type: Dict[PatternType, float] = {}
    for pattern_type, patterns in patterns_by_type.items():
        max_score = max((sp.composite_score for sp in patterns), default=0.0)
        max_scores_by_type[pattern_type] = max_score if max_score > 0 else 1.0  # Avoid division by zero
    
    # Compute final_score for each pattern
    result = []
    for sp in scored_patterns:
        pattern_type = sp.candidate.pattern_type
        max_score_in_type = max_scores_by_type[pattern_type]
        
        # Compute normalized_score
        normalized_score = sp.composite_score / max_score_in_type if max_score_in_type > 0 else 0.0
        
        # Compute final_score: 0.7 * composite_score + 0.3 * normalized_score
        final_score = (0.7 * sp.composite_score) + (0.3 * normalized_score)
        
        # Create new ScoredPatternCandidate with final_score
        result.append(ScoredPatternCandidate(
            candidate=sp.candidate,
            effect_size=sp.effect_size,
            business_impact=sp.business_impact,
            statistical_support=sp.statistical_support,
            composite_score=sp.composite_score,
            final_score=final_score
        ))
    
    return result
