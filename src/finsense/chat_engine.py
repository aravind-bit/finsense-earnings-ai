# src/finsense/chat_engine.py

import os
import time
from typing import Dict

from openai import OpenAI


def _load_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set.")
    return OpenAI(api_key=api_key)


client = _load_client()

SYSTEM_PROMPT = """
You are FinSense, an earnings-call analyst.

You read CFO/CEO remarks and structured KPI data, then answer with:
- crisp, evidence-based analysis
- clear language for product managers, investors, and finance teams
- no hallucinations — only infer from the provided data.

If the question cannot be answered from the data, reply:
"Not enough information in this earnings set to answer with confidence."
""".strip()

MODEL_NAME = "gpt-4.1-mini"


def _call_model_with_retries(messages, max_retries: int = 3) -> str:
    for attempt in range(1, max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=0.2,
            )
            return (resp.choices[0].message.content or "").strip()

        except Exception as e:  # pragma: no cover
            msg = str(e).lower()
            if ("rate limit" in msg or "429" in msg) and attempt < max_retries:
                sleep_s = 5 * attempt
                print(
                    f"[FinSense] Rate limit on attempt {attempt}/{max_retries}, "
                    f"sleeping {sleep_s}s..."
                )
                time.sleep(sleep_s)
                continue
            raise


def ask_finsense(question: str, insight: Dict) -> str:
    """
    Ask a question about a single earnings snapshot.

    `insight` is one JSON dict from data/insights/*.json
    """
    # Very defensive: allow missing keys without exploding
    insight_text = (
        f"Company: {insight.get('company_hint') or insight.get('_company_name')}\n"
        f"Ticker: {insight.get('_ticker')}\n"
        f"Quarter: {insight.get('fiscal_quarter')}, {insight.get('fiscal_year')}\n"
        f"KPIs: {insight.get('kpis')}\n"
        f"Sentiment: {insight.get('sentiment')}\n"
        f"CFO prepared remarks snippet: {insight.get('cfo_prepared_excerpt')}\n"
        f"Quarter summary (if present): {insight.get('ai_quarter_summary')}\n"
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Here is the insight data for one earnings set:\n\n{insight_text}",
        },
        {"role": "user", "content": question},
    ]

    return _call_model_with_retries(messages)
