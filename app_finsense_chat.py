import json
from pathlib import Path

import pandas as pd
import streamlit as st

from src.finsense.chat_engine import ask_finsense

# ----- Paths -----
ROOT = Path(__file__).resolve().parent
INSIGHTS_DIR = ROOT / "data" / "insights"
SUMMARIES_DIR = ROOT / "data" / "summaries"


# ----- Data loaders -----

def load_insight_packs():
    """Load all JSON insight packs from data/insights into a list of dicts."""
    packs = []
    if not INSIGHTS_DIR.exists():
        return packs

    for p in sorted(INSIGHTS_DIR.glob("*.json")):
        try:
            data = json.loads(p.read_text())
        except Exception as e:
            print(f"[WARN] Could not read insight pack {p}: {e}")
            continue

        # Convenience fields for UI
        data["_file_name"] = p.name
        data["_path"] = str(p)

        # Try to derive a short ticker from company_hint if present
        raw_company = str(data.get("company_hint") or "").strip()
        ticker_guess = raw_company.split()[0].upper() if raw_company else "UNKNOWN"
        data["_ticker"] = ticker_guess

        # Normalize year / quarter for display + matching
        fy = str(data.get("fiscal_year", "")).split(".")[0]
        fq = str(data.get("fiscal_quarter", "")).strip()
        data["_fiscal_year_str"] = fy
        data["_fiscal_quarter_str"] = fq

        seg = data.get("meta", {}).get("segment_index")
        seg_str = f"seg {seg}" if seg is not None else "seg ?"

        data["_label"] = f"{ticker_guess} — {fq} {fy} ({seg_str})"
        packs.append(data)

    return packs


def load_summaries():
    """
    Load all quarterly summaries from data/summaries.

    Returns a dict keyed by (ticker, year, quarter) -> summary dict.
    """
    summaries = {}
    if not SUMMARIES_DIR.exists():
        return summaries

    for p in SUMMARIES_DIR.glob("*_summary.json"):
        try:
            data = json.loads(p.read_text())
        except Exception as e:
            print(f"[WARN] Could not read summary {p}: {e}")
            continue

        ticker = str(data.get("ticker") or "").upper()
        year = str(data.get("fiscal_year") or "").split(".")[0]
        quarter = str(data.get("fiscal_quarter") or "").strip()

        if not (ticker and year and quarter):
            continue

        summaries[(ticker, year, quarter)] = data

    return summaries


# ----- Streamlit app -----

def main():
    st.set_page_config(page_title="FinSense — Earnings Call Analyst", layout="wide")

    st.title("FinSense — Earnings Call Analyst")
    st.caption(
        "Prototype internal tool for PMs and credit analysts. "
        "Pipeline: earnings PDFs → transcript ingestion → CFO KPI + sentiment extraction "
        "→ quarterly summaries → Q&A focused on this quarter."
    )

    packs = load_insight_packs()
    summaries = load_summaries()

    if not packs:
        st.error(
            "No insight packs found in `data/insights`.\n\n"
            "Run the ingestion + KPI notebook to generate CFO insight JSON files."
        )
        return

    # Sidebar: select earnings set
    st.sidebar.header("Select Earnings Set")
    st.sidebar.caption("Pick a ticker + quarter. Each entry corresponds to a specific document/segment.")

    options = [p["_label"] for p in packs]
    choice = st.sidebar.selectbox("Company / Period", options=options, index=0)
    selected_pack = packs[options.index(choice)]

    # Derive keys for summary lookup
    ticker = selected_pack.get("_ticker", "UNKNOWN")
    year = selected_pack.get("_fiscal_year_str", "")
    quarter = selected_pack.get("_fiscal_quarter_str", "")
    summary_key = (ticker, year, quarter)
    summary_data = summaries.get(summary_key)

    # ----- Layout: top metrics -----
    st.markdown("### Context")
    top_cols = st.columns(4)

    with top_cols[0]:
        st.metric("Ticker", ticker)
    with top_cols[1]:
        period_label = f"{quarter} {year}" if quarter and year else "—"
        st.metric("Period", period_label)
    with top_cols[2]:
        k = selected_pack.get("kpis", {}) or {}
        rev = k.get("revenue_growth_yoy_pct")
        st.metric("Revenue YoY %", f"{rev:.1f}%" if isinstance(rev, (int, float)) else "N/A")
    with top_cols[3]:
        eps = k.get("eps_growth_yoy_pct")
        st.metric("EPS YoY %", f"{eps:.1f}%" if isinstance(eps, (int, float)) else "N/A")

    meta = selected_pack.get("meta", {}) or {}
    company_pretty = str(selected_pack.get("company_hint") or ticker)
    sector_pretty = meta.get("sector", "Tech / Media").replace("_", " ").title() if isinstance(meta.get("sector"), str) else "Tech / Media"
    speaker = selected_pack.get("speaker", "CFO")
    segment_label = meta.get("section", meta.get("segment_type", "prepared_remarks"))

    st.markdown(
        f"**Company:** {company_pretty} &nbsp; • &nbsp; "
        f"**Sector:** {sector_pretty} &nbsp; • &nbsp; "
        f"**Speaker:** {speaker} &nbsp; • &nbsp; "
        f"**Segment:** {segment_label}"
    )

    source_path = meta.get("doc_path", selected_pack.get("_file_name", ""))
    if source_path:
        st.caption(f"Source file: `{source_path}`")

    st.markdown("---")

    # ----- Quarter snapshot (AI summary) -----
    with st.expander("📌 Quarter snapshot (AI summary)", expanded=True):
        if summary_data:
            st.success("AI snapshot available for this quarter.")
            st.markdown(summary_data.get("summary", ""))
        else:
            st.info(
                "No AI summary generated yet for this quarter.\n\n"
                "From the repo root you can create one with:\n"
                "```bash\n"
                "python -m src.finsense.summarizer TICKER YEAR QUARTER\n"
                "# or summarize all: python -m src.finsense.summarizer\n"
                "```"
            )

    # ----- CFO text preview -----
    with st.expander("📄 Show CFO prepared remarks (preview)", expanded=False):
        raw_text = meta.get("raw_text") or selected_pack.get("text")
        if raw_text:
            st.text_area("Preview", raw_text[:4000], height=220)
        else:
            st.info(
                "No preview text stored in this insight pack yet. "
                "You can extend the pipeline later to persist a short excerpt of the CFO's remarks here."
            )

    st.markdown("---")

    # ----- Q&A section -----
    st.markdown("### 💬 Ask FinSense about this quarter")
    with st.expander("Example questions", expanded=False):
        st.markdown(
            """
            - What drove revenue growth this quarter?
            - How did margins behave vs last year?
            - Did management raise or lower guidance?
            - Any notable risks or spending themes mentioned?
            """
        )

    # Chat history keyed per file, so switching entries keeps separate threads
    session_key = f"chat_history_{selected_pack['_file_name']}"
    if session_key not in st.session_state:
        st.session_state[session_key] = []

    # Render past messages
    for msg in st.session_state[session_key]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    user_question = st.chat_input(
        "Ask about this quarter (growth, margins, guidance, risks)…"
    )

    if user_question:
        # Add user message
        st.session_state[session_key].append({"role": "user", "content": user_question})
        with st.chat_message("user"):
            st.markdown(user_question)

        # Call FinSense
        try:
            answer = ask_finsense(user_question, selected_pack)
        except Exception as e:
            answer = f"Error while calling FinSense: {e}"

        # Add assistant message
        st.session_state[session_key].append({"role": "assistant", "content": answer})
        with st.chat_message("assistant"):
            st.markdown(answer)


if __name__ == "__main__":
    main()
