"""Two-stage ranking to prevent pattern type dominance."""

from typing import List, Dict
from ..models.insight import ScoredPatternCandidate
from ..candidate_generation.pattern_types import PatternType


def apply_two_stage_ranking(scored_patterns: List[ScoredPatternCandidate]) -> List[ScoredPatternCandidate]:
    """
    Apply two-stage ranking to prevent one pattern type from dominating.
    
    Stage 1 - Within-type ranking:
    1. Group candidates by pattern_type
    2. Sort each group by composite_score (descending)
    3. Keep only top 3 candidates per pattern_type
    
    Stage 2 - Cross-type ranking:
    4. Combine all retained candidates
    5. Sort them by composite_score (descending)
    6. Return ranked list (diversity selection happens later)
    
    Args:
        scored_patterns: List of scored patterns with composite_score
        
    Returns:
        List of scored patterns after two-stage ranking, sorted by composite_score
    """
    if not scored_patterns:
        return scored_patterns
    
    # Stage 1: Within-type ranking - keep top 3 per pattern_type
    patterns_by_type: Dict[PatternType, List[ScoredPatternCandidate]] = {}
    for sp in scored_patterns:
        pattern_type = sp.candidate.pattern_type
        if pattern_type not in patterns_by_type:
            patterns_by_type[pattern_type] = []
        patterns_by_type[pattern_type].append(sp)
    
    # Sort each group by composite_score and keep top 3
    retained_patterns = []
    for pattern_type, patterns in patterns_by_type.items():
        # Sort by composite_score (descending)
        sorted_patterns = sorted(patterns, key=lambda x: x.composite_score, reverse=True)
        # Keep top 3
        top_3 = sorted_patterns[:3]
        retained_patterns.extend(top_3)
    
    # Stage 2: Cross-type ranking - sort all retained by composite_score
    final_ranked = sorted(
        retained_patterns,
        key=lambda x: x.composite_score,
        reverse=True
    )
    
    return final_ranked
