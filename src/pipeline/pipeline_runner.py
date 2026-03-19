"""
Reusable pipeline execution logic extracted from CLI.

This module contains the core pipeline logic that can be used by both
CLI and API interfaces.
"""

import sys
import logging
from typing import Dict, Any, Optional, Tuple, List
import pandas as pd
from io import BytesIO
from datetime import datetime, date

from src.reading import read_file, ReadingAssistant
from src.normalization.canonicalizer import prepare_canonical_structure
from src.engine import InsightEngine
from src.llm import StrategicLLMLayer
from src.llm.reranker import BusinessReranker
from src.output.strategic_formatter import (
    format_strategic_output_json,
    convert_scored_patterns_to_dict,
)
from src.selection.insight_validation import validate_and_filter_insights
from src.selection.insight_postprocessor import (
    validate_dataset_size,
    deduplicate_insights_by_theme,
)
from src.selection.insight_deduplication import deduplicate_insights
from src.selection.story_deduplication import deduplicate_insights as deduplicate_story_insights
from src.narrative import GroundedNarrativeLayer


logger = logging.getLogger(__name__)


def _enforce_final_top3_constraints(candidates: List[Any]) -> List[Any]:
    """
    Final-stage selection constraints for grounded outputs:
    1) If a strong entity insight exists (campaign/platform/device), ensure >=1 appears in top 3.
    2) If stronger business metrics exist (CPA/CVR/ROAS/revenue/conversions), block spend-only insights
       from top 3 unless pattern_type is METRIC_IMBALANCE.

    This function only reorders the final candidate list; it does not change scoring.
    """
    if not candidates:
        return candidates

    # Helper predicates
    def _dimension(sp: Any) -> str:
        dims = getattr(sp.candidate, "dimensions", {}) or {}
        if dims:
            return str(list(dims.keys())[0]).lower()
        return "unknown"

    def _is_entity(sp: Any) -> bool:
        return _dimension(sp) in {"campaign", "platform", "device"}

    def _metric(sp: Any) -> str:
        return str(getattr(sp.candidate, "metric_name", "") or "").lower()

    def _is_spend_only(sp: Any) -> bool:
        if _metric(sp) != "spend":
            return False
        # Allow spend if it's explicitly a budget imbalance pattern
        try:
            from src.candidate_generation.pattern_types import PatternType
            return sp.candidate.pattern_type != PatternType.METRIC_IMBALANCE
        except Exception:
            return True

    stronger_metrics = {"cpa", "cvr", "roas", "revenue", "conversions"}
    has_stronger_metric = any(_metric(sp) in stronger_metrics for sp in candidates)

    # Hard rule 2 (global): if stronger business metrics exist, disqualify spend-only insights
    # entirely (unless pattern_type is METRIC_IMBALANCE).
    if has_stronger_metric:
        candidates = [sp for sp in candidates if not _is_spend_only(sp)]
        if not candidates:
            return candidates

    top3 = candidates[:3]
    rest = candidates[3:]

    # Hard rule 1: ensure at least one entity insight in top3 if any exists anywhere
    any_entity_exists = any(_is_entity(sp) for sp in candidates)
    if any_entity_exists and not any(_is_entity(sp) for sp in top3):
        # Promote the best available entity insight (first encountered in rank order)
        promoted = None
        new_rest = []
        for sp in rest:
            if promoted is None and _is_entity(sp):
                promoted = sp
            else:
                new_rest.append(sp)

        if promoted is not None:
            # Replace the 3rd slot (least important of top3) with the entity insight.
            # Prefer to demote a temporal insight if present.
            def _is_temporal(sp: Any) -> bool:
                if getattr(sp.candidate, "time_period", None) is not None:
                    return True
                pid = str(getattr(sp.candidate, "pattern_id", "") or "")
                return pid.startswith(("GRADUAL_DECLINE", "RECOVERY", "SPIKE_DROP", "WEEKEND_WEEKDAY"))

            demote_idx = 2
            for i in range(min(3, len(top3)) - 1, -1, -1):
                if _is_temporal(top3[i]):
                    demote_idx = i
                    break

            demoted_item = top3[demote_idx]
            top3 = top3[:demote_idx] + [promoted] + top3[demote_idx + 1 :]
            rest = [demoted_item] + new_rest

    return top3 + rest


def _metric_family_key(metric_name: str) -> str:
    """
    Metric-family key used for diversity filtering.
    """
    m = (metric_name or "").strip().lower()
    if m in {"cvr", "roas"}:
        return "efficiency"
    if m in {"revenue", "conversions"}:
        return "volume"
    if m in {"cpa", "cpc"}:
        return "cost"
    if m in {"ctr", "clicks", "impressions"}:
        return "engagement"
    # fallback: metric name
    return m or "unknown"


def _apply_metric_family_diversity(
    candidates: List[Any],
    desired_count: int,
) -> List[Any]:
    """
    Soft diversity filter:
    - First pass: keep at most 1 insight per metric family.
    - Second pass: if we still need more insights, fill remaining slots normally.

    This reorders and truncates only; it does not change any scoring.
    """
    if desired_count <= 0 or not candidates:
        return candidates

    desired_count = min(desired_count, len(candidates))
    if desired_count <= 1:
        return candidates[:desired_count]

    selected: List[Any] = []
    seen_families: set[str] = set()
    used_ids: set[str] = set()

    def _pid(sp: Any) -> str:
        return str(getattr(getattr(sp, "candidate", None), "pattern_id", "") or "")

    # Pass 1: first occurrence per family
    for sp in candidates:
        if len(selected) >= desired_count:
            break
        pid = _pid(sp)
        if pid and pid in used_ids:
            continue
        metric = getattr(getattr(sp, "candidate", None), "metric_name", "") or ""
        fam = _metric_family_key(metric)
        if fam in seen_families:
            continue
        seen_families.add(fam)
        selected.append(sp)
        if pid:
            used_ids.add(pid)

    # Pass 2: fill remaining slots normally
    if len(selected) < desired_count:
        selected_ids = set(used_ids)
        for sp in candidates:
            if len(selected) >= desired_count:
                break
            pid = _pid(sp)
            if pid and pid in selected_ids:
                continue
            selected.append(sp)
            if pid:
                selected_ids.add(pid)

    return selected


def _make_json_serializable(obj: Any) -> Any:
    """
    Recursively convert non-JSON-serializable objects to JSON-friendly types.
    
    Handles:
    - pandas Timestamp -> ISO format string
    - datetime/date -> ISO format string
    - numpy bool_ -> Python bool
    - numpy integer -> Python int
    - numpy floating -> Python float
    - numpy arrays -> Python list
    - nested dicts/lists recursively
    
    Args:
        obj: Object to convert
        
    Returns:
        JSON-serializable version of the object
    """
    import numpy as np
    
    # Handle pandas Timestamp
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    
    # Handle datetime objects
    if isinstance(obj, datetime):
        return obj.isoformat()
    
    # Handle date objects
    if isinstance(obj, date):
        return obj.isoformat()
    
    # Handle numpy boolean types explicitly (must come before generic numpy check)
    if isinstance(obj, np.bool_):
        return bool(obj)
    
    # Handle numpy integer types
    if isinstance(obj, np.integer):
        return int(obj)
    
    # Handle numpy floating types
    if isinstance(obj, np.floating):
        return float(obj)
    
    # Handle numpy arrays
    if isinstance(obj, np.ndarray):
        return [_make_json_serializable(item) for item in obj.tolist()]
    
    # Handle other numpy scalar types (via .item() method)
    if hasattr(obj, 'item') and hasattr(obj, 'dtype'):
        try:
            return _make_json_serializable(obj.item())
        except (ValueError, AttributeError):
            pass
    
    # Handle dictionaries - recurse
    if isinstance(obj, dict):
        return {key: _make_json_serializable(value) for key, value in obj.items()}
    
    # Handle lists/tuples - recurse
    if isinstance(obj, (list, tuple)):
        return [_make_json_serializable(item) for item in obj]
    
    # Return as-is if already serializable
    return obj


def _build_strategic_result_from_grounded(
    grounded_insights: List[Dict[str, Any]],
    scored_candidates: List[Any]
) -> Dict[str, Any]:
    """
    Convert grounded phrased insights to strategic result format.
    
    Args:
        grounded_insights: List of grounded insights with headline, what_is_happening, etc.
        scored_candidates: Original scored candidates for context
        
    Returns:
        Strategic result dict compatible with existing format
    """
    # Convert grounded insights to prioritized_insights format
    def _compose_summary(what: str, why: str) -> str:
        what = (what or "").strip()
        why = (why or "").strip()
        if not what:
            return why
        if not why:
            return what
        # Avoid repeated sentences when what/why are near-identical after cleanup.
        if why.lower() in what.lower():
            return what
        if what.lower() in why.lower():
            return why
        return f"{what} {why}".strip()

    prioritized_insights = []
    for i, grounded in enumerate(grounded_insights):
        prioritized_insights.append({
            "title": grounded.get("headline", ""),
            "summary": _compose_summary(
                grounded.get("what_is_happening", ""),
                grounded.get("why_it_matters", ""),
            ),
            "recommended_actions": [grounded.get("next_check", "")] if grounded.get("next_check") else [],
            "confidence": 0.8  # Default confidence for grounded insights
        })
    
    # Convert to top_priorities format (top 3)
    top_priorities = []
    for i, grounded in enumerate(grounded_insights[:3]):
        top_priorities.append({
            "issue_opportunity": grounded.get("headline", ""),
            "why_it_matters": grounded.get("why_it_matters", ""),
            "expected_impact": grounded.get("what_is_happening", "")
        })
    
    # Build executive summary deterministically from complete, validated headlines only.
    # Requirements:
    # - 1 short sentence
    # - no fragments / broken endings
    # - no invented facts (only reusing existing headlines)
    def _clean_headline(h: str) -> str:
        h = (h or "").strip()
        # Remove trailing punctuation so we can compose a single sentence safely
        while h.endswith((".", "!", "?", ";", ":")):
            h = h[:-1].rstrip()
        return h

    raw_headlines = [g.get("headline", "") for g in grounded_insights if g.get("headline")]
    headlines = [_clean_headline(h) for h in raw_headlines]
    headlines = [h for h in headlines if h]
    headlines = headlines[:3]

    if not headlines:
        executive_summary = "No strong insights detected."
    elif len(headlines) == 1:
        executive_summary = f"Top insight: {headlines[0]}."
    else:
        executive_summary = "Top insights: " + "; ".join(headlines) + "."
    
    # Extract recommended checks (dedupe near-identical checks)
    def _normalize_check(s: str) -> str:
        s = (s or "").strip().lower()
        if not s:
            return ""
        # collapse whitespace and remove trailing punctuation
        s = " ".join(s.split())
        while s.endswith((".", "!", "?", ";", ":")):
            s = s[:-1].rstrip()
        return s

    recommended_checks = []
    seen = set()
    for grounded in grounded_insights:
        check = grounded.get("next_check", "") or ""
        norm = _normalize_check(check)
        if not norm:
            continue
        if norm in seen:
            continue
        seen.add(norm)
        recommended_checks.append(check.strip())
        if len(recommended_checks) >= 5:
            break
    
    return {
        "executive_summary": executive_summary or "Analysis completed with grounded insights.",
        "top_priorities": top_priorities,
        "prioritized_insights": prioritized_insights,
        "recommended_checks": recommended_checks,
        "risks_warnings": [],
        "notes": "Insights generated using grounded narrative layer."
    }


def run_full_pipeline(
    file_path: Optional[str] = None,
    file_content: Optional[bytes] = None,
    file_name: Optional[str] = None,
    skip_reading: bool = False,
    skip_strategic: bool = False,
) -> Dict[str, Any]:
    """
    Run the full insight generation pipeline.
    
    This function executes the complete pipeline:
    1. File Ingestion
    2. LLM-Assisted Reading Layer (if not skipped)
    3. Canonical Bridge (if reading layer not skipped)
    4. Deterministic Insight Engine
    5. Strategic LLM Layer (if not skipped)
    6. User-Facing Output
    
    Args:
        file_path: Path to file (if reading from disk)
        file_content: File content as bytes (if uploading)
        file_name: Name of file (required if file_content provided)
        skip_reading: Skip LLM-assisted reading layer
        skip_strategic: Skip Strategic LLM layer
        
    Returns:
        Dictionary with:
        - success: bool
        - result: Dict with strategic insights (if successful)
        - error: str (if failed)
        - no_insights: bool (if no patterns found)
        
    Raises:
        ValueError: For validation errors (empty file, missing columns, etc.)
        RuntimeError: For LLM-related errors
    """
    try:
        # ============================================================
        # STEP 1: File Ingestion
        # ============================================================
        if file_content is not None:
            # Handle in-memory file upload
            if not file_name:
                raise ValueError("file_name is required when providing file_content")
            
            # Determine file type from extension
            file_ext = file_name.lower().split('.')[-1]
            if file_ext not in ['csv', 'xlsx', 'xls']:
                raise ValueError(f"Unsupported file type: {file_ext}. Supported: csv, xlsx, xls")
            
            # Read from bytes
            import pandas as pd
            from src.reading.file_ingestion import FileType
            
            if file_ext == 'csv':
                df = pd.read_csv(BytesIO(file_content))
                file_type = FileType.CSV
            else:  # xlsx or xls
                df = pd.read_excel(BytesIO(file_content), engine='openpyxl')
                file_type = FileType.XLSX
        else:
            # Read from file path
            if not file_path:
                raise ValueError("Either file_path or file_content must be provided")
            df, file_type = read_file(file_path)
        
        # CRITICAL FIX #1: Empty DataFrame validation
        if df.empty:
            return {
                "success": False,
                "error": "File is empty or contains no data rows.",
                "no_insights": False,
            }
        
        if len(df.columns) == 0:
            return {
                "success": False,
                "error": "File contains no columns.",
                "no_insights": False,
            }
        
        # IMPROVEMENT #3: Small Dataset / Low Confidence Handling
        row_count = len(df)
        allow_insights, dataset_message, max_insights = validate_dataset_size(row_count)
        
        if not allow_insights:
            # Dataset too small (< 5 rows) - return no insights
            return {
                "success": True,
                "no_insights": True,
                "message": dataset_message or "No strong insights detected in this dataset.",
            }
        
        # ============================================================
        # STEP 2: LLM-Assisted Reading Layer
        # ============================================================
        schema_mapping = None
        canonical_structure = None
        
        if not skip_reading:
            # Initialize reading assistant
            reading_assistant = ReadingAssistant()
            
            # Interpret schema (returns mappings only, doesn't modify df)
            # For in-memory files, we need to pass the DataFrame directly
            if file_content is not None:
                schema_mapping = reading_assistant.interpret_schema(
                    file_name, original_df=df
                )
            else:
                schema_mapping = reading_assistant.interpret_schema(
                    file_path, original_df=df
                )
            
            # ============================================================
            # STEP 3: Canonical Structure Preparation (Bridge)
            # ============================================================
            # Create canonical bridge with applied mappings
            # Original DataFrame remains unchanged
            canonical_structure = prepare_canonical_structure(
                df=df,
                schema_mapping=schema_mapping,
                apply_mappings=True,  # Create canonical bridge
            )
        else:
            canonical_structure = None
        
        # ============================================================
        # STEP 4: Deterministic Insight Engine
        # ============================================================
        engine = InsightEngine()
        
        # Extract analysis_mode from canonical structure if available
        analysis_mode = "full"  # Default to full mode
        if canonical_structure is not None:
            analysis_mode = canonical_structure.get("analysis_mode", "full")
        
        # Process using canonical structure if available, otherwise use file path
        if canonical_structure is not None:
            # Use canonical bridge (new mode)
            scored_patterns, dataframe = engine.process(canonical_structure=canonical_structure)
        else:
            # For in-memory files, we need to save temporarily or use DataFrame directly
            # For now, we'll require file_path if skip_reading is True
            if file_content is not None:
                raise ValueError(
                    "Cannot use in-memory file with skip_reading=True. "
                    "Please provide file_path or set skip_reading=False."
                )
            # Fallback to file path (legacy mode)
            scored_patterns, dataframe = engine.process(csv_path=file_path)
        
        # CRITICAL FIX #2: Empty patterns handling
        if not scored_patterns:
            return {
                "success": True,
                "no_insights": True,
                "message": (
                    "The deterministic engine did not find any statistically significant patterns. "
                    "This may occur if the dataset is too small, has insufficient variation, "
                    "all segments perform similarly, or required metrics (spend, revenue) are missing."
                ),
            }
        
        # ============================================================
        # STEP 4.5: Insight Validation Layer
        # ============================================================
        # Validate and filter insights to keep only the strongest 3-4
        # IMPROVEMENT #3: Apply dataset size limit to validation
        validated_patterns, validation_metadata = validate_and_filter_insights(
            scored_patterns,
            top_n=max_insights  # Use dataset-size-aware limit
        )

        # Story-level deduplication (metric-family business stories)
        validated_patterns = deduplicate_story_insights(validated_patterns)
        
        # If validation filtered out all insights, return no insights
        if not validated_patterns:
            return {
                "success": True,
                "no_insights": True,
                "message": (
                    "The system detected patterns, but none met the validation criteria for "
                    "business impact, statistical significance, and actionability. "
                    "This may indicate the dataset needs more variation or stronger signals."
                ),
            }
        
        # ============================================================
        # STEP 4.6: Insight Deduplication Layer
        # ============================================================
        # Remove duplicate insights that describe the same pattern
        # Keep only the strongest candidate (highest composite_score) per pattern signature
        deduplicated_patterns = deduplicate_insights(validated_patterns)

        # Final-stage hard constraints for grounded top priorities:
        # - Ensure at least one campaign/platform/device insight in top 3 if any exist
        # - Block spend-only insights from top 3 when stronger metrics exist (unless METRIC_IMBALANCE)
        deduplicated_patterns = _enforce_final_top3_constraints(deduplicated_patterns)
        
        # If deduplication removed all insights (shouldn't happen, but safety check)
        if not deduplicated_patterns:
            return {
                "success": True,
                "no_insights": True,
                "message": (
                    "The system detected patterns, but deduplication removed all candidates. "
                    "This may indicate duplicate patterns were detected."
                ),
            }

        # ============================================================
        # STEP 4.7: LLM Business-Aware Reranking (shortlist only)
        # ============================================================
        # This step ONLY reorders an already-selected shortlist and optionally removes
        # LLM-marked near-duplicates. It never introduces new insights.
        try:
            reranker = BusinessReranker()
            deduplicated_patterns = reranker.rerank(
                deduplicated_patterns,
                shortlist_size=min(8, max_insights * 2),
            )
        except Exception as e:
            logger.warning("BusinessReranker failed, keeping deterministic order: %s", e)

        # Re-apply deterministic hard constraints in case reranking disturbed them
        deduplicated_patterns = _enforce_final_top3_constraints(deduplicated_patterns)

        # Metric-family diversity filter for final selection (reorders and truncates only)
        deduplicated_patterns = _apply_metric_family_diversity(deduplicated_patterns, desired_count=max_insights)
        
        # ============================================================
        # STEP 5: Grounded Narrative Layer
        # ============================================================
        # Phrase insights using grounded narrative (constrained to detected facts)
        grounded_phrased_insights = []
        if not skip_strategic:
            try:
                logger.info("GroundedNarrativeLayer started")
                grounded_layer = GroundedNarrativeLayer()
                grounded_phrased_insights = grounded_layer.phrase_insights(
                    scored_candidates=deduplicated_patterns,
                    top_n=max_insights
                )
                logger.info(
                    "GroundedNarrativeLayer returned %d insights",
                    len(grounded_phrased_insights),
                )
            except Exception as e:
                # Make grounded narrative failure explicit and DO NOT silently fall back
                logger.error("GroundedNarrativeLayer failed: %s", e, exc_info=True)
                return {
                    "success": False,
                    "error": f"GroundedNarrativeLayer failed: {e}",
                    "no_insights": False,
                }
        
        # ============================================================
        # STEP 6: Strategic LLM Layer (Fallback/Executive Summary)
        # ============================================================
        if not skip_strategic:
            if grounded_phrased_insights:
                # Grounded narrative succeeded - build response from grounded insights
                strategic_result = _build_strategic_result_from_grounded(
                    grounded_phrased_insights,
                    deduplicated_patterns
                )
            else:
                # Grounded narrative produced no insights - log and fall back
                logger.warning(
                    "GroundedNarrativeLayer returned 0 insights; StrategicLLMLayer fallback triggered"
                )
                # Fallback to original Strategic LLM
                patterns_dict = convert_scored_patterns_to_dict(deduplicated_patterns)
                
                if not patterns_dict:
                    return {
                        "success": False,
                        "error": "Failed to convert patterns for analysis.",
                        "no_insights": False,
                    }
                
                strategic_layer = StrategicLLMLayer()
                context_dict = {
                    "total_patterns": len(scored_patterns),
                    "validated_patterns": len(validated_patterns),
                    "data_rows": len(dataframe),
                    "validation_metadata": _make_json_serializable(validation_metadata),
                }
                
                strategic_result = strategic_layer.analyze(
                    scored_patterns=patterns_dict,
                    top_n=max_insights,
                    context=context_dict
                )
                
                # IMPROVEMENT #1: Unified Insight Theme Deduplication (only for Strategic LLM fallback)
                # Combine all insights (top_priorities + prioritized_insights) for unified deduplication
                # This ensures no thematic duplication across different output formats
                
                all_insights = []
                
                # Convert top_priorities to insight format for unified processing
                top_priorities = strategic_result.get("top_priorities", [])
                for priority in top_priorities:
                    # Convert priority format to insight format
                    insight = {
                        "title": priority.get("issue_opportunity", ""),
                        "summary": f"{priority.get('why_it_matters', '')} {priority.get('expected_impact', '')}".strip(),
                        "issue_opportunity": priority.get("issue_opportunity", ""),
                        "why_it_matters": priority.get("why_it_matters", ""),
                        "expected_impact": priority.get("expected_impact", ""),
                        "_source": "top_priorities",
                        "_original": priority,
                    }
                    # Score based on explanation completeness and detail
                    why_length = len(priority.get("why_it_matters", ""))
                    impact_length = len(priority.get("expected_impact", ""))
                    insight["composite_score"] = why_length + impact_length
                    all_insights.append(insight)
                
                # Add prioritized_insights
                prioritized_insights = strategic_result.get("prioritized_insights", [])
                for insight in prioritized_insights:
                    enhanced_insight = insight.copy()
                    enhanced_insight["_source"] = "prioritized_insights"
                    # Prefer confidence score, fallback to summary length
                    confidence = insight.get("confidence")
                    if confidence is not None:
                        enhanced_insight["composite_score"] = float(confidence) * 100  # Scale to match length scores
                    else:
                        summary_length = len(insight.get("summary", ""))
                        enhanced_insight["composite_score"] = summary_length
                    all_insights.append(enhanced_insight)
                
                # Unified deduplication: group by theme, keep highest scoring per theme, limit to max_insights
                if all_insights:
                    deduplicated_all = deduplicate_insights_by_theme(
                        all_insights,
                        score_key="composite_score",
                        max_insights=max_insights  # Apply dataset-size-aware limit
                    )
                    
                    # Split back into top_priorities and prioritized_insights based on source
                    deduplicated_priorities = []
                    deduplicated_prioritized = []
                    
                    for insight in deduplicated_all:
                        source = insight.get("_source", "")
                        if source == "top_priorities":
                            # Restore original priority format
                            original = insight.get("_original", {})
                            deduplicated_priorities.append(original)
                        elif source == "prioritized_insights":
                            # Remove temporary fields
                            clean_insight = {k: v for k, v in insight.items() 
                                           if not k.startswith("_")}
                            deduplicated_prioritized.append(clean_insight)
                    
                    # Update strategic_result
                    strategic_result["top_priorities"] = deduplicated_priorities
                    strategic_result["prioritized_insights"] = deduplicated_prioritized
                else:
                    # No insights to deduplicate
                    strategic_result["top_priorities"] = []
                    strategic_result["prioritized_insights"] = []
            
            # ============================================================
            # STEP 6: User-Facing Output
            # ============================================================
            # CRITICAL FIX #8: Ensure internal IDs never leak - always hide by default
            output = format_strategic_output_json(strategic_result, hide_internal_ids=True)
            
            return {
                "success": True,
                "no_insights": False,
                "result": output,
            }
        else:
            # Skip Strategic LLM - return raw engine results (for debugging only)
            # Note: This should not be used in production API
            from src.selection.pattern_formatter import format_scored_patterns_json
            output = format_scored_patterns_json(scored_patterns, dataframe=dataframe, analysis_mode=analysis_mode)
            
            return {
                "success": True,
                "no_insights": False,
                "result": output,
                "warning": "Raw engine output (Strategic LLM skipped)",
            }
    
    except FileNotFoundError as e:
        return {
            "success": False,
            "error": f"File not found: {str(e)}",
            "no_insights": False,
        }
    except ValueError as e:
        # CRITICAL FIX #7: Sanitized user-facing errors
        error_msg = str(e)
        # Remove internal paths and technical details
        if "canonical_structure" in error_msg.lower():
            return {
                "success": False,
                "error": "Invalid data structure. Please check your file format.",
                "no_insights": False,
            }
        else:
            return {
                "success": False,
                "error": error_msg,
                "no_insights": False,
            }
    except RuntimeError as e:
        # CRITICAL FIX #7: Sanitized LLM errors (no raw output leakage)
        error_msg = str(e)
        # Check if this is an LLM-related error
        if "LLM" in error_msg or "JSON" in error_msg or "invalid" in error_msg.lower():
            # Don't expose raw LLM output or technical details
            if "Raw output" in error_msg:
                return {
                    "success": False,
                    "error": "Unable to process schema interpretation. Please try again or contact support.",
                    "no_insights": False,
                }
            else:
                # Generic error without technical details
                return {
                    "success": False,
                    "error": "Schema interpretation failed. Please check your file format and try again.",
                    "no_insights": False,
                }
        else:
            return {
                "success": False,
                "error": error_msg,
                "no_insights": False,
            }
    except Exception as e:
        # CRITICAL FIX #7: Sanitized errors - no tracebacks in user output
        error_msg = str(e)
        # Remove internal paths and technical stack traces
        if "Traceback" in error_msg or ("File" in error_msg and ".py" in error_msg):
            # This looks like a traceback - show generic error
            return {
                "success": False,
                "error": "An unexpected error occurred. Please check your file and try again.",
                "no_insights": False,
            }
        else:
            return {
                "success": False,
                "error": error_msg,
                "no_insights": False,
            }
