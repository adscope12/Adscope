"""Marketing Insight Engine - Phase 1: Pattern Scoring Only.

Stateless engine that processes campaign CSV data, generates patterns,
and scores them. No insights layer, no top-N selection yet.

Architecture Flow:
1. File Ingestion Layer: Receive uploaded file
2. LLM-Assisted Reading Layer (runs before this engine):
   - Interprets inconsistent column names
   - Interprets inconsistent platform/campaign/KPI naming
   - Handles Hebrew/English/typos/mixed naming
   - Preserves potentially relevant extra fields
   - Outputs canonical mappings for downstream processing
   - CRITICAL: Does NOT modify raw customer data values (data immutability rule)
3. Canonicalized Internal Structure: Apply mappings, preserve original data
4. Feature Extraction: Parse canonicalized structure (using mappings), compute KPIs
5. Normalization: Standardize metrics for pattern detection
6. Candidate Generation: Generate structural pattern candidates
7. Scoring: Score patterns (effect_size, business_impact, statistical_support, composite_score)
8. Selection: Apply two-stage ranking
9. Strategic LLM Layer (runs after this engine): Interprets scored patterns into strategic insights
10. User-Facing Output Layer: Format and deliver insights
"""

from typing import List, Tuple, Optional, Dict, Any
import pandas as pd
from .feature_extraction.parser import parse_csv, parse_dataframe
from .feature_extraction.feature_set import process_feature_set
from .normalization.normalized_set import NormalizedSet
from .candidate_generation.pattern_detector import generate_candidates
from .scoring.composite_scorer import score_candidate
from .selection.two_stage_ranker import apply_two_stage_ranking
from .selection.diversity_selector import select_diverse_patterns
from .models.insight import ScoredPatternCandidate


class InsightEngine:
    """Marketing Insight Engine - Phase 1: Pattern Scoring Only."""
    
    def __init__(self):
        """Initialize stateless engine."""
        pass
    
    def process(
        self,
        csv_path: Optional[str] = None,
        canonical_structure: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[ScoredPatternCandidate], pd.DataFrame]:
        """
        Process campaign data and return scored pattern candidates.
        
        This engine is called AFTER the LLM-Assisted Reading Layer has
        interpreted the schema. The reading layer runs in the CLI before this engine.
        
        The engine can accept either:
        - A file path (legacy mode, for backward compatibility)
        - A canonical structure (new mode, with applied mappings)
        
        The reading layer (which runs before this):
        - Interprets inconsistent column names (e.g., "עלות" → "spend")
        - Interprets inconsistent platform/campaign/KPI naming
        - Handles multilingual naming (Hebrew/English) and typos
        - Preserves relevant extra fields
        - Creates canonical bridge with renamed columns and mapped values
        
        CRITICAL: The reading layer follows the data immutability rule - it does NOT
        modify raw customer data values. Only schema-level mappings are created.
        The canonical bridge is a copy with renamed columns - original data unchanged.
        
        Pipeline (deterministic engine):
        1. Parse canonicalized DataFrame and compute KPIs (ROAS, CPA, Revenue, Spend, CTR, CVR)
           - Uses canonical_df from canonical_structure (with applied mappings)
           - Original DataFrame remains untouched
        2. Normalize metrics for pattern detection
        3. Generate structural pattern candidates
        4. Score patterns: effect_size, business_impact, statistical_support, composite_score
        5. Apply two-stage ranking (within-type top 3, then cross-type by composite_score)
        6. Diversity selection happens in formatter
        
        Args:
            csv_path: Optional path to CSV or XLSX file (legacy mode)
            canonical_structure: Optional canonical structure dict with:
                - canonical_df: Canonicalized DataFrame with renamed columns
                - original_df: Original DataFrame (unchanged)
                - schema_mapping: SchemaMapping object
                - column_mapping_dict: Column name mappings
                - value_mapping_dicts: Value mappings
        
        Returns:
            Tuple of (scored pattern candidates, normalized dataframe)
        """
        # Determine input source and analysis mode
        analysis_mode = "full"  # Default to full mode for legacy file path mode
        if canonical_structure is not None:
            # Use canonical structure (new mode)
            canonical_df = canonical_structure["canonical_df"]
            if canonical_df is None:
                raise ValueError("canonical_structure must contain 'canonical_df'")
            
            # Extract analysis_mode from canonical structure
            analysis_mode = canonical_structure.get("analysis_mode", "full")
            
            # Parse canonicalized DataFrame
            feature_set = parse_dataframe(canonical_df)
        elif csv_path is not None:
            # Use file path (legacy mode)
            feature_set = parse_csv(csv_path)
        else:
            raise ValueError("Either csv_path or canonical_structure must be provided")
        
        # 1. Feature Extraction: Compute KPIs
        feature_set = process_feature_set(feature_set)
        
        # 2. Normalization: Standardize metrics for comparison
        normalized_set = NormalizedSet.from_feature_set(feature_set)
        
        # 3. Candidate Generation: Structural pattern candidates
        # Pass analysis_mode to filter revenue/ROAS metrics in PERFORMANCE mode
        candidates = generate_candidates(normalized_set, analysis_mode=analysis_mode)
        
        # 4. Scoring: Effect size + business impact + statistical support
        # Pre-ranking filters applied inside score_candidate()
        scored_patterns = [score_candidate(candidate) for candidate in candidates]
        
        # Filter out None results (candidates that failed pre-ranking filters)
        filtered_patterns = [sp for sp in scored_patterns if sp is not None]
        
        # 5. Apply two-stage ranking:
        #    Stage 1: Within-type ranking - keep top 3 per pattern_type
        #    Stage 2: Cross-type ranking - sort all retained by composite_score
        ranked_patterns = apply_two_stage_ranking(filtered_patterns)
        
        # 6. Return ranked patterns and dataframe for Tier 2 insights
        return ranked_patterns, normalized_set.data
