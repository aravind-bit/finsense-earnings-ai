import os
import json
import time
from pathlib import Path
from typing import Dict, Any, Iterable

import pandas as pd
from openai import OpenAI
from openai import RateLimitError, APIError, APIStatusError

# ---------- PATHS ----------
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"
SUMMARIES_DIR = DATA_DIR / "summaries"
SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)


# ---------- OPENAI CLIENT ----------
def _load_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY environment variable is not set.\n"
            "Run: export OPENAI_API_KEY='your_key_here'"
        )
    return OpenAI(api_key=api_key)


client = _load_client()


# ---------- UTILS ----------
def infer_ticker(doc_path: Any, company_hint: Any) -> str:
    """
    Derive a ticker from doc_path (preferred) or fallback to company_hint.
    Keeps summarizer functional even if transcripts.csv lacks a ticker column.
    """
    ticker = ""

    # Try from filename: ADBE_2024Q2_Remarks.txt
    if isinstance(doc_path, str):
        name = Path(doc_path).name.split(".")[0]
        if "_" in name:
            cand = name.split("_")[0].upper()
            if cand.isalpha() and 2 <= len(cand) <= 6:
                ticker = cand

    # Fallback: first token of company_hint
    if not ticker and isinstance(company_hint, str):
        cand = company_hint.split()[0].upper()
        if cand.isalpha() and 2 <= len(cand) <= 8:
            ticker = cand

    return ticker or "UNKNOWN"


def build_prompt(ticker: str, year: int, quarter: str, text: str) -> str:
    """
    Prompt for mini-LLM summary.
    """
    return f"""
You are an equities / credit analyst.

Summarise this quarter in 3–6 sentences for a portfolio manager.
Company: {ticker}
Period: {year} {quarter}

Source text (prepared remarks + relevant segments):
---
{text[:15000]}
---

Focus on:
- revenue / margin / EPS trends
- guidance direction
- risks or watchpoints
- tone shifts or major themes

Avoid hype. Be factual and neutral.
"""


def _safe_chat_completion(prompt: str, max_retries: int = 3, base_delay: float = 10.0) -> str:
    """
    Call OpenAI with simple exponential backoff on rate limits / transient API errors.
    """
    attempt = 0
    while True:
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a concise but thorough buy-side analyst. "
                            "Your summaries must be factual and investment-grade."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
            )
            return resp.choices[0].message.content.strip()
        except (RateLimitError, APIError, APIStatusError) as e:
            attempt += 1
            if attempt > max_retries:
                raise RuntimeError(f"Giving up after {max_retries} retries: {e}") from e
            delay = base_delay * (2 ** (attempt - 1))
            print(f"  -> Rate / API limit hit (attempt {attempt}/{max_retries}). Sleeping {delay:.0f}s...")
            time.sleep(delay)


def summarise_quarter(ticker: str, year: int, quarter: str, text_block: str) -> str:
    """
    Summarise one quarter for one ticker.
    """
    prompt = build_prompt(ticker, year, quarter, text_block)
    return _safe_chat_completion(prompt)


def _iter_groups(df: pd.DataFrame) -> Iterable:
    """
    Convenience generator to iterate through grouped quarters.
    """
    return df.groupby(["ticker", "fiscal_year", "fiscal_quarter"], dropna=False)


# ---------- MAIN PIPELINE ----------
def main():
    csv_path = PROCESSED_DIR / "transcripts.csv"
    print(f"Loading transcripts from: {csv_path}")
    df = pd.read_csv(csv_path)

    # Ensure ticker exists
    if "ticker" not in df.columns:
        df["ticker"] = df.apply(
            lambda r: infer_ticker(r.get("doc_path"), r.get("company_hint")),
            axis=1,
        )

    # numeric fiscal year / quarter cleanup
    df["fiscal_year"] = pd.to_numeric(df.get("fiscal_year"), errors="coerce")
    df = df.dropna(subset=["fiscal_year", "fiscal_quarter"])
    df["fiscal_year"] = df["fiscal_year"].astype(int)

    # Keep only earnings prepared-remarks rows
    df = df[df.get("section") == "prepared_remarks"]

    if df.empty:
        print("No prepared_remarks with fiscal year/quarter. Nothing to summarise.")
        return

    groups = _iter_groups(df)

    for (ticker, year, quarter), g in groups:
        if ticker == "UNKNOWN":
            print(f"Skipping UNKNOWN ticker group {year} {quarter}")
            continue

        out_path = SUMMARIES_DIR / f"{ticker}_{year}_{quarter}_summary.json"
        if out_path.exists():
            print(f"Skipping {ticker} {year} {quarter} (already summarised).")
            continue

        texts = [t for t in g["text"].astype(str).tolist() if t.strip()]
        if not texts:
            print(f"Skipping {ticker} {year} {quarter} — no text.")
            continue

        text_block = "\n\n---\n\n".join(texts)
        print(f"Summarising {ticker} {year} {quarter} ...")

        try:
            summary = summarise_quarter(ticker, year, str(quarter), text_block)
        except Exception as e:
            print(f"  -> ERROR summarising {ticker} {year} {quarter}: {e}")
            continue

        payload: Dict[str, Any] = {
            "ticker": ticker,
            "fiscal_year": year,
            "fiscal_quarter": str(quarter),
            "summary": summary,
        }

        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"  -> wrote {out_path}")


if __name__ == "__main__":
    main()
