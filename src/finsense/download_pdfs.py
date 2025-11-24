import os
import requests
from pathlib import Path
from datetime import datetime

from .scrape_ir import get_ir_targets, discover_pdf_links_for_target
from .paths import RAW

HEADERS = {"User-Agent": "FinSenseBot/0.1"}

def safe_filename(s: str) -> str:
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in s)

def download_pdf(url: str, out_path: Path):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        print(f"[ERROR] Failed to download {url}: {e}")
        return False
    
    out_path.write_bytes(resp.content)
    print(f"Saved PDF → {out_path}")
    return True

def run(max_per_company: int = 1):
    targets = get_ir_targets()
    print(f"Loaded {len(targets)} IR targets.\n")

    RAW.mkdir(parents=True, exist_ok=True)

    for target in targets:
        ticker = target["ticker"]
        company = target["company_name"]

        print(f"=== {ticker} ({company}) ===")

        links = discover_pdf_links_for_target(target, max_links=5)
        print(f"Found {len(links)} candidate PDFs.")

        if not links:
            print("Skipping.\n")
            continue

        # Download only the first one for speed
        for link in links[:max_per_company]:
            pdf_url = link["pdf_url"]
            label = link["label"]

            # Build filename
            now = datetime.now()
            fname = f"{ticker}_{now.year}Q{now.month//3 + 1}_{safe_filename(label[:40])}.pdf"
            out_path = RAW / fname

            download_pdf(pdf_url, out_path)

        print()

if __name__ == "__main__":
    run()

