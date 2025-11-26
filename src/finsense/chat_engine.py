# src/finsense/chat_engine.py

import os
from openai import OpenAI

# --- Load API key safely ---
def _load_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set.")
    return OpenAI(api_key=api_key)

client = _load_client()

# --- Base prompt ---
SYSTEM_PROMPT = """
You are FinSense, an earnings-call analyst.
You read CFO/CEO remarks and structured KPI data, then answer with:
- crisp, evidence-based analysis
- clarity suitable for product managers, investors, and finance teams
- no hallucinations — only infer from provided data.

If the question cannot be answered from the provided insight data, reply:
"Not enough information in this earnings set to answer with confidence."
"""

def ask_finsense(question: str, insight: dict) -> str:
    """
    Ask a question about CFO insights.
    'insight' is the JSON dictionary generated in the KPI insight pack.
    """
    insight_text = (
        f"Company: {insight.get('company_hint')}\n"
        f"Quarter: {insight.get('fiscal_quarter')}, {insight.get('fiscal_year')}\n"
        f"KPIs: {insight.get('kpis')}\n"
        f"Sentiment: {insight.get('sentiment')}\n"
        f"Speaker: {insight.get('speaker')}\n"
        f"Section: {insight.get('section')}\n"
    )

    response = client.chat.completions.create(
        model="gpt-4o-nano",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Insight data:\n{insight_text}"},
            {"role": "user", "content": question},
        ],
        temperature=0.2,
    )

    # NOTE: new OpenAI SDK: message is an object, use .content
    return response.choices[0].message.content

