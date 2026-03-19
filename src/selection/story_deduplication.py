"""
Story-level insight deduplication.

Removes semantically duplicate insights that tell the same business story,
keeping only the highest-scoring candidate per story group.
"""

from typing import List, Dict


def _story_family(metric_name: str) -> str:
    m = (metric_name or "").strip().lower()
    if m in {"cvr", "roas"}:
        return "efficiency"
    if m in {"revenue", "conversions"}:
        return "volume"
    if m in {"cpa", "cpc"}:
        return "cost"
    return m or "unknown"


def _perspective_key(sp: object) -> str:
    """
    Determine the "perspective" / dimension for grouping:
    - temporal if time_period is present or pattern_id indicates temporal family
    - otherwise the first dimension key (campaign/platform/device/etc.)
    """
    cand = getattr(sp, "candidate", None)
    if cand is None:
        return "unknown"

    if getattr(cand, "time_period", None) is not None:
        return "temporal"

    pid = str(getattr(cand, "pattern_id", "") or "")
    if pid.startswith(("GRADUAL_DECLINE", "RECOVERY", "SPIKE_DROP", "WEEKEND_WEEKDAY")):
        return "temporal"

    dims = getattr(cand, "dimensions", {}) or {}
    if dims:
        return str(list(dims.keys())[0]).lower()

    return "unknown"


def _dedup_key(sp: object) -> str:
    metric = getattr(getattr(sp, "candidate", None), "metric_name", "") or ""
    return f"{_perspective_key(sp)}_{_story_family(metric)}"


def deduplicate_insights(scored_patterns: List[object]) -> List[object]:
    """
    Remove semantically duplicate insights (same business story).
    Keep highest composite_score one per group.
    """
    if not scored_patterns:
        return []

    best_by_story: Dict[str, object] = {}

    for sp in scored_patterns:
        key = _dedup_key(sp)

        current_best = best_by_story.get(key)
        if current_best is None:
            best_by_story[key] = sp
            continue

        # Keep higher composite_score; if missing, treat as 0
        cur_score = float(getattr(sp, "composite_score", 0.0) or 0.0)
        best_score = float(getattr(current_best, "composite_score", 0.0) or 0.0)
        if cur_score > best_score:
            best_by_story[key] = sp

    deduped = list(best_by_story.values())
    deduped.sort(key=lambda x: float(getattr(x, "composite_score", 0.0) or 0.0), reverse=True)
    return deduped

