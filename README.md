# FinSense — Earnings Intelligence Assistant  
*AI-powered prototype that extracts CFO insights, KPIs, and guidance signals from earnings materials.*

FinSense is an internal-style analytics product that accelerates how investment teams, credit analysts, and product leaders consume quarterly earnings information.

Instead of manually reading 10–50 page transcripts or IR PDFs, FinSense converts raw documents into:

- Structured KPI extracts  
- Guidance & margin commentary  
- CFO preview remarks  
- AI-generated quarterly summaries  
- A conversational Q&A interface on top of each quarter

The goal: reduce the “first 80%” of earnings analysis from **hours to minutes**, so humans can focus on judgment, not document-wrangling.

---

## 📌 Why This Exists

Across buy-side research, private credit, and corporate finance, analysts repeatedly:

- Read long, inconsistent earnings materials  
- Manually extract revenue/EPS growth each quarter  
- Search for guidance and margin commentary by hand  
- Skim CFO/CEO remarks for tone and narrative changes  
- Copy/paste notes into trackers and emails to PMs  
- Answer the same questions about “what changed this quarter?”

This leads to:

- Slow turnaround during earnings weeks  
- Missed language and guidance signals  
- No standard, repeatable framework  
- Analyst fatigue and inconsistent notes  

**FinSense automates the foundational layer of earnings intelligence.**

---

## Product Goals

1. **Accelerate decision-making**  
   Turn raw earnings documents into structured, queryable insight packs.

2. **Deliver consistency**  
   Use a repeatable pipeline for CFO signals, guidance mentions, and KPI extraction.

3. **Enable conversational analytics**  
   Allow PMs and analysts to ask natural questions like:
   - “What changed this quarter vs last?”
   - “Did margins expand or compress?”
   - “How did AI / content investment evolve?”
   and receive grounded, document-aware answers.

---

##  Core Features

### 1. Automated Document Ingestion

- Supports `.pdf` and `.txt` earnings materials  
- Uses a YAML-driven parsing config (`configs/finsense.yaml`)  
- Attempts to segment by speaker when transcripts are structured  
- Falls back to full-text mode for simple IR PDFs / press releases  

### 2. KPI & Signal Extraction (Notebook Workflow)

Notebook: notebooks/06_kpi_extraction.ipynb

From the processed transcript data, the notebook:

Filters down to CFO-style segments / prepared remarks where possible

Extracts basic but high-signal KPIs with simple, transparent logic:

Revenue YoY %

EPS YoY % (where present)

Margin commentary (expansion/compression language)

Guidance/outlook commentary

Adds a short CFO preview excerpt when available

Packages everything into compact insight packs written as JSON:

data/insights/
  ├── NVDA_2024Q2_segX.json
  ├── AMD_2024Q2_segY.json
  └── ...


Each insight pack contains:

company_hint, fiscal_year, fiscal_quarter

speaker, section

kpis (revenue, EPS, commentary fields)

meta (doc path, ingest date, segment index)

optional cfo_preview_text

The extraction is intentionally simple and interpretable: more like a V1 analytics backbone than a black-box model.

### 3. AI-Generated Quarter Snapshot

Module: src/finsense/summarizer.py

Given an insight pack, FinSense can generate a short AI summary of the quarter, such as:

What changed vs prior expectations (if present in the text)

High-level direction of growth / profitability

Notable narrative themes (AI, content spend, restructuring, etc.)

These summaries are stored back onto the insight packs as a field like:

"ai_quarter_summary": "Short bullet-style or paragraph summary..."


This is designed to mimic the type of quick brief a PM might want before a meeting.

### 4. LLM-Powered Q&A (Chat Engine)

Module: src/finsense/chat_engine.py

The chat engine:

Loads an insight pack

Builds a focused prompt using:

CFO preview text

Extracted KPIs

Commentary fields

Meta (company, period, segment)

Calls an OpenAI model and returns grounded, text-only answers

#### Analysts can ask:

“How did revenue and EPS trend this quarter?”

“Any hints of margin pressure?”

“What are the main risks management is flagging?”

This is wired directly into the Streamlit front-end.

### 5. Streamlit Front-End — FinSense Chat

File: app_finsense_chat.py

The app behaves like a light internal product:

#### Sidebar:

Top Metrics / Context:

Company (from filename + mappings)

Ticker (when derivable from filenames like AMD_2024Q2_...)

Period (Year + Quarter)

Sector (from a simple watchlist mapping where available)

#### CFO Panel:

CFO preview text (if present)

Extracted KPIs (Revenue YoY %, EPS YoY %)

Guidance/margin commentary fields

Quarter Snapshot (AI Summary):

Collapsible section; stays closed by default

Shows the AI-generated summary if available

Displays a small note if no summary has been generated yet

Chat with FinSense:

Chat-style interface (user questions + AI answers)

Chat history is session-based per insight pack

Designed to mimic how a PM would interrogate a quarter

This is deliberately minimal but professional — something that would not look out of place as an internal tool inside a credit or equity analytics team.

## 🛠 Tech Stack
Language & Core

Python 3.13

pandas, numpy

Document Handling

pdfminer.six for PDF text extraction

Basic regex & string ops for segment detection and KPI parsing

Configuration

PyYAML for finsense.yaml parsing rules

Simple environment-based project paths (paths.py)

AI / NLP

OpenAI Chat Completions API

Deterministic schema for passing KPIs + context into prompts

App Layer

streamlit for the front-end

Deployed on Streamlit Community Cloud

## 🗂 Project Structure
finsense-earnings-ai/
├── app_finsense_chat.py          # Streamlit front-end (FinSense chat)
├── configs/
│   ├── finsense.yaml             # Parsing & output config
│   └── watchlist.csv             # Ticker → name → sector mapping
├── data/
│   ├── raw/                      # Input earnings materials (PDF, TXT)
│   ├── processed/
│   │   └── transcripts.csv       # Output of ingestion pipeline
│   └── insights/                 # Insight packs (JSON)
├── notebooks/
│   └── 06_kpi_extraction.ipynb   # KPI extraction & pack generation
└── src/
    └── finsense/
        ├── __init__.py
        ├── config.py             # YAML config loader
        ├── ingest.py             # Ingestion / parsing logic
        ├── paths.py              # Project path helpers
        ├── chat_engine.py        # LLM Q&A
        └── summarizer.py         # Quarter snapshot summaries

## Career & Product Relevance

This project is intentionally designed to look and feel like an internal analytics product, not just a notebook:

Full pipeline: ingestion → processing → insights → UI → AI

Config-driven parsing (YAML) for maintainability

JSON insight packs for downstream reuse (BI, notebooks, APIs)

Q&A layer that aligns with how PMs / credit analysts actually think

It demonstrates experience at the intersection of:

Product management for analytics platforms

BI / data engineering workflows

AI-assisted analysis in financial contexts

Translating ambiguous business questions into concrete data products

That aligns strongly with roles like:

Manager, Product Management – Analytics (e.g., private credit / global credit teams)

Analytics Product Lead / Analytics Engineer in asset management or fintech

Data & BI PMs who own reporting ecosystems, not just single dashboards

## Possible Extensions

Some natural next steps:

Multi-quarter trend comparison per ticker

Peer benchmarking (e.g., AMD vs NVDA vs ADBE)

Sentiment scoring using finance-tuned models (FinBERT, etc.)

Automated scraping of the latest IR materials per ticker

Support for audio transcripts (earnings calls → Whisper → FinSense pipeline)

Export to Power BI / Tableau-ready tables for portfolio dashboards

### Contact

Author: Aravind Anisetti

📧 Email: anisetti.ar@gmail.com

🌐 Portfolio: aravind-bit.github.io/portfolio-aravind

💼 LinkedIn: linkedin.com/in/aravindsai-anisetti

FinSense is a learning and demonstration project — feedback, ideas, and collaboration are welcome.
