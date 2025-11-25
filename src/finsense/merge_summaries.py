import json
import logging
from pathlib import Path

from .paths import ROOT, DATA

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s"
)
LOGGER = logging.getLogger("finsense.merge_summaries")

SUMMARIES_DIR = DATA / "summaries"
INSIGHTS_DIR = DATA / "insights"


def _load_quarter_summaries():
    """
    Load all per-quarter AI summaries from data/summaries into a dict keyed by
    (ticker, fiscal_year, fiscal_quarter).

    Expects filenames like: TICKER_2024_Q2_summary.json
    """
    summaries = {}
    if not SUMMARIES_DIR.exists():
        LOGGER.warning("Summaries dir %s does not exist.", SUMMARIES_DIR)
        return summaries

    for p in SUMMARIES_DIR.glob("*_summary.json"):
        try:
            data = json.loads(p.read_text())
        except Exception as e:
            LOGGER.warning("Could not read summary %s: %s", p.name, e)
            continue

        stem_parts = p.stem.split("_")
        if len(stem_parts) < 3:
            LOGGER.warning("Unexpected summary filename format: %s", p.name)
            continue

        ticker = stem_parts[0].upper()
        try:
            fiscal_year = int(stem_parts[1])
        except ValueError:
            LOGGER.warning("Could not parse year in %s", p.name)
            continue
        fiscal_quarter = stem_parts[2]  # e.g. "Q2"

        key = (ticker, fiscal_year, fiscal_quarter)
        summaries[key] = data

    LOGGER.info("Loaded %d quarter summaries.", len(summaries))
    return summaries


def _infer_ticker_from_insight_path(p: Path, data: dict) -> str:
    """
    Try to infer a clean ticker from the insight JSON.
    Priority:
      1) explicit `ticker` field (if present)
      2) filename prefix before first underscore
      3) first token of company_hint
    """
    if "ticker" in data and data["ticker"]:
        return str(data["ticker"]).upper()

    stem = p.stem  # e.g. "ADBE_2024Q2_seg1"
    if "_" in stem:
        ticker = stem.split("_")[0].upper()
        if ticker:
            return ticker

    company_hint = str(data.get("company_hint", "")).strip()
    if company_hint:
        return company_hint.split()[0].upper()

    return "UNKNOWN"


def merge_summaries_into_insights():
    """
    For each insight pack in data/insights, look up a matching per-quarter
    summary in data/summaries and, if found, embed:
      - ai_quarter_summary
      - ai_quarter_highlights (optional list of bullets)
    back into the insight JSON.
    """
    quarter_summaries = _load_quarter_summaries()
    if not quarter_summaries:
        LOGGER.warning("No quarter summaries found; nothing to merge.")
        return

    if not INSIGHTS_DIR.exists():
        LOGGER.warning("Insights dir %s does not exist.", INSIGHTS_DIR)
        return

    updated = 0
    skipped = 0

    for p in INSIGHTS_DIR.glob("*.json"):
        try:
            data = json.loads(p.read_text())
        except Exception as e:
            LOGGER.warning("Could not read insight %s: %s", p.name, e)
            continue

        fiscal_year = data.get("fiscal_year")
        fiscal_quarter = data.get("fiscal_quarter")

        if fiscal_year is None or fiscal_quarter is None:
            skipped += 1
            continue

        ticker = _infer_ticker_from_insight_path(p, data)
        key = (ticker, int(fiscal_year), str(fiscal_quarter))

        summary = quarter_summaries.get(key)
        if not summary:
            skipped += 1
            continue

        # Pull a few fields we care about; tolerate whatever shape the summary JSON has.
        data["ticker"] = ticker
        data["ai_quarter_summary"] = summary.get(
            "ai_quarter_summary",
            summary.get("summary", "No AI summary text stored for this quarter."),
        )
        data["ai_quarter_highlights"] = summary.get(
            "highlights",
            summary.get("bullets", []),
        )

        # Optional: also store the raw summary blob under an `ai_summary_raw` key if you like
        # data["ai_summary_raw"] = summary

        p.write_text(json.dumps(data, indent=2))
        updated += 1

    LOGGER.info(
        "Merge complete. Updated %d insight packs with AI summaries. Skipped %d.",
        updated,
        skipped,
    )


def main():
    LOGGER.info("Merging AI quarter summaries into insight packs...")
    merge_summaries_into_insights()


if __name__ == "__main__":
    main()

