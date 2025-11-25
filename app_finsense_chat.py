import json
from pathlib import Path
from typing import Dict, Any, List, Optional

import pandas as pd
import streamlit as st
import logging

from src.finsense.chat_engine import ask_finsense

def inject_custom_css() -> None:
    """Lightweight visual polish: cards, badges, and soft hover animations."""
    st.markdown(
        """
        <style>
        /* Tighten up the main page width a bit */
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2rem;
            max-width: 1200px;
        }

        /* Metric cards: give them a card-like feel */
        .stMetric {
            background: radial-gradient(circle at top left,
                                        rgba(56, 189, 248, 0.10),
                                        rgba(15, 23, 42, 0.95));
            border-radius: 0.9rem !important;
            padding: 0.75rem 1rem !important;
            box-shadow: 0 12px 30px rgba(15, 23, 42, 0.8);
            border: 1px solid rgba(148, 163, 184, 0.3);
            transition: transform 120ms ease-out, box-shadow 120ms ease-out;
        }

        .stMetric:hover {
            transform: translateY(-2px);
            box-shadow: 0 18px 40px rgba(15, 23, 42, 0.9);
        }

        /* Metric label text */
        .stMetric label {
            font-size: 0.72rem !important;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: #9ca3af !important;
        }

        /* “Logo strip” badges */
        .finsense-logo-strip {
            margin-top: 0.4rem;
            margin-bottom: 1.1rem;
        }

        .finsense-badge {
            display: inline-flex;
            align-items: center;
            gap: 0.25rem;
            padding: 0.18rem 0.7rem;
            margin-right: 0.35rem;
            margin-bottom: 0.25rem;
            border-radius: 999px;
            border: 1px solid rgba(148, 163, 184, 0.4);
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.09em;
            color: #e5e7eb;
            background: linear-gradient(
                135deg,
                rgba(15, 23, 42, 0.95),
                rgba(30, 64, 175, 0.85)
            );
            box-shadow: 0 10px 25px rgba(15, 23, 42, 0.9);
            transition: transform 130ms ease-out,
                        box-shadow 130ms ease-out,
                        border-color 130ms ease-out;
        }

        .finsense-badge:hover {
            transform: translateY(-1px);
            box-shadow: 0 16px 38px rgba(15, 23, 42, 1);
            border-color: rgba(96, 165, 250, 0.9);
        }

        .finsense-badge-dot {
            width: 0.45rem;
            height: 0.45rem;
            border-radius: 999px;
            background: radial-gradient(circle,
                        rgba(248, 250, 252, 1),
                        rgba(96, 165, 250, 1));
        }

        /* Accordion headers: slightly stronger contrast */
        [data-testid="stExpander"] > details > summary {
            background: linear-gradient(
                90deg,
                rgba(15, 23, 42, 0.94),
                rgba(15, 23, 42, 0.85)
            );
            border-radius: 0.75rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_logo_strip() -> None:
    """Show a simple 'coverage strip' for the tickers in this demo."""
    st.markdown(
        """
        <div class="finsense-logo-strip">
          <span class="finsense-badge">
            <span class="finsense-badge-dot"></span>
            ADBE · SaaS / Creativity
          </span>
          <span class="finsense-badge">
            <span class="finsense-badge-dot"></span>
            NFLX · Streaming Media
          </span>
          <span class="finsense-badge">
            <span class="finsense-badge-dot"></span>
            NVDA · AI / GPUs
          </span>
          <span class="finsense-badge">
            <span class="finsense-badge-dot"></span>
            AMD · Semiconductors
          </span>
        </div>
        """,
        unsafe_allow_html=True,
    )


INSIGHTS_DIR = Path("data/insights")
WATCHLIST_PATH = Path("configs/watchlist.csv")


# ---------- Helpers ----------

def load_watchlist() -> Dict[str, Dict[str, str]]:
    """
    Load configs/watchlist.csv into a ticker → {company_name, sector} mapping.
    Tickers are stored uppercased.
    """
    mapping: Dict[str, Dict[str, str]] = {}

    if not WATCHLIST_PATH.exists():
        return mapping

    try:
        df = pd.read_csv(WATCHLIST_PATH)
    except Exception:
        return mapping

    for _, row in df.iterrows():
        ticker = str(row.get("ticker", "")).upper().strip()
        if not ticker:
            continue
        mapping[ticker] = {
            "company_name": str(row.get("company_name", "")).strip(),
            "sector": str(row.get("sector", "")).strip(),
        }

    return mapping


def derive_ticker_from_filename(file_name: str) -> Optional[str]:
    """
    Best-effort: take the first chunk before '_' and treat as ticker if it looks like one.
    Example: 'AMD_2024Q2_Transcript.json' → 'AMD'
    """
    if "_" not in file_name:
        return None
    first = file_name.split("_", 1)[0].upper()
    # Simple heuristic: 2–5 uppercase letters
    if 2 <= len(first) <= 5 and first.isalpha():
        return first
    return None


def build_display_label(
    pack: Dict[str, Any],
    ticker_info: Dict[str, Dict[str, str]],
) -> str:
    """
    Build the dropdown label for an insight pack.
    Avoids showing '??' and 'FULL_TEXT' etc.
    """
    file_name = pack.get("_file_name", "insight.json")
    raw_ticker = pack.get("ticker") or derive_ticker_from_filename(file_name)

    ticker = raw_ticker or "Unknown"
    ticker = ticker.upper()

    # Company name preference: watchlist, then company_hint, then file name
    wl = ticker_info.get(ticker, {})
    company_from_watchlist = wl.get("company_name") or ""
    company_hint = str(pack.get("company_hint", "")).strip()

    if company_from_watchlist:
        company_display = company_from_watchlist
    elif company_hint:
        company_display = company_hint
    else:
        company_display = file_name.replace(".json", "")

    year = pack.get("fiscal_year")
    quarter = pack.get("fiscal_quarter")

    if year and quarter:
        period_display = f"{year} {quarter}"
    else:
        period_display = "Unknown period"

    seg_idx = pack.get("segment_index")
    seg_display = f"Seg {seg_idx}" if seg_idx is not None else ""

    parts = [ticker, company_display, period_display, seg_display]
    # Remove empty pieces and join cleanly
    label = " | ".join(p for p in parts if p)
    return label


def clean_speaker_for_display(speaker: Optional[str]) -> str:
    """
    Turn internal labels like 'FULL_TEXT' into something user-friendly.
    """
    if not speaker or speaker.upper() in {"FULL_TEXT", "UNKNOWN"}:
        return "Not labeled (full document)"
    return speaker


def format_pct(value: Any) -> str:
    """
    Nicely format percentage values, handling None/NaN.
    """
    if value is None:
        return "N/A"
    try:
        # Handle numpy / pandas types too
        v = float(value)
    except Exception:
        return "N/A"
    return f"{v:.1f}%"


# ---------- Data loading ----------

def load_insight_packs() -> List[Dict[str, Any]]:
    """Load all JSON insight packs from data/insights into a list of dicts, enriched with display fields."""
    packs: List[Dict[str, Any]] = []

    if not INSIGHTS_DIR.exists():
        return packs

    ticker_map = load_watchlist()

    for p in sorted(INSIGHTS_DIR.glob("*.json")):
        try:
            data = json.loads(p.read_text())
        except Exception as e:
            print(f"[WARN] Could not read {p}: {e}")
            continue

        data["_file_name"] = p.name
        data["_path"] = str(p)

        # Derive ticker + sector
        raw_ticker = data.get("ticker") or derive_ticker_from_filename(p.name)
        ticker = raw_ticker.upper() if raw_ticker else None
        data["_ticker"] = ticker

        if ticker and ticker in ticker_map:
            data["_company_name"] = ticker_map[ticker]["company_name"]
            data["_sector"] = ticker_map[ticker]["sector"]
        else:
            data["_company_name"] = data.get("company_hint")
            data["_sector"] = None

        # Clean speaker for display
        data["_speaker_display"] = clean_speaker_for_display(data.get("speaker"))

        # Build label for the dropdown
        data["_label"] = build_display_label(data, ticker_map)

        packs.append(data)

    return packs


# ---------- Streamlit App ----------

def main():
    st.set_page_config(
        page_title="FinSense — Earnings Intelligence Assistant",
        #page_icon="",
        layout="wide",
    )
    # 🔹 New: global CSS polish Turn raw earnings PDFs into CFO signals, KPIs, and an AI-ready Q&A layer for portfolio and credit analytics.
    inject_custom_css()


    # 🔹 New: coverage / logo strip under the title
    
    # Top hero area
    st.markdown(
        """
        <div style="padding: 0.6rem 1rem; border-radius: 0.75rem; background: #0f172a;">
          <h2 style="margin: 0; color: #e5e7eb;">
            FinSense — Earnings Intelligence Assistant
          </h2>
          <p style="margin: 0.25rem 0 0; color: #9ca3af; font-size: 0.9rem;">
            FinSense is a small prototype that turns messy earnings PDFs into structured KPIs, AI summaries, 
            and a simple Q&A interface for each quarter.
            It’s basically an AI-ready Q&A layer that helps analysts quickly see what changed.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_logo_strip()

    

    packs = load_insight_packs()
    if not packs:
        st.error(
            "No insight packs found in `data/insights`.\n\n"
            "Run the ingestion + KPI notebook (`06_kpi_extraction.ipynb`) so that JSON insight files are created."
        )
        return

    # Sidebar selection
    st.sidebar.header("Select earnings set")
    options = [p["_label"] for p in packs]
    choice = st.sidebar.selectbox("Company / period / segment", options=options, index=0)
    selected_pack = packs[options.index(choice)]

    # ---------- Context header / metrics ----------

    col_top_left, col_top_mid, col_top_right = st.columns([1.4, 1.2, 1.2])

    with col_top_left:
        st.markdown("#### Snapshot")

        ticker_display = selected_pack.get("_ticker") or "Unknown"
        company_display = selected_pack.get("_company_name") or selected_pack.get(
            "company_hint", "Unknown company"
        )
        sector_display = selected_pack.get("_sector") or "Not tagged"

        year = selected_pack.get("fiscal_year")
        quarter = selected_pack.get("fiscal_quarter")
        if year and quarter:
            period_display = f"{year} {quarter}"
        else:
            period_display = "Unknown period"

        st.markdown(f"**Company:** {company_display}")
        st.markdown(f"**Ticker:** `{ticker_display}`")
        st.markdown(f"**Sector:** {sector_display}")
        st.markdown(f"**Period:** {period_display}")

        doc_path = (
            selected_pack.get("meta", {}).get("doc_path")
            or selected_pack.get("doc_path")
            or selected_pack.get("_file_name")
        )
        st.caption(f"Source: `{doc_path}`")

    with col_top_mid:
        st.markdown("#### KPIs (auto-extracted)")
        k = selected_pack.get("kpis", {}) or {}

        col_kpi1, col_kpi2 = st.columns(2)
        with col_kpi1:
            st.metric(
                "Revenue YoY",
                format_pct(k.get("revenue_growth_yoy_pct")),
            )
        with col_kpi2:
            st.metric(
                "EPS YoY",
                format_pct(k.get("eps_growth_yoy_pct")),
            )

        guidance_comment = k.get("guidance_comment") or "No explicit guidance language captured."
        margin_comment = k.get("margin_comment") or "No explicit margin commentary captured."

        st.caption("**Guidance:** " + guidance_comment)
        st.caption("**Margins:** " + margin_comment)

    with col_top_right:
        st.markdown("#### Speaker / segment")

        speaker_display = selected_pack.get("_speaker_display", "Not labeled")
        section_display = selected_pack.get("section") or "Not specified"
        seg_idx = selected_pack.get("segment_index")
        seg_label = f"Segment index: {seg_idx}" if seg_idx is not None else "Segment index not tracked"

        st.markdown(f"**Speaker:** {speaker_display}")
        st.markdown(f"**Section:** {section_display}")
        st.caption(seg_label)

        st.markdown(
            "<span style='font-size: 0.85rem; color: #9ca3af;'>"
            "These fields are derived from speaker tags in the source file. "
            "Some IR PDFs don't expose clean speaker labels, so they appear as full-document segments."
            "</span>",
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # ---------- CFO preview & AI summary (both collapsed by default) ----------

    cfo_preview = selected_pack.get("cfo_preview_text")
    with st.expander("CFO prepared remarks (preview)", expanded=False):
        if cfo_preview:
            st.write(cfo_preview)
        else:
            st.info(
                """
                No CFO preview is available for this earnings set in this demo version.
                
                In a full workflow, this panel would display a short excerpt of the CFO’s 
                prepared remarks — giving analysts a quick snapshot before exploring the 
                full transcript or financial statements.
                """
            )

    ai_summary = selected_pack.get("ai_quarter_summary")
    with st.expander("Quarter snapshot (AI summary)", expanded=False):
        if ai_summary:
            st.write(ai_summary)
            st.caption(
                "This AI snapshot is generated from the structured insight pack (KPIs + meta + preview)."
            )
        else:
            st.info(
                """
                No AI quarter summary has been generated for this earnings set.
                
                In the complete FinSense workflow, this panel would contain 
                a 3–5 bullet snapshot highlighting:
                • Revenue and margin direction  
                • Spend themes  
                • Risk commentary  
                • Guidance sentiment  
        """
            )

    st.markdown("---")

    # ---------- Chat with FinSense ----------

    st.markdown(
        """
        <div style="
            padding: 0.8rem 1rem; 
            border-radius: 8px; 
            background: #0f172a; 
            border: 1px solid #1e293b;
            box-shadow: 0 0 12px rgba(0, 255, 180, 0.15);
        ">
          <h4 style="margin: 0; color:#00e5ff; font-weight: 500;">
            “What is the question, Neo?”
          </h4>
        </div>
        """,
        unsafe_allow_html=True,
    )

    session_key = f"chat_history_{selected_pack['_file_name']}"
    if session_key not in st.session_state:
        st.session_state[session_key] = []
    
    # Render past messages
    for msg in st.session_state[session_key]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    
    # Use a form + text_input instead of st.chat_input to avoid auto-scroll
    with st.form("finsense_qa_form", clear_on_submit=True):
        user_question = st.text_input(
            "Ask about this quarter (growth, margins, guidance, risks)…",
            key=f"qa_input_{selected_pack['_file_name']}",
        )
        submitted = st.form_submit_button("Ask FinsSense")
    
    if submitted and user_question.strip():
        # Add user message
        st.session_state[session_key].append({"role": "user", "content": user_question})
        with st.chat_message("user"):
            st.markdown(user_question)
    
    try:
        answer = ask_finsense(user_question, selected_pack)
    except Exception as e:
        # Log the full error for yourself
        logging.exception("Error while calling FinSense")

        err_str = str(e).lower()

        # Friendly messages instead of raw JSON
        if "rate limit" in err_str or "rate_limit_exceeded" in err_str or "429" in err_str:
            answer = (
                "FinSense hit the OpenAI usage limit for this demo.  \n\n"
                "The backend API is throttling requests right now, so I can’t answer this one. "
                "If you’re running locally, you can use your own OpenAI key and avoid this limit."
            )
        elif "api key" in err_str or "authentication" in err_str:
            answer = (
                "FinSense couldn’t reach the OpenAI API.  \n\n"
                "Check that an `OPENAI_API_KEY` is configured in the Streamlit secrets or "
                "environment variables."
            )
        else:
            answer = (
                "Something went wrong while trying to answer this question.  \n\n"
                "You can try again in a bit, or re-run the app locally if you’re experimenting."
            )

        # Add assistant message
        st.session_state[session_key].append({"role": "assistant", "content": answer})
        with st.chat_message("assistant"):
            st.markdown(answer)


if __name__ == "__main__":
    main()
