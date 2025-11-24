"""
FinSense summarizer

CLI helper to generate structured quarterly summaries using the OpenAI API.

- Reads data/processed/transcripts.csv
- For each (ticker, fiscal_year, fiscal_quarter) combo, pulls CFO prepared remarks
  (or falls back to FULL_TEXT if needed)
- Calls the LLM to generate a concise, analyst-style summary
- Writes JSON files under data/summaries, e.g. NVDA_2024_Q2_summary.json

Usage (from repo root, with .venv active):

    export OPENAI_API_KEY="sk-..."   # or set this in your shell profile

    # Summarize everything in the file
    python -m src.finsense.summarizer

    # Summarize a single quarter
    python -m src.finsense.summarizer NVDA 2024 Q2
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
from openai import OpenAI

# ---- Paths ----

ROOT = Path(__file__).resolve().parents[2]
TRANSCRIPTS_CSV = ROOT / "data" / "processed" / "transcripts.csv"
OUT_DIR = ROOT / "data" / "summaries"


# ---- OpenAI client loader ----

def _load_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY environment variable is not set. "
            "Set it before running the summarizer."
        )
    return OpenAI(api_key=api_key)


client = _load_client()


# ---- Core LLM call ----

SYSTEM_PROMPT = """
You are FinSense, a buy-side style earnings-call analyst.

You receive:
- basic metadata about an earnings set (ticker, company, quarter),
- the CFO's prepared remarks text (or full text if needed).

You must return a concise but useful summary for a portfolio manager.

Formatting rules:
- Use short paragraphs and bullet points.
- Lead with 'Headline' (1–2 sentences on the quarter).
- Then have sections:
  - Growth & revenue drivers
  - Margins / profitability
  - Guidance & outlook
  - Risks / watchpoints
- Be specific and quantitative when numbers are present.
- If information is missing (e.g., no guidance), say so explicitly.
""".strip()


def _call_summary_llm(payload: Dict) -> str:
    """
    Call the OpenAI chat completion API to generate a summary.
    `payload` is a small dict with metadata + text.
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Here is the earnings context and CFO remarks. "
                "Summarize this quarter following the format rules.\n\n"
                f"METADATA:\n{json.dumps(payload['meta'], indent=2)}\n\n"
                f"CFO / FULL TEXT (truncated):\n{payload['text']}"
            ),
        },
    ]

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=messages,
        temperature=0.2,
    )

    return response.choices[0].message.content.strip()


# ---- Data helpers ----

def _load_transcripts() -> pd.DataFrame:
    if not TRANSCRIPTS_CSV.exists():
        raise FileNotFoundError(f"Transcripts file not found: {TRANSCRIPTS_CSV}")

    df = pd.read_csv(TRANSCRIPTS_CSV)
    # Normalise column names a bit
    for col in ["fiscal_year", "fiscal_quarter"]:
        if col in df.columns:
            # Allow for NaNs and non-int years
            df[col] = df[col].astype("string")

    return df


def _select_cfo_text(
    df: pd.DataFrame, ticker: str, year: str, quarter: str
) -> Tuple[str, Dict]:
    """
    Given the full transcripts DataFrame and a (ticker, year, quarter),
    pick the best CFO text segment and return (text, meta).

    Preference order:
    1. CFO + prepared_remarks
    2. FULL_TEXT + prepared_remarks
    3. Any prepared_remarks
    4. As a last resort, the first segment for that ticker/quarter
    """
    mask_base = (
        (df["fiscal_year"].astype("string") == year)
        & (df["fiscal_quarter"].astype("string") == quarter)
    )

    # Try multiple possible company/ticker columns
    ticker_cols = [c for c in df.columns if c in ("ticker", "company_hint")]
    if ticker_cols:
        col = ticker_cols[0]
        mask_base = mask_base & (df[col].str.upper().str.contains(ticker.upper(), na=False))

    candidates = df[mask_base].copy()
    if candidates.empty:
        raise ValueError(f"No rows found for {ticker} {year} {quarter}")

    def _pick(mask_extra):
        sub = candidates[mask_extra]
        if not sub.empty:
            return sub

    # 1) CFO prepared remarks
    cfo_prepared = _pick(
        (candidates["speaker"].str.upper() == "CFO")
        & (candidates["section"] == "prepared_remarks")
    )
    if cfo_prepared is not None:
        chosen = cfo_prepared
    else:
        # 2) FULL_TEXT prepared remarks
        full_prepared = _pick(candidates["section"] == "prepared_remarks")
        if full_prepared is not None:
            chosen = full_prepared
        else:
            # 3) any prepared remarks
            any_prepared = _pick(candidates["section"] == "prepared_remarks")
            if any_prepared is not None:
                chosen = any_prepared
            else:
                # 4) fallback: first few rows
                chosen = candidates.sort_values("segment_index").head(3)

    # Concatenate text segments in order
    chosen = chosen.sort_values("segment_index")
    full_text = "\n\n".join(chosen["text"].astype(str).tolist())

    # Truncate to keep token usage manageable
    MAX_CHARS = 5000
    if len(full_text) > MAX_CHARS:
        full_text = full_text[:MAX_CHARS] + "\n\n[Truncated for length…]"

    # Build meta for the LLM and for the JSON output
    meta = {
        "ticker": ticker,
        "company_hint": chosen["company_hint"].iloc[0]
        if "company_hint" in chosen.columns
        else ticker,
        "fiscal_year": year,
        "fiscal_quarter": quarter,
        "speaker": "CFO (preferred, with fallbacks)",
        "segment_count": int(chosen.shape[0]),
        "source_docs": sorted(chosen["doc_path"].astype(str).unique().tolist())
        if "doc_path" in chosen.columns
        else [],
    }

    return full_text, meta


# ---- Public API ----

def summarize_quarter(ticker: str, year: str, quarter: str) -> Dict:
    """
    Summarize a single (ticker, year, quarter) into a JSON-ready dict.
    """
    df = _load_transcripts()
    text, meta = _select_cfo_text(df, ticker, year, quarter)

    payload = {"meta": meta, "text": text}
    summary_text = _call_summary_llm(payload)

    result = {
        "ticker": ticker,
        "fiscal_year": year,
        "fiscal_quarter": quarter,
        "summary": summary_text,
        "meta": meta,
    }
    return result


def summarize_all_unique() -> List[Dict]:
    """
    Iterate over all distinct (ticker, year, quarter) combos in transcripts
    and summarize each.

    Returns the list of result dicts.
    """
    df = _load_transcripts()

    # Guess ticker column
    ticker_col = "ticker" if "ticker" in df.columns else "company_hint"

    combos = (
        df[[ticker_col, "fiscal_year", "fiscal_quarter"]]
        .dropna()
        .drop_duplicates()
    )

    results: List[Dict] = []
    for _, row in combos.iterrows():
        ticker = str(row[ticker_col]).split()[0].upper()  # e.g. "ADBE 2024Q2 SAMPLE" -> "ADBE"
        year = str(row["fiscal_year"])
        quarter = str(row["fiscal_quarter"])

        print(f"Summarizing {ticker} {year} {quarter} ...", flush=True)
        try:
            res = summarize_quarter(ticker, year, quarter)
        except Exception as exc:
            print(f"  [WARN] Skipping {ticker} {year} {quarter}: {exc}")
            continue

        _write_summary_file(res)
        results.append(res)

    return results


# ---- I/O helpers ----

def _write_summary_file(summary: Dict) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ticker = summary["ticker"]
    year = summary["fiscal_year"]
    quarter = summary["fiscal_quarter"]

    out_path = OUT_DIR / f"{ticker}_{year}_{quarter}_summary.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"  -> wrote {out_path.relative_to(ROOT)}")
    return out_path


# ---- CLI entrypoint ----

def main(argv: Optional[List[str]] = None) -> None:
    argv = argv or sys.argv[1:]

    if len(argv) == 0:
        # Summarize all combos
        print(f"Loading transcripts from: {TRANSCRIPTS_CSV}")
        summarize_all_unique()
        return

    if len(argv) != 3:
        print(
            "Usage:\n"
            "  python -m src.finsense.summarizer              # summarize all\n"
            "  python -m src.finsense.summarizer TICKER YEAR QUARTER\n"
            "Example:\n"
            "  python -m src.finsense.summarizer ADBE 2024 Q2",
            file=sys.stderr,
        )
        sys.exit(1)

    ticker, year, quarter = argv
    print(f"Summarizing single quarter: {ticker} {year} {quarter}")
    summary = summarize_quarter(ticker, year, quarter)
    _write_summary_file(summary)


if __name__ == "__main__":
    main()
