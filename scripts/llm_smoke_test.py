import json
from src.llm.strategic_layer import StrategicLLMLayer

sample_patterns = [
    {
        "id": "underfunded_winner",
        "category": "budget_efficiency",
        "segment_id": "A_vs_B",
        "dimension": "campaign",
        "metric": "roas",
        "observed_value": 2.99,
        "baseline_value": 1.20,
        "importance_score": 0.40,
        "confidence": 0.92,
        "supporting_candidates": ["SEGMENT_GAP_campaign_A_B_roas"],
    }
]

layer = StrategicLLMLayer()
out = layer.analyze(sample_patterns, context={"goal": "Increase ROAS while controlling spend"})
print(json.dumps(out, indent=2, ensure_ascii=False))
