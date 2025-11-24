import re
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import Iterable, Dict, Any, List

import pandas as pd
from pdfminer.high_level import extract_text

from .paths import RAW, PROCESSED, ROOT
from .config import load_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
LOGGER = logging.getLogger("finsense.ingest")

def read_txt(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")

def read_pdf(p: Path) -> str:
    try:
        return extract_text(str(p))
    except Exception as e:
        LOGGER.warning("PDF read failed for %s: %s", p.name, e)
        return ""

def load_document(p: Path) -> str:
    if p.suffix.lower() == ".pdf":
        return read_pdf(p)
    return read_txt(p)

META_PATTERNS = [
    re.compile(r"\b(Q[1-4])\s*(?:FY|Fiscal Year)?\s*(\d{4})", re.I),
    re.compile(r"\b(FY|Fiscal Year)\s*(\d{4})\s*(Q[1-4])", re.I),
    re.compile(r"(\d{4})\s*Q([1-4])", re.I),
]

def guess_meta_from_filename(name: str) -> Dict[str, Any]:
    company = re.sub(r"[\._-]+", " ", name.split(".")[0])
    fiscal_year, fiscal_quarter = None, None
    for pat in META_PATTERNS:
        m = pat.search(name)
        if m:
            g = m.groups()
            if len(g) == 2 and g[0].upper().startswith("Q"):
                fiscal_quarter, fiscal_year = g[0].upper(), int(g[1])
            elif len(g) == 2 and g[0].upper().startswith("F"):
                fiscal_year, fiscal_quarter = int(g[1]), g[0].upper()
            elif len(g) == 2:
                fiscal_year, fiscal_quarter = int(g[0]), f"Q{g[1]}"
            break
    return {"company_hint": company[:80], "fiscal_year": fiscal_year, "fiscal_quarter": fiscal_quarter}

def clean_text(s: str) -> str:
    s = s.replace("\x00", " ")
    s = re.sub(r"\r\n?", "\n", s)
    s = re.sub(r"[ \t]+\n", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()

def detect_segments(text: str, speaker_line_regex: str) -> List[Dict[str, Any]]:
    pattern = re.compile(speaker_line_regex, re.M)
    matches = list(pattern.finditer(text))
    if not matches:
        return [{"speaker": "FULL_TEXT", "section": "prepared_remarks", "content": text.strip()}]

    segments = []
    last_idx = 0
    for i, m in enumerate(matches):
        if i == 0 and m.start() > 0:
            pre = text[:m.start()].strip()
            if pre:
                segments.append({"speaker": "PREFACE", "section": "preface", "content": pre})
        speaker = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        section = "qa" if speaker.lower().startswith(("q&a", "question-and-answer")) else "prepared_remarks"
        segments.append({"speaker": speaker, "section": section, "content": content})
        last_idx = end
    if last_idx < len(text):
        tail = text[last_idx:].strip()
        if tail:
            segments.append({"speaker": "UNKNOWN", "section": "tail", "content": tail})
    return segments

def iter_docs(raw_dir: Path) -> Iterable[Path]:
    for ext in ("*.txt", "*.pdf"):
        yield from raw_dir.rglob(ext)

def build_records(p: Path, cfg) -> List[Dict[str, Any]]:
    raw = load_document(p)
    if not raw.strip():
        LOGGER.warning("Empty/failed document: %s", p.name)
        return []
    raw = clean_text(raw)
    meta = guess_meta_from_filename(p.name)
    segments = detect_segments(raw, cfg.parse.speaker_line_regex)

    today = datetime.today().date().isoformat()
    recs = []
    for idx, seg in enumerate(segments):
        recs.append({
            "doc_path": str(p.relative_to(ROOT)),
            "company_hint": meta["company_hint"],
            "fiscal_year": meta["fiscal_year"],
            "fiscal_quarter": meta["fiscal_quarter"],
            "ingest_date": today,
            "segment_index": idx,
            "speaker": seg["speaker"],
            "section": seg["section"],
            "text": seg["content"],
            "source": "manual_drop",
        })
    return recs

def run(input_dir: str | None, output_path: str | None):
    cfg = load_config()
    in_dir = Path(input_dir).resolve() if input_dir else RAW
    out_path = Path(output_path) if output_path else (ROOT / cfg.output.parquet_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    logging.info("Scanning: %s", in_dir)
    files = list(iter_docs(in_dir))
    if not files:
        logging.warning("No transcripts found under %s (txt/pdf).", in_dir)
        return
    all_records: List[Dict[str, Any]] = []
    for p in files:
        logging.info("Parsing: %s", p.name)
        all_records.extend(build_records(p, cfg))

    if not all_records:
        logging.warning("No records to write.")
        return

    df = pd.DataFrame(all_records)
    df.to_csv(out_path, index=False)
    logging.info("Wrote %d rows to %s", len(df), out_path)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="FinSense: ingest transcripts from data/raw")
    ap.add_argument("--input", type=str, default=None, help="Input directory (defaults to data/raw)")
    ap.add_argument("--output", type=str, default=None, help="Output parquet (defaults to configs setting)")
    args = ap.parse_args()
    run(args.input, args.output)
