# app_finsense_chat.py

import json
import logging
from pathlib import Path
from typing import List, Dict, Any

import streamlit as st

from src.finsense.chat_engine import ask_finsense

# ---- logging ----
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("finsense_chat")

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
INSIGHTS_DIR = DATA_DIR / "insights"


# ---------- helpers ----------

def load_insight_packs() -> List[Dict[str, Any]]:
    packs: List[Dict[str, Any]] = []
    if not INSIGHTS_DIR.exists():
        return packs

    for p in sorted(INSIGHTS_DIR.glob("*.json")):
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
            obj["_file_name"] = p.name

            # labels for dropdown
            ticker = obj.get("_ticker") or obj.get("ticker") or "?"
            company = obj.get("_company_name") or obj.get("company_hint") or "Unknown"
            fy = obj.get("fiscal_year")
            fq = obj.get("fiscal_quarter")
            obj["_label"] = f"{ticker} | {company} | {fy} {fq}"

            packs.append(obj)
        except Exception as e:  # pragma: no cover
            logger.exception("Failed to load insight %s: %s", p, e)
    return packs


def inject_custom_css():
    st.markdown(
        """
        <style>
        body {
            background-color: #020617;
        }
        .finsense-hero {
            padding: 1rem 1.5rem;
            border-radius: 1rem;
            background: #020617;
            border: 1px solid #1f2937;
        }
        .finsense-hero h1 {
            margin: 0;
            font-size: 2rem;
            color: #e5e7eb;
        }
        .finsense-hero p {
            margin: 0.3rem 0 0;
            color: #9ca3af;
            font-size: 0.95rem;
        }
        .finsense-chip-row {
            margin-top: 0.75rem;
            display: flex;
            flex-wrap: wrap;
            gap: 0.4rem;
        }
        .finsense-chip {
            padding: 0.15rem 0.65rem;
            border-radius: 999px;
            border: 1px solid #1f2937;
            background: #020617;
            color: #9ca3af;
            font-size: 0.75rem;
            letter-spacing: .04em;
            text-transform: uppercase;
        }
        .finsense-question-card {
            margin-top: 1.25rem;
            padding: 1rem 1.5rem;
            border-radius: 1rem;
            border: 1px solid #1f2937;
            background: linear-gradient(135deg, #020617, #0f172a);
        }
        .finsense-question-card h3 {
            margin: 0 0 0.5rem 0;
            font-size: 1.4rem;
            color: #e5e7eb;
        }
        .finsense-question-card p {
            margin: 0;
            color: #9ca3af;
            font-size: 0.9rem;
        }
        .finsense-chat-bubble-user {
            padding: 0.5rem 0.75rem;
            border-radius: 0.75rem;
            background: #0f172a;
            margin-top: 0.5rem;
        }
        .finsense-chat-bubble-assistant {
            padding: 0.5rem 0.75rem;
            border-radius: 0.75rem;
            background: #020617;
            border: 1px solid #1f2937;
            margin-top: 0.35rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def quarter_summary_from_insight(insight: Dict[str, Any]) -> str:
    # See if the insight already has a quarter-level summary attached
    summary = insight.get("ai_quarter_summary") or insight.get("summary")
    if isinstance(summary, dict):
        # if summarizer wrote { "ticker": ..., "summary": "..." }
        summary = summary.get("summary")
    return summary or "No AI summary attached yet for this quarter."


def cfo_excerpt_from_insight(insight: Dict[str, Any]) -> str:
    return insight.get("cfo_prepared_excerpt") or insight.get("text") or "Preview not available."


# ---------- main app ----------

def main():
    st.set_page_config(
        page_title="FinSense — Earnings Intelligence Assistant",
        layout="wide",
    )
    inject_custom_css()

    # Hero
    st.markdown(
        """
        <div class="finsense-hero">
          <h1>FinSense — Earnings Intelligence Assistant</h1>
          <p>
            FinSense is a small prototype that turns messy earnings PDFs into structured KPIs,
            AI summaries, and a simple Q&amp;A interface for each quarter. It’s basically an
            AI-ready Q&amp;A layer that helps analysts quickly see what changed.
          </p>
          <div class="finsense-chip-row">
            <span class="finsense-chip">ADBE · SAAS / CREATIVITY</span>
            <span class="finsense-chip">NFLX · STREAMING MEDIA</span>
            <span class="finsense-chip">NVDA · AI / GPUS</span>
            <span class="finsense-chip">AMD · SEMICONDUCTORS</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("")  # spacing

    # Load packs
    packs = load_insight_packs()
    if not packs:
        st.error(
            "No insight packs found in `data/insights`.\n\n"
            "Run the ingestion + KPI notebook (`06_kpi_extraction.ipynb`) "
            "and the summariser so that JSON insight files are created."
        )
        return

    # Sidebar selection
    st.sidebar.header("Select earnings set")
    options = [p["_label"] for p in packs]
    choice = st.sidebar.selectbox("Company / period / segment", options, index=0)
    selected = packs[options.index(choice)]

    # ---------- snapshot row ----------
    col_snap, col_kpi, col_spk = st.columns([1.1, 1.1, 1.1])

    with col_snap:
        st.markdown("### Snapshot")
        company = selected.get("_company_name") or selected.get("company_hint") or "Unknown"
        ticker = selected.get("_ticker") or selected.get("ticker")
        fy = selected.get("fiscal_year")
        fq = selected.get("fiscal_quarter")
        sector = selected.get("sector") or selected.get("sector_hint") or "Tech"

        st.markdown(f"**Company:** {company}")
        if ticker:
            st.markdown(f"**Ticker:** `{ticker}`")
        st.markdown(f"**Sector:** {sector}")
        st.markdown(f"**Period:** {fy} {fq}")
        src = selected.get("doc_path") or selected.get("_file_name")
        if src:
            st.caption(f"Source: `{src}`")

    with col_kpi:
        st.markdown("### KPIs (auto-extracted)")

        k = selected.get("kpis", {}) or {}
        rev = k.get("revenue_growth_yoy_pct")
        eps = k.get("eps_growth_yoy_pct")
        guidance = k.get("guidance_commentary") or selected.get("guidance")
        margins = k.get("margin_commentary") or selected.get("margins")

        c1, c2 = st.columns(2)
        with c1:
            st.metric(
                "REVENUE YOY",
                f"{rev:.1f}%" if isinstance(rev, (int, float)) else "N/A",
            )
        with c2:
            st.metric(
                "EPS YOY",
                f"{eps:.1f}%" if isinstance(eps, (int, float)) else "N/A",
            )

        st.markdown(
            f"**Guidance:** {guidance or 'guidance commentary detected'}"
        )
        st.markdown(
            f"**Margins:** {margins or 'margin commentary detected'}"
        )

    with col_spk:
        st.markdown("### Speaker / segment")
        speaker = selected.get("speaker") or "Not labeled (full document)"
        section = selected.get("section") or "prepared_remarks"
        seg_idx = selected.get("segment_index", 0)

        st.markdown(f"**Speaker:** {speaker}")
        st.markdown(f"**Section:** {section}")
        st.markdown(f"Segment index: {seg_idx}")

        st.caption(
            "These fields are derived from speaker tags in the source file. "
            "Some IR PDFs don't expose clean speaker labels, so they appear "
            "as full-document segments."
        )

    st.markdown("---")

    # ---------- expanders ----------
    with st.expander("CFO prepared remarks (preview)"):
        st.write(cfo_excerpt_from_insight(selected))

    with st.expander("Quarter snapshot (AI summary)"):
        st.write(quarter_summary_from_insight(selected))

    st.markdown("")

    # ---------- Q&A card ----------
    st.markdown(
        """
        <div class="finsense-question-card">
          <h3>“What is the question, Neo?”</h3>
          <p>Ask about this quarter (growth, margins, guidance, risks)…</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    user_q = st.text_input(
        "Ask about this quarter (growth, margins, guidance, risks)…",
        key="user_question",
        label_visibility="collapsed",
    )

    if st.button("Ask FinSense") and user_q.strip():
        q = user_q.strip()
        st.session_state.chat_history.append(("user", q))
        try:
            with st.spinner("Thinking like an over-caffeinated earnings analyst…"):
                answer = ask_finsense(q, selected)
            st.session_state.chat_history.append(("assistant", answer))
        except Exception as e:
            logger.exception("Error while calling FinSense: %s", e)
            st.session_state.chat_history.append(
                (
                    "assistant",
                    "Something went wrong while trying to answer this question.\n\n"
                    "If you're running the demo in the cloud, it might be hitting the "
                    "free OpenAI usage caps. Try again later or run it locally with "
                    "your own API key.",
                )
            )

    # render chat
    for role, content in st.session_state.chat_history:
        if role == "user":
            st.markdown(
                f"<div class='finsense-chat-bubble-user'>🧑‍💻 <b>You</b>: {content}</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"<div class='finsense-chat-bubble-assistant'>🤖 <b>FinSense</b>: {content}</div>",
                unsafe_allow_html=True,
            )


if __name__ == "__main__":
    main()
