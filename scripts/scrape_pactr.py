"""Scrape PACTR registry via Search_v2.aspx using Playwright.
Submit per-condition basic searches, download CSVs, merge, map to ICTRP schema.
Also supports --mode full: date-paginated full-registry scrape (year windows 2008-2026).
sentinel:skip-file  reason: CLI wrapper around Playwright; hardcoded URLs are config defaults
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import time
from pathlib import Path

# Force UTF-8 on stdout (Windows cp1252 lesson) — guard under __main__ so
# importlib-loading from pytest does not corrupt pytest's capture state.
def _fix_stdout() -> None:
    if hasattr(sys.stdout, "buffer") and "pytest" not in sys.modules:
        sys.stdout = io.TextIOWrapper(  # type: ignore[assignment]
            sys.stdout.buffer, encoding="utf-8", errors="replace",
            line_buffering=True,  # flush after every newline (critical for background runs)
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
DEFAULT_FULL_OUT = Path("C:/Users/user/data/ictrp/pactr_full_2026-05-04.csv")

# Row count above which a year window is considered cap-likely and subdivided
# into monthly sub-windows. Set well below any expected server cap (e.g., 1000).
CAP_THRESHOLD = 800

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
# Date-window helpers
# ---------------------------------------------------------------------------

def iter_year_windows(year_from: int, year_to: int) -> list[tuple[str, str]]:
    """Return list of (start_date, end_date) MM/DD/YYYY strings, one per year.

    Both year_from and year_to are inclusive. Covers 01/01/YYYY – 12/31/YYYY.
    """
    windows = []
    for year in range(year_from, year_to + 1):
        windows.append((f"01/01/{year}", f"12/31/{year}"))
    return windows


def iter_month_windows(year: int) -> list[tuple[str, str]]:
    """Return 12 monthly (start_date, end_date) MM/DD/YYYY strings for a given year."""
    import calendar
    windows = []
    for month in range(1, 13):
        last_day = calendar.monthrange(year, month)[1]
        start = f"{month:02d}/01/{year}"
        end = f"{month:02d}/{last_day:02d}/{year}"
        windows.append((start, end))
    return windows


# ---------------------------------------------------------------------------
# Per-date-window scraping
# ---------------------------------------------------------------------------

def _expand_advanced_and_date_panels(page) -> None:
    """Expand the PACTR 'Advanced Search' accordion and 'Registration Date' sub-panel.

    The date fields (#txtRegistrationFromValue / #txtRegistrationToValue) live inside
    two nested Bootstrap collapse panels:
      1. #divEditAdvanced  — the top-level '[Advanced search]' section (collapsed by default)
      2. #divRegistrationDate — the 'Registration Date' row within the advanced panel

    Both must be expanded before the date inputs become interactable.
    We JS-click the Bootstrap data-toggle anchors, then wait for the panels to animate open.
    """
    page.evaluate("""
        () => {
            const adv = document.querySelector('[href="#divEditAdvanced"]');
            if (adv) adv.click();
        }
    """)
    page.wait_for_timeout(700)

    page.evaluate("""
        () => {
            const reg = document.querySelector('[href="#divRegistrationDate"]');
            if (reg) reg.click();
        }
    """)
    page.wait_for_timeout(700)


def _set_date_field(page, field_id: str, value: str) -> None:
    """Set a date input value using the native HTMLInputElement setter.

    PACTR's date fields are bound by jQuery's bootstrap-datepicker. A plain
    page.fill() does not trigger the picker's internal event handlers, so the
    value is silently ignored on form submission.  Using the native value
    descriptor setter fires the correct 'input'+'change' sequence and the
    postback correctly includes the value.
    """
    page.evaluate(
        """
        ([id, val]) => {
            const el = document.getElementById(id);
            if (!el) return;
            const setter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value'
            ).set;
            setter.call(el, val);
            el.dispatchEvent(new Event('input',  { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }
        """,
        [field_id, value],
    )


def _scrape_date_window(
    page,
    start_date: str,
    end_date: str,
    label: str,
    scratch_dir: Path,
    idx: int,
    total: int,
    retries: int = 3,
) -> tuple[Path | None, int]:
    """Scrape a single date window from PACTR. Returns (csv_path | None, row_count).

    Expands the 'Advanced Search' and 'Registration Date' accordion panels,
    fills the date fields using the native value setter (required for jQuery
    bootstrap-datepicker to register the value on postback), then submits via
    the Advanced Search button (#MainContent_ctrlSearch_btnSearch).

    row_count is 0 when the result page says no records.
    row_count is -1 on hard failure (all retries exhausted).
    """
    safe_label = re.sub(r"[/\\]", "-", label)
    out_path = scratch_dir / "raw_full" / f"{safe_label}.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    backoff = 5
    for attempt in range(1, retries + 1):
        try:
            # Navigate fresh each attempt.
            # Use domcontentloaded (not networkidle) — PACTR keeps background XHR
            # requests running for analytics/calendars that delay networkidle by minutes.
            page.goto(PACTR_URL, wait_until="domcontentloaded", timeout=90_000)

            # Expand the Advanced Search section and Registration Date sub-panel
            _expand_advanced_and_date_panels(page)

            # Verify date fields are now visible before filling
            if not page.locator("#txtRegistrationFromValue").is_visible():
                raise RuntimeError(
                    "Registration date fields not visible after expanding panels"
                )

            # Set date values using native setter (page.fill() bypasses jQuery datepicker handlers)
            _set_date_field(page, "txtRegistrationFromValue", start_date)
            _set_date_field(page, "txtRegistrationToValue", end_date)

            # Submit via the Advanced Search button (NOT lbBasicSearch which is basic-search only)
            page.click("#MainContent_ctrlSearch_btnSearch")

            # Wait for results — generous timeout for large date windows where server
            # processing of the result set may take >60s (observed for 2019+ windows).
            try:
                page.wait_for_selector("text=Total records found:", timeout=120_000)
            except Exception:
                # Fallback: wait for domcontentloaded (faster than networkidle on PACTR)
                page.wait_for_load_state("domcontentloaded", timeout=120_000)

            # Check for zero results
            body_text = page.inner_text("body")
            if "Total records found: 0" in body_text or "No records found" in body_text:
                print(f"[{idx}/{total}] '{label}' -> 0 rows (empty — continuing)")
                return None, 0

            # Extract displayed row count for cap detection
            displayed_count = 0
            m = re.search(r"Total records found:\s*(\d+)", body_text)
            if m:
                displayed_count = int(m.group(1))

            # Set download dropdown to value 9 = "Download all in CSV"
            page.select_option("#ddlDownloadTrials", value="9")

            # Trigger download — allow up to 10 minutes for server to generate large CSVs
            # (2019 range consistently times out at 5 min — server-side query may be slow)
            with page.expect_download(timeout=600_000) as dl_info:
                page.click("#btnDownloadTrials")
            download = dl_info.value
            download.save_as(str(out_path))

            # Count rows in downloaded file
            try:
                df_tmp = pd.read_csv(
                    out_path, dtype=str, low_memory=False, on_bad_lines="warn"
                )
                nrows = len(df_tmp)
            except Exception:
                nrows = displayed_count if displayed_count > 0 else 0

            print(f"[{idx}/{total}] '{label}' -> {nrows} rows (page reported {displayed_count})")
            return out_path, nrows

        except Exception as exc:
            if attempt < retries:
                print(
                    f"[{idx}/{total}] '{label}' attempt {attempt}/{retries} failed: {exc}; "
                    f"retrying in {backoff}s"
                )
                time.sleep(backoff)
                backoff *= 2
            else:
                print(f"[{idx}/{total}] '{label}' FAILED after {retries} attempts: {exc}")
                return None, -1

    return None, -1


# ---------------------------------------------------------------------------
# Full-registry scrape (date-paginated)
# ---------------------------------------------------------------------------

def scrape_full(
    year_from: int,
    year_to: int,
    out_path: Path,
    scratch_dir: Path,
    headless: bool = True,
    cap_threshold: int = CAP_THRESHOLD,
) -> pd.DataFrame | None:
    """Scrape the full PACTR registry using year-by-year date windows.

    For any year window that returns >= cap_threshold rows, automatically
    subdivides into 12 monthly sub-windows to avoid server caps.

    State is checkpointed to {scratch_dir}/state.json after each window so
    the scrape can be resumed if interrupted.

    Returns merged, deduplicated DataFrame mapped to ICTRP schema.
    """
    from playwright.sync_api import sync_playwright

    state_path = scratch_dir / "state.json"
    raw_dir = scratch_dir / "raw_full"
    raw_dir.mkdir(parents=True, exist_ok=True)

    # Build the list of top-level year windows
    year_windows = iter_year_windows(year_from, year_to)
    total_top = len(year_windows)

    # Load existing state (resume support)
    completed_labels: dict[str, str] = {}  # label -> csv_path (str) or "" for 0-result
    if state_path.exists():
        try:
            completed_labels = json.loads(state_path.read_text(encoding="utf-8"))
            print(f"Resuming from state: {len(completed_labels)} windows already done")
        except Exception as exc:
            print(f"WARNING: Could not load state file {state_path}: {exc} — starting fresh")

    # Collect all (label, start, end) windows to process, expanding subdivisions
    # We build the full plan first so we know the total count for progress display
    plan: list[tuple[str, str, str]] = []  # (label, start, end)
    for start, end in year_windows:
        year = int(start.split("/")[-1])
        plan.append((f"{year}", start, end))

    # Gather all raw CSV paths (newly scraped + previously done)
    raw_paths: list[Path] = []

    # Re-collect already-completed paths
    for label, csv_path_str in completed_labels.items():
        if csv_path_str and Path(csv_path_str).exists():
            raw_paths.append(Path(csv_path_str))

    per_year_counts: dict[str, int] = {}

    def _fresh_page(pw):
        """Launch a fresh browser+context+page for one window.

        Re-using a single long-lived page across many windows causes PACTR
        session degradation (cookie/storage accumulation, network-layer stalls)
        that leads to silent hangs on the `expect_download` step after ~10 windows.
        Launching fresh per window costs ~5s but eliminates the stall entirely.

        Browser args are tuned for Windows headless stability:
        - --disable-gpu: prevents GPU process launch (crashes in headless on some Windows configs)
        - --no-sandbox: required in some CI / restricted environments
        - --disable-dev-shm-usage: prevents /dev/shm exhaustion (Linux-specific but harmless on Windows)
        - --single-process: eliminates renderer subprocess that can crash on OOM; trades
          isolation for stability. Use only in headless mode.
        """
        args = [
            "--disable-gpu",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-setuid-sandbox",
        ]
        browser = pw.chromium.launch(headless=headless, args=args)
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page = ctx.new_page()
        return browser, ctx, page

    idx = 0
    total = len(plan)  # will grow if we expand years into months

    with sync_playwright() as pw:
        for label, start, end in plan:
            if label in completed_labels:
                print(f"[skip] '{label}' already completed")
                continue

            idx += 1
            browser, ctx, page = _fresh_page(pw)
            try:
                csv_path, nrows = _scrape_date_window(
                    page, start, end, label, scratch_dir, idx, total,
                )
            finally:
                try:
                    browser.close()
                except Exception:
                    pass

            if nrows == -1:
                # Hard failure — save state and continue
                print(f"WARNING: '{label}' failed permanently; skipping")
                completed_labels[label] = ""
                state_path.write_text(
                    json.dumps(completed_labels, indent=2), encoding="utf-8"
                )
                # Politeness pause
                time.sleep(7)
                continue

            if nrows >= cap_threshold:
                # Cap-likely: subdivide this year into monthly windows
                year_int = int(start.split("/")[-1])
                print(
                    f"  -> {nrows} rows >= cap_threshold={cap_threshold}; "
                    f"subdividing {year_int} into monthly windows"
                )
                month_windows = iter_month_windows(year_int)
                # Mark the year-level entry as "subdivided" (no CSV)
                completed_labels[label] = "__subdivided__"
                state_path.write_text(
                    json.dumps(completed_labels, indent=2), encoding="utf-8"
                )
                # Discard the year-level CSV
                if csv_path and csv_path.exists():
                    csv_path.unlink(missing_ok=True)

                for m_idx, (m_start, m_end) in enumerate(month_windows, start=1):
                    month_label = f"{year_int}-m{m_idx:02d}"
                    if month_label in completed_labels:
                        print(f"[skip] '{month_label}' already completed")
                        continue
                    total += 1
                    idx += 1
                    m_browser, m_ctx, m_page = _fresh_page(pw)
                    try:
                        m_path, m_nrows = _scrape_date_window(
                            m_page, m_start, m_end, month_label,
                            scratch_dir, idx, total,
                        )
                    finally:
                        try:
                            m_browser.close()
                        except Exception:
                            pass
                    if m_nrows >= 0 and m_path is not None:
                        raw_paths.append(m_path)
                        per_year_counts[month_label] = m_nrows
                    completed_labels[month_label] = str(m_path) if m_path else ""
                    state_path.write_text(
                        json.dumps(completed_labels, indent=2), encoding="utf-8"
                    )
                    if m_idx < len(month_windows):
                        time.sleep(7)

                per_year_counts[label] = nrows  # record pre-subdivision count
            else:
                # Normal window
                if csv_path is not None:
                    raw_paths.append(csv_path)
                    per_year_counts[label] = nrows
                else:
                    per_year_counts[label] = 0
                completed_labels[label] = str(csv_path) if csv_path else ""
                state_path.write_text(
                    json.dumps(completed_labels, indent=2), encoding="utf-8"
                )

            # Politeness pause between top-level windows
            time.sleep(7)

        # Note: each browser is already closed in its own try/finally block above.
        # No shared browser reference remains here.

    # Summary table
    print("\n--- Per-year row counts ---")
    for lbl in sorted(per_year_counts):
        print(f"  {lbl}: {per_year_counts[lbl]}")
    print("---------------------------\n")

    if not raw_paths:
        print("ERROR: No CSV files downloaded. Aborting.")
        return None

    # Merge all downloaded CSVs
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

    # Deduplicate on TrialNumber
    before_dedup = len(merged)
    merged = merged.drop_duplicates(subset=["TrialNumber"], keep="first")
    print(f"Merged: {before_dedup} total rows -> {len(merged)} unique trials after dedup")

    # Map to ICTRP schema
    ictrp = map_pactr_to_ictrp(merged)

    missing_cols = [c for c in REQUIRED_COLUMNS if c not in ictrp.columns]
    if missing_cols:
        print(f"ERROR: Missing required columns after mapping: {missing_cols}")
        return None

    # Write output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ictrp.to_csv(out_path, index=False, encoding="utf-8")
    print(f"Written: {out_path}")

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
        "--mode",
        choices=["condition", "full"],
        default="condition",
        help=(
            "Scrape mode: 'condition' (10-query keyword search, default) or "
            "'full' (date-paginated full-registry 2008-2026)"
        ),
    )
    # Output path — default depends on mode; resolved in main()
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help=(
            f"Output CSV path. "
            f"Defaults: condition={DEFAULT_OUT}, full={DEFAULT_FULL_OUT}"
        ),
    )
    # condition-mode options
    parser.add_argument(
        "--queries",
        type=str,
        default=None,
        help="Comma-separated list of search queries (default: all 10 conditions)",
    )
    # full-mode options
    parser.add_argument(
        "--year-from",
        type=int,
        default=2008,
        help="First year (inclusive) for full-mode date windows (default: 2008)",
    )
    parser.add_argument(
        "--year-to",
        type=int,
        default=2026,
        help="Last year (inclusive) for full-mode date windows (default: 2026)",
    )
    parser.add_argument(
        "--cap-threshold",
        type=int,
        default=CAP_THRESHOLD,
        help=(
            f"Row-count threshold above which a year window is subdivided into "
            f"monthly windows (default: {CAP_THRESHOLD})"
        ),
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
        help="Directory for per-query/window raw CSV files",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    _fix_stdout()
    args = _parse_args(argv)

    if args.mode == "full":
        out_path = args.out if args.out is not None else DEFAULT_FULL_OUT
        print(f"Mode: full (date-paginated, {args.year_from}–{args.year_to})")
        print(f"Output: {out_path}")
        print(f"Headless: {args.headless}")
        print(f"Cap threshold: {args.cap_threshold}")
        print()
        result = scrape_full(
            year_from=args.year_from,
            year_to=args.year_to,
            out_path=out_path,
            scratch_dir=args.scratch_dir,
            headless=args.headless,
            cap_threshold=args.cap_threshold,
        )
    else:
        # condition mode (backward-compat default)
        out_path = args.out if args.out is not None else DEFAULT_OUT
        queries = DEFAULT_QUERIES
        if args.queries:
            queries = [q.strip() for q in args.queries.split(",") if q.strip()]

        print(f"Mode: condition ({len(queries)} keyword queries)")
        print(f"Queries: {queries}")
        print(f"Output: {out_path}")
        print(f"Headless: {args.headless}")
        print()

        result = scrape_all(
            queries=queries,
            out_path=out_path,
            scratch_dir=args.scratch_dir,
            headless=args.headless,
        )

    return 0 if result is not None else 1


if __name__ == "__main__":
    sys.exit(main())
