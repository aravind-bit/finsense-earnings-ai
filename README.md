# **FinSense — Earnings Call Analyst**
### *LLM-powered analytics tool for extracting KPIs, guidance signals, and CFO insights from earnings materials.*

FinSense is an internal-style analytics product designed to help investment teams, credit analysts, and PMs consume earnings information **in minutes instead of hours**.

The system ingests transcripts, press releases, and IR documents from multiple companies, extracts financial signals (revenue YoY, EPS YoY, margin/guidance commentary), generates executive summaries, and exposes a **chat-based interface** for Q&A over each quarter.

FinSense combines:
- **ETL-style ingestion**
- **Document parsing & cleaning**
- **Rule-based KPI extraction**
- **Preview text generation**
- **LLM-based analysis & Q&A**
- **A Streamlit UI for analysts**

---

## ## ⭐ Why This Project Exists

Investment and credit teams routinely sift through:
- 10–60 page earnings transcripts  
- CFO prepared remarks  
- Footnotes and guidance commentary  
- PDF-only IR materials  
- Multiple companies per cycle  

This leads to:
- Long read times  
- Inconsistent note-taking  
- Missed signals in noisy documents  
- Slow turnaround for PM updates and reporting  

**FinSense solves this by automating the first 80% of the analysis.**

---

# **🎯 Product Goals**

### **1. Reduce time-to-insight**
Turn raw earnings materials into:
- CFO summaries  
- KPI extracts  
- Trend commentary  
- LLM-readable insight packs  

### **2. Increase consistency**
A deterministic, repeatable pipeline ensures:
- Standard KPI extraction  
- Normalized metadata  
- Structured quarterly outputs  

### **3. Enable conversational analytics**
Analysts can ask questions like:
- “What changed this quarter?”  
- “Did margins compress?”  
- “What tone did management convey?”  
- “What risks were highlighted?”  

LLM responses are grounded in the extracted data.

---

# **📦 Architecture Overview**

data/raw <-- Earnings PDFs / TXTs (source documents)
data/processed <-- Cleaned transcript segments (CSV)
data/insights <-- Insight packs per quarter (JSON)
src/finsense <-- Pipeline & chat engine
├── ingest.py <-- PDF/TXT ingestion & speaker segmentation
├── config.py <-- Yaml configuration
├── paths.py <-- Project paths
├── chat_engine.py <-- OpenAI-powered Q&A
├── summarizer.py <-- Optional LLM summarization
app_finsense_chat.py <-- Streamlit app (UI layer)
notebooks/
└── 06_kpi_extraction.ipynb <-- KPI extraction and insight pack build


---

# **🔄 Data Pipeline**

### **1. Ingestion**
`src/finsense/ingest.py`:
- Loads PDFs/TXTs  
- Cleans irregular formatting  
- Attempts speaker segmentation  
- Falls back to FULL_TEXT for messy PDFs  
- Writes processed transcripts to CSV  

### **2. KPI & insight extraction**
Notebook `06_kpi_extraction.ipynb`:
- Detects CFO-like segments  
- Extracts:
  - Revenue growth YoY  
  - EPS growth YoY  
  - Margin commentary  
  - Guidance/outlook snippets  
- Generates a **preview_text** for UI display  
- Builds **insight packs** (one JSON per quarter)

Each pack includes:
```json
{
  "company_hint": "NVIDIA",
  "fiscal_year": 2024,
  "fiscal_quarter": "Q2",
  "kpis": {...},
  "sentiment": {...},
  "preview_text": "Revenue grew 13% YoY driven by...",
  "meta": {...}
}
