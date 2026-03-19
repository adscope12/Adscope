from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import os

from dotenv import load_dotenv
from pathlib import Path
from openai import OpenAI


# Load environment variables from .env
load_dotenv(Path.cwd() / ".env")


@dataclass
class StrategicLLMConfig:
    model: str = "gpt-4.1-mini"
    temperature: float = 0.2


class StrategicLLMLayer:
    """
    Strategic LLM Layer - runs AFTER the deterministic insight engine.
    
    Architecture position:
    1. LLM-Assisted Reading Layer (runs BEFORE deterministic engine)
       - Interprets inconsistent column names, platform/campaign/KPI naming
       - Handles multilingual naming (Hebrew/English), typos
       - Preserves relevant fields
    2. Deterministic Insight Engine (runs here)
       - Feature extraction, normalization, pattern generation, scoring
    3. Strategic LLM Layer (this class - runs AFTER deterministic engine)
       - Interprets scored insights produced by the deterministic engine
       - Does NOT invent new insights; only prioritizes and turns them into strategy
    """

    def __init__(self, api_key: Optional[str] = None, config: Optional[StrategicLLMConfig] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")

        if not self.api_key:
            raise ValueError(
                "OPENAI_API_KEY is missing. Put it in .env or export it in the shell."
            )

        self.client = OpenAI(api_key=self.api_key)
        self.config = config or StrategicLLMConfig()

    def analyze(self, insights: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> str:
        """
        Takes scored insights from the engine and produces a strategic interpretation.
        """
        context = context or {}
        prompt = self._build_prompt(insights, context)

        resp = self.client.chat.completions.create(
            model=self.config.model,
            temperature=self.config.temperature,
            messages=[
                {
                    "role": "system",
                    "content": "You are a senior performance marketing analyst. Be concrete and action-oriented.",
                },
                {"role": "user", "content": prompt},
            ],
        )

        return resp.choices[0].message.content.strip()

    def _build_prompt(self, insights: List[Dict[str, Any]], context: Dict[str, Any]) -> str:
        """
        Builds the prompt sent to the LLM.
        """
        return f"""
You will receive scored marketing insights produced by a deterministic engine.
Your job: prioritize, group, and turn them into a short strategy plan.

IMPORTANT:
Do NOT invent new insights. Only use the provided data.

Context (may be empty):
{context}

Insights JSON:
{insights}

Output format:

1) Top 3 priorities (bullets)
   Each must include:
   - what the issue/opportunity is
   - why it matters
   - expected impact

2) Risks / warning signals

3) Recommended next checks (max 5 bullets)

4) One short executive summary paragraph (2–4 sentences)
""".strip()