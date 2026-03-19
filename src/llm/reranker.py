"""
Business-aware LLM reranker for a small shortlist of already-selected insights.

CRITICAL:
- Does NOT select new insights outside the shortlist.
- Does NOT change any numeric values (used only for reasoning).
- Only reorders/prunes a shortlist returned by the deterministic pipeline.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from . import _load_env, _make_json_serializable


@dataclass
class RerankResult:
    ranked_ids: List[str]
    duplicate_ids: List[str]
    top_3_ids: List[str]
    rationale: str


class BusinessReranker:
    """
    Lightweight reranker that uses the LLM to:
    - Re-rank a SHORTLIST of already-selected insights
    - Flag semantic duplicates not caught by deterministic dedup
    """

    def __init__(self, model: Optional[str] = None) -> None:
        _load_env()
        import os

        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("Missing OPENAI_API_KEY in environment (.env).")

        # Allow a separate model if desired, but default to same family
        self.model = model or os.getenv("OPENAI_RERANK_MODEL", os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))

        from openai import OpenAI  # type: ignore

        self.client = OpenAI(api_key=self.api_key)

    def _build_payload(self, shortlist: List[Any]) -> Dict[str, Any]:
        items: List[Dict[str, Any]] = []
        for sp in shortlist:
            cand = getattr(sp, "candidate", None)
            if cand is None:
                continue

            dims = getattr(cand, "dimensions", {}) or {}
            dimension = list(dims.keys())[0] if dims else "unknown"
            primary_seg = getattr(cand, "primary_segment", {}) or {}
            comp_seg = getattr(cand, "comparison_segment", {}) or {}

            item = {
                "id": getattr(cand, "pattern_id", ""),
                "dimension": dimension,
                "segment": primary_seg.get("value"),
                "comparison_target": comp_seg.get("value"),
                "metric": getattr(cand, "metric_name", ""),
                "observed_value": getattr(cand, "observed_value", None),
                "baseline_value": getattr(cand, "baseline_value", None),
                "effect_size": getattr(sp, "effect_size", None),
                "business_impact": getattr(sp, "business_impact", None),
                "statistical_support": getattr(sp, "statistical_support", None),
                "composite_score": getattr(sp, "composite_score", None),
                "time_period": getattr(cand, "time_period", None),
            }
            items.append(item)

        payload = {"shortlist": items}
        return _make_json_serializable(payload)

    def _call_llm(self, payload: Dict[str, Any]) -> RerankResult:
        system = (
            "You are a senior performance marketing strategist.\n"
            "You receive a SMALL SHORTLIST of already-approved insights from a deterministic engine.\n"
            "CRITICAL RULES:\n"
            "- DO NOT invent new insights or IDs.\n"
            "- DO NOT change or fabricate numeric values.\n"
            "- ONLY use the provided shortlist; never reference IDs not in the input.\n"
        )

        user = (
            "You are given a SHORTLIST of candidate insights.\n"
            "Each insight has: id, dimension, segment, comparison_target, metric, observed_value,\n"
            "baseline_value, effect_size, business_impact, statistical_support, composite_score, time_period.\n\n"
            "Your job:\n"
            "1) Rank all insights from most to least useful for a marketing decision-maker.\n"
            "2) Identify any insights that are semantically duplicates (same business story).\n"
            "3) Recommend the best top 3 IDs.\n\n"
            "IMPORTANT CONSTRAINTS:\n"
            "- You MUST NOT invent new IDs or remove IDs silently.\n"
            "- You MUST NOT change any numeric values (use them only for reasoning).\n"
            "- You MUST ONLY rank the provided insights.\n\n"
            "Return STRICT JSON of the form:\n"
            "{\n"
            '  "ranked_ids": ["id1", "id2", ...],\n'
            '  "duplicate_ids": ["idX", "idY"],\n'
            '  "top_3_ids": ["id1", "id2", "id3"],\n'
            '  "rationale": "short explanation of why these were ranked this way"\n'
            "}\n\n"
            "SHORTLIST JSON:\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )

        # Use chat.completions with JSON mode
        chat = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        text = chat.choices[0].message.content

        data = json.loads(text)
        if not isinstance(data, dict):
            raise RuntimeError("Reranker returned non-dict JSON.")

        ranked_ids = data.get("ranked_ids") or []
        duplicate_ids = data.get("duplicate_ids") or []
        top_3_ids = data.get("top_3_ids") or []
        rationale = data.get("rationale") or ""

        if not isinstance(ranked_ids, list) or not isinstance(duplicate_ids, list) or not isinstance(top_3_ids, list):
            raise RuntimeError("Reranker returned invalid ID lists.")

        ranked_ids = [str(x) for x in ranked_ids]
        duplicate_ids = [str(x) for x in duplicate_ids]
        top_3_ids = [str(x) for x in top_3_ids]

        return RerankResult(
            ranked_ids=ranked_ids,
            duplicate_ids=duplicate_ids,
            top_3_ids=top_3_ids,
            rationale=str(rationale),
        )

    def rerank(self, scored_patterns: List[Any], shortlist_size: int = 8) -> List[Any]:
        """
        Rerank a shortlist (up to shortlist_size) and drop LLM-marked duplicates.
        Falls back to original order on any error.
        """
        if len(scored_patterns) <= 1:
            return scored_patterns
        
        shortlist = scored_patterns[:shortlist_size]
        id_to_sp: Dict[str, Any] = {}
        ordered_ids: List[str] = []
        for sp in shortlist:
            pid = getattr(getattr(sp, "candidate", None), "pattern_id", "") or ""
            if not pid:
                continue
            pid = str(pid)
            id_to_sp[pid] = sp
            ordered_ids.append(pid)
        
        if len(id_to_sp) <= 1:
            return scored_patterns

        # Debug: show candidates before reranking
        try:
            print("\n=== RERANK: Shortlist BEFORE LLM ===")
            for pid in ordered_ids:
                sp = id_to_sp[pid]
                score = getattr(sp, "composite_score", None)
                print(f"- id={pid}, composite_score={score}")
        except Exception:
            pass
        
        try:
            payload = self._build_payload(shortlist)
            result = self._call_llm(payload)
        except Exception:
            # On any LLM failure, keep original deterministic order
            return scored_patterns

        valid_ids = set(ordered_ids)

        # Debug: show raw LLM response IDs
        try:
            print("\n=== RERANK: LLM RESPONSE ===")
            print(f"ranked_ids   = {result.ranked_ids}")
            print(f"duplicate_ids= {result.duplicate_ids}")
            print(f"top_3_ids    = {result.top_3_ids}")
        except Exception:
            pass

        # Sanitize IDs: only allow those from the shortlist
        ranked_ids = [i for i in result.ranked_ids if i in valid_ids]
        if not ranked_ids:
            ranked_ids = ordered_ids

        duplicate_ids = [i for i in result.duplicate_ids if i in valid_ids]

        top_3_ids = [i for i in result.top_3_ids if i in ranked_ids and i not in duplicate_ids]
        if len(top_3_ids) != 3:
            # Fallback: take first 3 from ranked_ids (excluding duplicates)
            seen = set(duplicate_ids)
            top_3_ids = [i for i in ranked_ids if i not in seen][:3]

        # Build final ID order:
        final_ids: List[str] = []
        seen_final: set[str] = set()

        # 1) top_3_ids first
        for i in top_3_ids:
            if i not in seen_final and i not in duplicate_ids:
                final_ids.append(i)
                seen_final.add(i)

        # 2) remaining ranked_ids (excluding duplicates and already used)
        for i in ranked_ids:
            if i in seen_final or i in duplicate_ids:
                continue
            final_ids.append(i)
            seen_final.add(i)

        # 3) any shortlist IDs not seen yet (defensive)
        for i in ordered_ids:
            if i not in seen_final and i not in duplicate_ids:
                final_ids.append(i)
                seen_final.add(i)

        # Debug: final selected top_3 after reranking
        try:
            print("\n=== RERANK: FINAL TOP 3 ===")
            for pid in top_3_ids:
                sp = id_to_sp.get(pid)
                score = getattr(sp, "composite_score", None) if sp is not None else None
                print(f"- id={pid}, composite_score={score}")
            print("=== END RERANK DEBUG ===\n")
        except Exception:
            pass

        # Map back to ScoredPatternCandidate objects
        new_shortlist: List[Any] = [id_to_sp[i] for i in final_ids if i in id_to_sp]

        # Append any remaining patterns beyond the shortlist in original order
        tail = [
            sp
            for sp in scored_patterns
            if getattr(getattr(sp, "candidate", None), "pattern_id", "") not in id_to_sp
        ]

        return new_shortlist + tail

