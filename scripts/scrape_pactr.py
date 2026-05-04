"""Scrape PACTR registry via Search_v2.aspx using Playwright.
Submit per-condition basic searches, download CSVs, merge, map to ICTRP schema.
sentinel:skip-file  reason: CLI wrapper around Playwright; hardcoded URLs are config defaults
"""
from __future__ import annotations

import argparse
import io
import re
import sys
import time
from pathlib import Path

# Force UTF-8 on stdout (Windows cp1252 lesson) — guard under __main__ so
# importlib-loading from pytest does not corrupt pytest's capture state.
def _fix_stdout() -> None:
    if hasattr(sys.stdout, "buffer") and "pytest" not in sys.modules:
        sys.stdout = io.TextIOWrapper(  # type: ignore[assignment]
            sys.stdout.buffer, encoding="utf-8", errors="replace"
        )

import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PACTR_URL = "https://pactr.samrc.ac.za/Search_v2.aspx"

DEFAULT_QUERIES = [
    "tuberculosis",
    "HIV",
    "sickle cell",
    "schistosomiasis",
    "maternal sepsis",
    "neonatal sepsis",
    "snakebite",
    "helminth",
    "cervical cancer",
    "cholera",
]

DEFAULT_OUT = Path("C:/Users/user/data/ictrp/pactr_2026-05-04.csv")

# ICTRP required columns (matches ictrp_loader.REQUIRED_COLUMNS)
REQUIRED_COLUMNS = [
    "TrialID",
    "Source Register",
    "Conditions",
    "Secondary IDs",
    "Results URL",
    "Date registered",
    "Countries",
    "Primary Sponsor",
    "Recruitment Status",
]

_PACTR_DATE_RE = re.compile(
    r"(\d{1,2})/(\d{1,2})/(\d{4})(?:\s+\d{1,2}:\d{2}:\d{2}\s+[APap][Mm])?$"
)


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

def _parse_pactr_date(raw: str) -> str:
    """Convert PACTR MM/DD/YYYY (optionally with HH:MM:SS AM) to ISO YYYY-MM-DD.

    Returns empty string for blank/null/unparseable input.
    """
    if not isinstance(raw, str) or not raw.strip():
        return ""
    val = raw.strip()
    m = _PACTR_DATE_RE.match(val)
    if m:
        month, day, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        # Sanity-check year: PACTR records have some 1/1/1900 sentinel
        if year < 1980:
            return ""
        return f"{year:04d}-{month:02d}-{day:02d}"
    return ""


def _first_non_empty_date(*candidates: str) -> str:
    """Return the first non-empty ISO date from candidates (already parsed)."""
    for c in candidates:
        parsed = _parse_pactr_date(c)
        if parsed:
            return parsed
    return ""


# ---------------------------------------------------------------------------
# Field mapping
# ---------------------------------------------------------------------------

def map_pactr_to_ictrp(raw: pd.DataFrame) -> pd.DataFrame:
    """Map a raw PACTR CSV DataFrame to ICTRP required columns.

    Returns a new DataFrame with exactly REQUIRED_COLUMNS plus any extra
    PACTR-native columns preserved after them.
    """
    out = pd.DataFrame()

    # TrialID <- TrialNumber
    out["TrialID"] = raw["TrialNumber"].fillna("").astype(str)

    # Source Register: constant
    out["Source Register"] = "PACTR"

    # Conditions: concatenate Diseases + titles + description for condition_matcher
    def _concat_conditions(row: pd.Series) -> str:
        parts = []
        for col in ("Diseases", "PublicTitle", "OfficialScientificTitle", "Description"):
            val = row.get(col, "")
            if isinstance(val, str) and val.strip():
                parts.append(val.strip())
        return " | ".join(parts)

    out["Conditions"] = raw.apply(_concat_conditions, axis=1)

    # Secondary IDs: preserve as-is; replace NaN with ""
    sec = raw.get("Secondary IDs", pd.Series([""] * len(raw)))
    out["Secondary IDs"] = sec.where(sec.notna(), "").astype(str)
    # Guard against literal "nan" strings
    out["Secondary IDs"] = out["Secondary IDs"].replace("nan", "")

    # Results URL: ReportingResultURLHyperlinks first, then PublicationURL
    def _results_url(row: pd.Series) -> str:
        for col in ("ReportingResultURLHyperlinks", "PublicationURL"):
            val = row.get(col, "")
            if isinstance(val, str) and val.strip() and val.strip().lower() != "nan":
                return val.strip()
        return ""

    out["Results URL"] = raw.apply(_results_url, axis=1)

    # Date registered: EthicsApprovalDate, then ActualStartDate, then AnticipatedStartDate
    def _date_registered(row: pd.Series) -> str:
        return _first_non_empty_date(
            row.get("EthicsApprovalDate", ""),
            row.get("ActualStartDate", ""),
            row.get("AnticipatedStartDate", ""),
        )

    out["Date registered"] = raw.apply(_date_registered, axis=1)

    # Countries: period-separated -> semicolon-separated
    def _countries(val) -> str:
        if not isinstance(val, str) or not val.strip():
            return ""
        # PACTR uses ". " as separator between countries
        parts = [c.strip() for c in re.split(r"\.\s+", val.strip())]
        # Remove trailing period from last token if present
        cleaned = []
        for p in parts:
            p = p.rstrip(".")
            if p:
                cleaned.append(p)
        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for c in cleaned:
            if c not in seen:
                seen.add(c)
                unique.append(c)
        return "; ".join(unique)

    out["Countries"] = raw["RecruitmentCentreCountry"].apply(_countries)

    # Primary Sponsor: take first value if multi-valued (period-separated)
    def _primary_sponsor(val) -> str:
        if not isinstance(val, str) or not val.strip():
            return ""
        parts = [p.strip() for p in re.split(r"\.\s+", val.strip())]
        # Return first non-empty
        for p in parts:
            p = p.rstrip(".")
            if p:
                return p
        return ""

    out["Primary Sponsor"] = raw["SponsorName"].apply(_primary_sponsor)

    # Recruitment Status: direct
    out["Recruitment Status"] = raw["RecruitmentStatus"].fillna("").astype(str)

    return out


# ---------------------------------------------------------------------------
# Per-query scraping
# ---------------------------------------------------------------------------

def _scrape_query(
    page,
    query: str,
    scratch_dir: Path,
    idx: int,
    total: int,
    retries: int = 3,
) -> Path | None:
    """Scrape a single query from PACTR. Returns path to downloaded CSV or None."""
    out_path = scratch_dir / "raw" / f"{query.replace(' ', '_')}.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    backoff = 5
    for attempt in range(1, retries + 1):
        try:
            # Navigate fresh each attempt
            page.goto(PACTR_URL, wait_until="networkidle", timeout=60_000)

            # Fill basic search
            page.fill("#txtBasicSearch", query)

            # Click the visible search trigger — the page CSS hides #btnBasicSearch;
            # the actual visible search element is an <a> LinkButton (lbBasicSearch).
            search_link = page.locator('a[href*="lbBasicSearch"]')
            if search_link.count() > 0 and search_link.is_visible():
                search_link.click()
            else:
                # Fallback: force-click the hidden submit button via JS
                page.evaluate(
                    "__doPostBack('ctl00$MainContent$ctrlSearch$lbBasicSearch','')"
                )
            try:
                page.wait_for_selector(
                    "text=Total records found:", timeout=60_000
                )
            except Exception:
                # Fallback: wait for networkidle
                page.wait_for_load_state("networkidle", timeout=60_000)

            # Check for zero results
            body_text = page.inner_text("body")
            if "Total records found: 0" in body_text or "No records found" in body_text:
                print(f"[{idx}/{total}] '{query}' -> 0 rows (empty result — logged, continuing)")
                return None

            # Set download dropdown to value 9 = "Download all in CSV"
            page.select_option("#ddlDownloadTrials", value="9")

            # Trigger download
            with page.expect_download(timeout=60_000) as dl_info:
                page.click("#btnDownloadTrials")
            download = dl_info.value
            download.save_as(str(out_path))

            # Count rows
            try:
                df_tmp = pd.read_csv(
                    out_path, dtype=str, low_memory=False, on_bad_lines="warn"
                )
                nrows = len(df_tmp)
            except Exception:
                nrows = "?"
            print(f"[{idx}/{total}] '{query}' -> {nrows} rows")
            return out_path

        except Exception as exc:
            if attempt < retries:
                print(
                    f"[{idx}/{total}] '{query}' attempt {attempt}/{retries} failed: {exc}; "
                    f"retrying in {backoff}s"
                )
                time.sleep(backoff)
                backoff *= 2
            else:
                print(f"[{idx}/{total}] '{query}' FAILED after {retries} attempts: {exc}")
                return None

    return None


# ---------------------------------------------------------------------------
# Main scrape routine
# ---------------------------------------------------------------------------

def scrape_all(
    queries: list[str],
    out_path: Path,
    scratch_dir: Path,
    headless: bool = True,
) -> pd.DataFrame | None:
    """Run all queries, merge, map to ICTRP schema, write output CSV."""
    from playwright.sync_api import sync_playwright

    raw_paths: list[Path] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        for idx, query in enumerate(queries, start=1):
            path = _scrape_query(page, query, scratch_dir, idx, len(queries))
            if path is not None:
                raw_paths.append(path)
            # Politeness pause between queries (5-10s)
            if idx < len(queries):
                time.sleep(7)

        browser.close()

    if not raw_paths:
        print("ERROR: No CSV files downloaded. Aborting.")
        return None

    # Merge
    dfs: list[pd.DataFrame] = []
    for p in raw_paths:
        try:
            df = pd.read_csv(p, dtype=str, low_memory=False, on_bad_lines="warn")
            dfs.append(df)
        except Exception as exc:
            print(f"WARNING: Failed to read {p}: {exc}")

    if not dfs:
        print("ERROR: All downloaded CSVs failed to parse.")
        return None

    merged = pd.concat(dfs, ignore_index=True)

    # Deduplicate on TrialNumber (keep first occurrence)
    before_dedup = len(merged)
    merged = merged.drop_duplicates(subset=["TrialNumber"], keep="first")
    print(f"Merged: {before_dedup} total rows -> {len(merged)} unique trials after dedup")

    # Map to ICTRP schema
    ictrp = map_pactr_to_ictrp(merged)

    # Verify required columns present
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in ictrp.columns]
    if missing_cols:
        print(f"ERROR: Missing required columns after mapping: {missing_cols}")
        return None

    # Write output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ictrp.to_csv(out_path, index=False, encoding="utf-8")
    print(f"Written: {out_path}")

    # Stats
    pct_sec_ids = (ictrp["Secondary IDs"].str.len() > 0).mean() * 100
    print(f"Total rows: {len(ictrp)}")
    print(f"Unique trials: {ictrp['TrialID'].nunique()}")
    print(f"% with non-empty Secondary IDs: {pct_sec_ids:.1f}%")

    return ictrp


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape PACTR via Search_v2.aspx and produce ICTRP-format CSV"
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Output CSV path (default: {DEFAULT_OUT})",
    )
    parser.add_argument(
        "--queries",
        type=str,
        default=None,
        help="Comma-separated list of search queries (default: all 10 conditions)",
    )
    parser.add_argument(
        "--headless",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run Chromium in headless mode (default: True)",
    )
    parser.add_argument(
        "--scratch-dir",
        type=Path,
        default=Path("C:/Users/user/data/ictrp/scratch"),
        help="Directory for per-query raw CSV files",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    _fix_stdout()
    args = _parse_args(argv)

    queries = DEFAULT_QUERIES
    if args.queries:
        queries = [q.strip() for q in args.queries.split(",") if q.strip()]

    print(f"Scraping {len(queries)} queries from PACTR...")
    print(f"Queries: {queries}")
    print(f"Output: {args.out}")
    print(f"Headless: {args.headless}")
    print()

    result = scrape_all(
        queries=queries,
        out_path=args.out,
        scratch_dir=args.scratch_dir,
        headless=args.headless,
    )

    return 0 if result is not None else 1


if __name__ == "__main__":
    sys.exit(main())
