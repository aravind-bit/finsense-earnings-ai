"""
FinSense — Unified Pipeline Runner

This script performs the full end-to-end analytics workflow:

1. Load watchlist
2. Discover PDF links from IR pages
3. Download PDFs into data/raw
4. Run transcript ingestion
5. Extract CFO KPI + sentiment insights
6. Write insight packs to data/insights

Run with:
    python -m src.finsense.pipeline_run
"""

import pandas as pd
from pathlib import Path
import json
import numpy as np

from .scrape_ir import get_ir_targets, discover_pdf_links_for_target
from .download_pdfs import download_pdf
from .paths import RAW, CONFIGS, PROCESSED
from .ingest import run as ingest_run


####################################################
# 0. Helpers
####################################################

def to_python(obj):
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.ndarray,)):
        return obj.tolist()
    return obj

def safe_filename(s: str) -> str:
    allowed = "-_.() "
    return "".join(c if c.isalnum() or c in allowed else "_" for c in str(s))


####################################################
# 1. PDF Discovery + Download
####################################################

def step_discover_and_download(max_per_company=1):
    print("\n=== STEP 1: Discovering & Downloading PDFs ===")

    targets = get_ir_targets()
    RAW.mkdir(parents=True, exist_ok=True)

    total_downloaded = 0

    for target in targets:
        ticker = target["ticker"]
        ir_url = target["ir_url"]

        print(f"\n--- {ticker} ---")
        links = discover_pdf_links_for_target(target, max_links=5)
        print(f"Found {len(links)} candidate PDFs")

        for link in links[:max_per_company]:
            url = link["pdf_url"]
            label = safe_filename(link["label"][:40])
            fname = f"{ticker}_{label}.pdf"
            out_path = RAW / fname

            if download_pdf(url, out_path):
                total_downloaded += 1

    print(f"\nCompleted PDF download step. Total PDFs downloaded: {total_downloaded}")
    return total_downloaded


####################################################
# 2. Transcript Ingestion
####################################################

def step_ingest():
    print("\n=== STEP 2: Ingesting Transcripts ===")
    ingest_run(None, None)  # uses defaults from config
    out_path = PROCESSED / "transcripts.csv"
    print("Ingestion complete:", out_path)
    return out_path


####################################################
# 3. CFO KPI + Sentiment Extraction (script version)
####################################################

def extract_basic_kpis(text: str):
    import re
    kpis = {
        "revenue_growth_yoy_pct": None,
        "eps_growth_yoy_pct": None,
        "guidance_comment": None,
        "margin_comment": None,
    }

    if not isinstance(text, str) or not text.strip():
        return kpis

    lower = text.lower()

    # Revenue YoY
    m = re.search(r"(\\d+)%\\s+year[- ]?over[- ]?year", lower)
    if m:
        try:
            kpis["revenue_growth_yoy_pct"] = int(m.group(1))
        except ValueError:
            pass

    # EPS
    m = re.search(r"eps\\s+(?:grew|increased|up)\\s+(\\d+)%", lower)
    if m:
        try:
            kpis["eps_growth_yoy_pct"] = int(m.group(1))
        except ValueError:
            pass

    # Guidance
    if any(w in lower for w in ["guidance", "outlook", "forecast"]):
        kpis["guidance_comment"] = "..."

    # Margin
    if "margin" in lower:
        kpis["margin_comment"] = "..."

    return kpis


from textblob import TextBlob
def extract_sentiment(text: str):
    if not isinstance(text, str) or not text.strip():
        return {"polarity": 0.0, "subjectivity": 0.0}
    tb = TextBlob(text)
    return {
        "polarity": float(tb.sentiment.polarity),
        "subjectivity": float(tb.sentiment.subjectivity),
    }


def step_extract_insights():
    print("\n=== STEP 3: Extracting CFO KPI + Sentiment Insights ===")

    df = pd.read_csv(PROCESSED / "transcripts.csv")
    print("Loaded transcripts:", len(df))

    # Filter CFO prepared remarks
    cfo_df = df[
        (df["speaker"].str.contains("CFO", case=False, na=False)) &
        (df["section"] == "prepared_remarks")
    ]

    print("CFO segments found:", len(cfo_df))

    rows = []
    for _, r in cfo_df.iterrows():
        text = r["text"]

        kpis = extract_basic_kpis(text)
        sent = extract_sentiment(text)

        rows.append({
            "company_hint": r["company_hint"],
            "doc_path": r["doc_path"],
            "fiscal_year": r["fiscal_year"],
            "fiscal_quarter": r["fiscal_quarter"],
            "segment_index": r["segment_index"],
            "revenue_growth_yoy_pct": kpis["revenue_growth_yoy_pct"],
            "eps_growth_yoy_pct": kpis["eps_growth_yoy_pct"],
            "guidance_comment": kpis["guidance_comment"],
            "margin_comment": kpis["margin_comment"],
            "sentiment_polarity": sent["polarity"],
            "sentiment_subjectivity": sent["subjectivity"],
        })

    enriched = pd.DataFrame(rows)
    print("Enriched rows:", len(enriched))

    # Save insight packs
    insight_dir = Path(PROCESSED).parent / "insights"
    insight_dir.mkdir(parents=True, exist_ok=True)

    for idx, row in enriched.iterrows():
        fname = safe_filename(f"{row['company_hint']}_{row['fiscal_year']}_{row['fiscal_quarter']}_seg{row['segment_index']}.json")
        out_path = insight_dir / fname

        with out_path.open("w", encoding="utf-8") as f:
            json.dump({k: to_python(v) for k, v in row.items()}, f, indent=2)

    print(f"Wrote {len(enriched)} insight packs → {insight_dir}")
    return enriched


####################################################
# 4. Main Orchestration
####################################################

def run_pipeline():
    print("\n==========================")
    print("   FinSense Pipeline Run  ")
    print("==========================")

    downloaded = step_discover_and_download(max_per_company=1)
    ingest_path = step_ingest()
    insights = step_extract_insights()

    print("\n=== PIPELINE COMPLETE ===")
    print(f"PDFs downloaded: {downloaded}")
    print(f"CFO insight packs: {len(insights)}")


if __name__ == "__main__":
    run_pipeline()

