# FinSense — Earnings Call Analyst

FinSense is a prototype internal tool for **portfolio managers and credit analysts** who live inside earnings transcripts but don’t have time to read every line.

It turns messy IR documents (PDFs, press releases, sample transcripts) into:

- **Quarter-level KPI snapshots** – e.g. revenue YoY, EPS YoY, basic sentiment.
- **LLM-generated quarterly summaries** – “what actually happened this quarter?”
- **An interactive Q&A surface** – ask questions about growth, margins, guidance, risks for a specific ticker and quarter.

The goal is to reduce “time-to-insight” for a new quarter from **hours to minutes**.

---

## Why this exists

In a typical buy-side workflow (Carlyle, multi-strategy funds, long-only shops):

- PMs and sector leads need a **fast sanity check** on new earnings: *Is this quarter broadly in-line? Any surprises? Should we re-underwrite?*
- Associates spend hours stitching together **IR PDFs, press releases, and transcripts**, and pushing bullet points into email, slides, and internal notes.
- There’s no consistent way to **query historical language** across quarters (“how is management talking about AI / capital returns vs last year?”).

FinSense is a small but concrete step towards an internal **earnings intelligence layer**:

> *“Give me a structured, AI-assisted view of this quarter before I dive into the 20-page transcript.”*

---

## High-level architecture

**Input layer**

- `data/raw/` – sample IR PDFs and text files:
  - Sample AMD, ADBE, NVDA, NFLX remarks and press releases.
  - Sustainability / content overview PDFs to show the limits of the pipeline.

**ETL & processing**

1. **Ingestion** (`src/finsense/ingest.py` + `data/processed/transcripts.csv`)
   - Parses PDFs/text into a long, tidy table:
   - Columns like `doc_path`, `company_hint`, `fiscal_year`, `fiscal_quarter`, `segment_index`, `speaker`, `section`, `text`.

2. **KPI & sentiment extraction** (`notebooks/06_kpi_extraction.ipynb`)
   - Filters down to **CFO prepared remarks** (or fallbacks).
   - Extracts lightweight KPIs:
     - `revenue_growth_yoy_pct`
     - `eps_growth_yoy_pct`
     - basic sentiment scores.
   - Writes per-segment insight packs as JSON to `data/insights/`.

3. **Quarterly summarization** (`src/finsense/summarizer.py`)
   - Groups transcripts by `(ticker, fiscal_year, fiscal_quarter)`.
   - Calls an LLM (OpenAI `gpt-4.1-mini`) with:
     - metadata (ticker, company, quarter),
     - CFO / FULL_TEXT snippets.
   - Returns an **analyst-style summary** with:
     - Headline
     - Growth & revenue drivers
     - Margins / profitability
     - Guidance & outlook
     - Risks / watchpoints
   - Writes JSON to `data/summaries/`, e.g. `ADBE_2024_Q2_summary.json`.

**Experience layer**

4. **Streamlit app** (`app_finsense_chat.py`)
   - Dropdown: select `(ticker, quarter, segment)`.
   - Context panel:
     - Ticker, period, revenue YoY, EPS YoY.
     - Company name, sector, speaker, segment type.
   - **Quarter snapshot (AI summary)**:
     - Renders `data/summaries/*_summary.json` if available.
   - **CFO prepared remarks preview**:
     - Optional text preview (or a message explaining why it’s not stored yet).
   - **Q&A chat**:
     - LLM sees the selected insight pack (KPI + sentiment + context).
     - User asks: “What changed in margins vs last year?”, “Any commentary on AI / capex?”, etc.

---

## Quickstart

### 1. Environment

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

pip install -r requirements.txt
