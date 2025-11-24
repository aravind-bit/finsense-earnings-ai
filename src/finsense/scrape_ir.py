from pathlib import Path
from typing import List, Dict

import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from .paths import CONFIGS


def load_watchlist() -> pd.DataFrame:
    """
    Load the ticker watchlist that defines which companies FinSense tracks.
    Source: configs/watchlist.csv
    """
    path = CONFIGS / "watchlist.csv"
    df = pd.read_csv(path)
    return df


def get_ir_targets() -> List[Dict[str, str]]:
    """
    Return a simple list of dicts:
    [
      {"ticker": "NVDA", "company_name": "...", "ir_url": "...", "priority": "Std"},
      ...
    ]
    This will feed the actual scraper.
    """
    df = load_watchlist()
    records: List[Dict[str, str]] = []
    for _, row in df.iterrows():
        records.append(
            {
                "ticker": row["ticker"],
                "company_name": row["company_name"],
                "ir_url": row["ir_url"],
                "priority": row["priority"],
            }
        )
    return records


HEADERS = {
    "User-Agent": "FinSenseBot/0.1 (+https://github.com/aravind-bit/finsense-earnings-ai)"
}


def discover_pdf_links_for_target(target: Dict[str, str], max_links: int = 10) -> List[Dict[str, str]]:
    """
    Given a single IR target (ticker + ir_url), fetch the IR page and
    try to find candidate PDF links that look like earnings/quarterly results.

    This is a heuristic first pass; later we can refine per-company patterns.
    """
    ir_url = target["ir_url"]
    ticker = target["ticker"]
    company = target["company_name"]

    try:
        resp = requests.get(ir_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"[WARN] Failed to fetch IR page for {ticker} ({ir_url}): {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")

    candidates: List[Dict[str, str]] = []

    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = (a.get_text() or "").strip()

        href_lower = href.lower()
        text_lower = text.lower()

        # Only care about PDFs
        if ".pdf" not in href_lower:
            continue

        # Heuristic: look for earnings-ish language
        if not any(
            kw in href_lower or kw in text_lower
            for kw in [
                "earnings",
                "results",
                "quarter",
                "q1",
                "q2",
                "q3",
                "q4",
                "prepared remarks",
                "presentation",
            ]
        ):
            continue

        full_url = urljoin(ir_url, href)

        candidates.append(
            {
                "ticker": ticker,
                "company_name": company,
                "label": text,
                "pdf_url": full_url,
            }
        )

        if len(candidates) >= max_links:
            break

    return candidates


if __name__ == "__main__":
    targets = get_ir_targets()
    print(f"Loaded {len(targets)} IR targets from watchlist.csv\n")

    if not targets:
        print("No IR targets found.")
    else:
        for target in targets:
            ticker = target["ticker"]
            ir_url = target["ir_url"]
            print(f"=== {ticker} | {ir_url} ===")
            pdf_links = discover_pdf_links_for_target(target, max_links=10)
            print(f"Found {len(pdf_links)} candidate PDF links.")
            # Optionally show the first 1–2 for debugging
            for link in pdf_links[:2]:
                print(f" - {link['pdf_url']}  |  label: {link['label']}")
            print()

