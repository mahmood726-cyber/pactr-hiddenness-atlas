"""Tests for scripts/scrape_pactr.py — no network calls; fixture-based only."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

# Import the mapping function and helpers directly from the script
import importlib.util
import sys

# Load the script as a module (it lives in scripts/, not a package)
_SCRIPT = Path(__file__).parent.parent / "scripts" / "scrape_pactr.py"
_spec = importlib.util.spec_from_file_location("scrape_pactr", _SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["scrape_pactr"] = _mod
_spec.loader.exec_module(_mod)

map_pactr_to_ictrp = _mod.map_pactr_to_ictrp
_parse_pactr_date = _mod._parse_pactr_date
_first_non_empty_date = _mod._first_non_empty_date
REQUIRED_COLUMNS = _mod.REQUIRED_COLUMNS
iter_year_windows = _mod.iter_year_windows
iter_month_windows = _mod.iter_month_windows

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Test 1: basic mapping — 2-row mock DataFrame
# ---------------------------------------------------------------------------

def test_map_pactr_to_ictrp_basic():
    """2-row mock: output has all 9 ICTRP required columns in correct format."""
    raw = pd.DataFrame({
        "TrialNumber": ["PACTR2008060000861040", "PACTR2008060000892906"],
        "Diseases": ["Infections and Infestations", "Infections and Infestations"],
        "PublicTitle": ["TB treatment trial A", "TB pericarditis trial B"],
        "OfficialScientificTitle": ["Scientific A", "Scientific B"],
        "Description": ["Description A", "Description B"],
        "Secondary IDs": [pd.NA, pd.NA],
        "ReportingResultURLHyperlinks": ["http://example.com/results1", ""],
        "PublicationURL": ["", "http://example.com/pub2"],
        "EthicsApprovalDate": ["03/17/2008", "07/31/2007"],
        "ActualStartDate": ["8/15/2008 12:00:00 AM", "1/1/2009 12:00:00 AM"],
        "AnticipatedStartDate": ["7/26/2007 12:00:00 AM", "1/1/2009 12:00:00 AM"],
        "RecruitmentCentreCountry": [
            "Zimbabwe. Zimbabwe. South Africa. Zimbabwe. South Africa. Botswana. South Africa. Zambia",
            "Mozambique. South Africa. India. Nigeria. South Africa",
        ],
        "SponsorName": [
            "St Georges Hospital Medical School. St Georges Hospital Medical School",
            "University of Cape Town. University of Cape Town",
        ],
        "RecruitmentStatus": ["Completed", "Completed"],
    })

    out = map_pactr_to_ictrp(raw)

    # All 9 required columns present
    for col in REQUIRED_COLUMNS:
        assert col in out.columns, f"Missing required column: {col}"

    # TrialID matches TrialNumber
    assert list(out["TrialID"]) == ["PACTR2008060000861040", "PACTR2008060000892906"]

    # Source Register is constant "PACTR"
    assert list(out["Source Register"]) == ["PACTR", "PACTR"]

    # Date registered: uses EthicsApprovalDate (first fallback)
    assert out["Date registered"].iloc[0] == "2008-03-17"
    assert out["Date registered"].iloc[1] == "2007-07-31"

    # Countries: deduplicated, semicolon-joined
    countries_0 = out["Countries"].iloc[0]
    assert ";" in countries_0, f"Expected semicolon-separated countries, got: {countries_0}"
    assert "Zimbabwe" in countries_0
    assert "South Africa" in countries_0
    # No duplicate "Zimbabwe" — deduplication should occur
    parts_0 = [c.strip() for c in countries_0.split(";")]
    assert parts_0.count("Zimbabwe") == 1, "Duplicate countries not deduplicated"

    countries_1 = out["Countries"].iloc[1]
    assert "Mozambique" in countries_1
    assert "Nigeria" in countries_1

    # Primary Sponsor: first value only
    assert out["Primary Sponsor"].iloc[0] == "St Georges Hospital Medical School"
    assert out["Primary Sponsor"].iloc[1] == "University of Cape Town"

    # Recruitment Status: direct
    assert list(out["Recruitment Status"]) == ["Completed", "Completed"]

    # Results URL: row 0 gets ReportingResultURLHyperlinks; row 1 falls back to PublicationURL
    assert out["Results URL"].iloc[0] == "http://example.com/results1"
    assert out["Results URL"].iloc[1] == "http://example.com/pub2"


# ---------------------------------------------------------------------------
# Test 2: empty Secondary IDs — no "nan" strings
# ---------------------------------------------------------------------------

def test_map_pactr_to_ictrp_handles_empty_secondary_ids():
    """Empty Secondary IDs should produce empty string, not 'nan'."""
    raw = pd.DataFrame({
        "TrialNumber": ["PACTR2008060000861040"],
        "Diseases": ["Test"],
        "PublicTitle": ["Title"],
        "OfficialScientificTitle": ["Sci"],
        "Description": ["Desc"],
        "Secondary IDs": [pd.NA],  # NaN / missing
        "ReportingResultURLHyperlinks": [pd.NA],
        "PublicationURL": [pd.NA],
        "EthicsApprovalDate": ["03/17/2008"],
        "ActualStartDate": [""],
        "AnticipatedStartDate": [""],
        "RecruitmentCentreCountry": ["South Africa"],
        "SponsorName": ["University of Cape Town"],
        "RecruitmentStatus": ["Completed"],
    })

    out = map_pactr_to_ictrp(raw)

    sec_id = out["Secondary IDs"].iloc[0]
    assert sec_id == "", f"Expected empty string, got: {repr(sec_id)}"
    assert sec_id != "nan", "Secondary IDs must not contain literal 'nan'"
    assert sec_id is not None, "Secondary IDs must not be None"


# ---------------------------------------------------------------------------
# Test 3: first-non-null date fallback logic
# ---------------------------------------------------------------------------

def test_map_pactr_to_ictrp_first_non_null_date():
    """EthicsApprovalDate empty -> falls back to ActualStartDate -> ISO YYYY-MM-DD."""
    raw = pd.DataFrame({
        "TrialNumber": ["PACTR_TEST_001"],
        "Diseases": ["Test"],
        "PublicTitle": ["Title"],
        "OfficialScientificTitle": ["Sci"],
        "Description": ["Desc"],
        "Secondary IDs": [""],
        "ReportingResultURLHyperlinks": [""],
        "PublicationURL": [""],
        "EthicsApprovalDate": [""],        # empty — skip
        "ActualStartDate": ["3/15/2020 12:00:00 AM"],  # <- should pick this
        "AnticipatedStartDate": ["1/1/2019 12:00:00 AM"],
        "RecruitmentCentreCountry": ["Uganda"],
        "SponsorName": ["Test Sponsor"],
        "RecruitmentStatus": ["Recruiting"],
    })

    out = map_pactr_to_ictrp(raw)

    assert out["Date registered"].iloc[0] == "2020-03-15", (
        f"Expected 2020-03-15, got: {out['Date registered'].iloc[0]}"
    )


# ---------------------------------------------------------------------------
# Test 4: fixture-based — real PACTR CSV shape passes through mapping
# ---------------------------------------------------------------------------

def test_map_pactr_to_ictrp_on_real_fixture():
    """Load the 2-row pactr_micro.csv fixture and verify schema passes mapping."""
    fixture = FIXTURES / "pactr_micro.csv"
    assert fixture.exists(), f"Fixture missing: {fixture}"

    raw = pd.read_csv(fixture, dtype=str, low_memory=False, on_bad_lines="warn")
    assert len(raw) == 2, f"Expected 2 rows in fixture, got {len(raw)}"

    out = map_pactr_to_ictrp(raw)

    # All required columns present
    for col in REQUIRED_COLUMNS:
        assert col in out.columns, f"Missing required column after fixture mapping: {col}"

    # TrialIDs match expected PACTR identifiers
    assert out["TrialID"].iloc[0] == "PACTR2008060000861040"
    assert out["TrialID"].iloc[1] == "PACTR2008060000892906"

    # Source Register all PACTR
    assert (out["Source Register"] == "PACTR").all()

    # Date registered parsed to ISO (ethics dates: 2008-03-17, 2007-07-31)
    assert out["Date registered"].iloc[0] == "2008-03-17"
    assert out["Date registered"].iloc[1] == "2007-07-31"

    # Countries: semicolon-separated (not period-separated)
    assert "." not in out["Countries"].iloc[0].replace("St.", ""), (
        "Countries should be semicolon-separated, not period-separated"
    )

    # Secondary IDs: no literal "nan"
    for i, val in enumerate(out["Secondary IDs"]):
        assert val != "nan", f"Row {i}: Secondary IDs contains literal 'nan'"


# ---------------------------------------------------------------------------
# Test 5: sentinel date values (1/1/1900) are skipped
# ---------------------------------------------------------------------------

def test_parse_pactr_date_rejects_sentinel_1900():
    """PACTR uses 1/1/1900 12:00:00 AM as a null sentinel — must return empty string."""
    result = _parse_pactr_date("1/1/1900 12:00:00 AM")
    assert result == "", f"Expected empty string for 1900 sentinel, got: {repr(result)}"


def test_parse_pactr_date_valid():
    """Valid PACTR date parses to ISO format."""
    assert _parse_pactr_date("03/17/2008") == "2008-03-17"
    assert _parse_pactr_date("8/15/2008 12:00:00 AM") == "2008-08-15"
    assert _parse_pactr_date("3/15/2020 12:00:00 AM") == "2020-03-15"
    assert _parse_pactr_date("") == ""
    assert _parse_pactr_date("  ") == ""


# ---------------------------------------------------------------------------
# Test 7: iter_year_windows — covers 2008..2026 inclusive (19 windows)
# ---------------------------------------------------------------------------

def test_year_windows_2008_to_2026_inclusive():
    """Date-window iterator must cover 2008-01-01 through 2026-12-31."""
    windows = iter_year_windows(2008, 2026)
    assert len(windows) == 19, f"Expected 19 year windows, got {len(windows)}"
    assert windows[0] == ("01/01/2008", "12/31/2008"), (
        f"First window wrong: {windows[0]}"
    )
    assert windows[-1] == ("01/01/2026", "12/31/2026"), (
        f"Last window wrong: {windows[-1]}"
    )
    # All windows have correct year in both start and end
    for i, (start, end) in enumerate(windows):
        year = 2008 + i
        assert start == f"01/01/{year}", f"Window {i} start wrong: {start}"
        assert end == f"12/31/{year}", f"Window {i} end wrong: {end}"


def test_year_windows_single_year():
    """Single-year range returns exactly 1 window."""
    windows = iter_year_windows(2015, 2015)
    assert len(windows) == 1
    assert windows[0] == ("01/01/2015", "12/31/2015")


def test_year_windows_inclusive_both_ends():
    """Both year_from and year_to are included."""
    windows = iter_year_windows(2020, 2022)
    assert len(windows) == 3
    assert windows[0][0] == "01/01/2020"
    assert windows[2][1] == "12/31/2022"


# ---------------------------------------------------------------------------
# Test 8: iter_month_windows — 12 windows per year, correct day counts
# ---------------------------------------------------------------------------

def test_month_windows_non_leap_year():
    """Non-leap year 2023: February ends on 28."""
    windows = iter_month_windows(2023)
    assert len(windows) == 12, f"Expected 12 monthly windows, got {len(windows)}"
    # January
    assert windows[0] == ("01/01/2023", "01/31/2023")
    # February (non-leap)
    assert windows[1] == ("02/01/2023", "02/28/2023")
    # December
    assert windows[11] == ("12/01/2023", "12/31/2023")


def test_month_windows_leap_year():
    """Leap year 2024: February ends on 29."""
    windows = iter_month_windows(2024)
    assert len(windows) == 12
    assert windows[1] == ("02/01/2024", "02/29/2024"), (
        f"Feb 2024 should end on 29, got: {windows[1]}"
    )


def test_month_windows_all_months_covered():
    """All 12 months are represented in a monthly subdivision."""
    windows = iter_month_windows(2020)
    months_start = [w[0].split("/")[0] for w in windows]
    assert months_start == [f"{m:02d}" for m in range(1, 13)], (
        f"Expected months 01-12, got: {months_start}"
    )
