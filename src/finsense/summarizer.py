# src/finsense/summarizer.py

import os
import json
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple

import numpy as np
import pandas as pd
from openai import OpenAI

# -------- Paths --------

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"
SUMMARIES_DIR = DATA_DIR / "summaries"

MODEL_NAME = "gpt-4.1-mini"  # quarter-level summaries


# -------- OpenAI client --------

def _load_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY environment variable is not set. "
            "Export it in your shell before running the summarizer."
        )
    return OpenAI(api_key=api_key)


client = _load_client()


# -------- Helpers --------

def infer_ticker(doc_path: Any, company_hint: Any) -> str:
    """
    Derive a ticker symbol from the file name first, then fall back to company_hint.
    This keeps us robust even if 'ticker' is missing in transcripts.csv.
    """
    ticker = ""

    # Try to pull from file name, e.g. 'AMD_2025Q4_Transcript.pdf'
    if isinstance(doc_path, str) and doc_path:
        name = Path(doc_path).name
        base = name.split(".")[0]
        if "_" in base:
            candidate = base.split("_")[0].upper()
            if candidate.isalpha() and 2 <= len(candidate) <= 6:
                ticker = candidate

    # Fallback: first token of company_hint
    if not ticker and isinstance(company_hint, str) and company_hint:
        candidate = company_hint.split()[0].upper()
        if 2 <= len(candidate) <= 8:
            ticker = candidate

    return ticker or "UNKNOWN"


def build_quarter_prompt(
    ticker: str, fiscal_year: int, fiscal_quarter: str, text_block: str
) -> str:
    """
    Build the user prompt we send to the LLM for each (ticker, year, quarter).
    """
    return f"""
You are an equities / credit analyst.

Summarise the earnings story for this quarter as if explaining to a portfolio manager.
Company: {ticker}
Period: {fiscal_year} {fiscal_quarter}

The following text combines selected prepared remarks and context from the quarter:
---
{text_block[:15000]}
---

Write a concise summary (3–6 sentences) focused on:
- Top-line and bottom-line trends (growth, margins, EPS if mentioned)
- Any explicit guidance changes or tone shift
- Risks / watchpoints the PM should keep in mind.

Avoid hype. Be factual and neutral in tone.
""".strip()


def call_model_with_retries(prompt: str, max_retries: int = 3) -> str:
    """
    Call the chat model with simple retry logic for rate-limit errors.
    Returns the summary text.
    """
    for attempt in range(1, max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a concise but thorough buy-side analyst. "
                            "Summaries must be neutral, factual, and directly useful "
                            "for an investment committee or credit committee."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
            )
            return (resp.choices[0].message.content or "").strip()

        except Exception as e:  # pragma: no cover
            msg = str(e).lower()
            if ("rate limit" in msg or "429" in msg) and attempt < max_retries:
                sleep_s = 10 * attempt
                print(
                    f"  -> Rate / API limit hit (attempt {attempt}/{max_retries}). "
                    f"Sleeping {sleep_s}s..."
                )
                time.sleep(sleep_s)
                continue
            raise


def summarise_quarter(
    ticker: str, fiscal_year: int, fiscal_quarter: str, text_block: str
) -> str:
    """High-level wrapper."""
    prompt = build_quarter_prompt(ticker, fiscal_year, fiscal_quarter, text_block)
    return call_model_with_retries(prompt)


def iter_groups(
    df: pd.DataFrame,
) -> Iterable[Tuple[str, int, str, pd.DataFrame]]:
    """
    Yield (ticker, year, quarter, group_df) tuples, with types normalised.
    """
    groups = df.groupby(["ticker", "fiscal_year", "fiscal_quarter"], dropna=False)
    for (ticker, year, quarter), g in groups:
        if not isinstance(ticker, str):
            ticker = str(ticker)
        if pd.isna(year):
            continue
        year_int = int(year)
        quarter_str = str(quarter)
        yield ticker, year_int, quarter_str, g


def _safe_json(val):
    """Convert numpy/pandas scalars into plain Python types for JSON."""
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        return float(val)
    if isinstance(val, (np.ndarray,)):
        return val.tolist()
    return val


# -------- Main pipeline --------

def main() -> None:
    # 1) Load transcripts
    csv_path = PROCESSED_DIR / "transcripts.csv"
    print(f"Loading transcripts from: {csv_path}")
    df = pd.read_csv(csv_path)

    # 2) Ensure 'ticker' exists
    if "ticker" not in df.columns:
        df["ticker"] = df.apply(
            lambda r: infer_ticker(r.get("doc_path"), r.get("company_hint")),
            axis=1,
        )

    # 3) Clean fiscal year / quarter and keep only prepared remarks
    df["fiscal_year"] = pd.to_numeric(df.get("fiscal_year"), errors="coerce")
    df = df.dropna(subset=["fiscal_year", "fiscal_quarter"])
    df["fiscal_year"] = df["fiscal_year"].astype(int)

    if "section" in df.columns:
        df = df[df["section"] == "prepared_remarks"]

    if df.empty:
        print(
            "No usable prepared_remarks rows with fiscal_year and fiscal_quarter. "
            "Nothing to summarise."
        )
        return

    SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)

    # 4) Loop over (ticker, year, quarter)
    for ticker, year, quarter, g in iter_groups(df):
        if ticker == "UNKNOWN":
            continue

        texts = [
            str(t) for t in g.get("text", []) if isinstance(t, str) and t.strip()
        ]
        if not texts:
            print(f"Skipping {ticker} {year} {quarter} – no text.")
            continue

        text_block = "\n\n---\n\n".join(texts)
        print(f"Summarising {ticker} {year} {quarter} ...")

        try:
            summary_text = summarise_quarter(ticker, year, quarter, text_block)
        except Exception as e:
            print(f"  -> ERROR summarising {ticker} {year} {quarter}: {e}")
            continue

        payload: Dict[str, Any] = {
            "ticker": _safe_json(ticker),
            "fiscal_year": _safe_json(year),
            "fiscal_quarter": _safe_json(quarter),
            "summary": _safe_json(summary_text),
        }

        out_path = SUMMARIES_DIR / f"{ticker}_{year}_{quarter}_summary.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"  -> wrote {out_path}")


if __name__ == "__main__":
    main()
