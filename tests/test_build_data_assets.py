"""Tests for scripts/build_data_assets.py.

Uses tmp_path (pytest built-in) and synthesized CSVs — no CDE dependency.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pandas as pd
import pytest

# Bring scripts/ onto sys.path so we can import the script as a module
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from build_data_assets import (  # noqa: E402
    extract_ncts_from_text,
    parse_review_id,
    build_pairwise70_nct_bridge,
    build_cdsr_string_index,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_csv(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _cde_filename(review_id_with_pub: str, csv_type: str) -> str:
    """Construct a CDE-style filename."""
    cd = review_id_with_pub.split("_")[0]
    return f"10_1002_14651858_{review_id_with_pub}_{cd}-{csv_type}.csv"


# ---------------------------------------------------------------------------
# Test 1: extract_ncts_from_text handles multiple NCTs and deduplication
# ---------------------------------------------------------------------------

def test_extract_nct_from_cell_handles_multiple_nct():
    """A cell containing two distinct NCT IDs returns both; duplicates collapsed."""
    text = (
        "Study registration: NCT12345678. "
        "See also NCT87654321 for follow-up. "
        "NCT12345678 was previously published."
    )
    result = extract_ncts_from_text(text)
    # The function itself doesn't deduplicate (caller does); check both present
    assert "NCT12345678" in result
    assert "NCT87654321" in result
    # No spurious entries
    assert all(r.startswith("NCT") and len(r) == 11 for r in result)
    # Confirm the duplicate appears (deduplication is the caller's job)
    assert result.count("NCT12345678") == 2


# ---------------------------------------------------------------------------
# Test 2: build_pairwise70_nct_bridge on micro fixture directory
# ---------------------------------------------------------------------------

def test_build_pairwise70_nct_bridge_on_micro_fixture(tmp_path):
    """Two synthetic CDE CSVs with known NCTs → correct (review_id, nct) rows."""
    # Review 1: CD000042 with 2 NCTs in study-information
    r1_file = tmp_path / _cde_filename("CD000042_pub2", "study-information")
    _write_csv(
        r1_file,
        "Study,Char: Notes\n"
        "Smith 2001,Study registration: NCT12345678. Funded by NIHR.\n"
        "Jones 2005,NCT87654321 registered in Africa.\n"
    )

    # Review 2: CD000099 with 1 NCT
    r2_file = tmp_path / _cde_filename("CD000099_pub1", "study-information")
    _write_csv(
        r2_file,
        "Study,Char: Notes\n"
        "Garcia 2015,No registration.\n"
        "Patel 2018,NCT11112222 African trial.\n"
    )

    out_parquet = tmp_path / "study_references.parquet"
    n = build_pairwise70_nct_bridge(tmp_path, out_parquet)

    assert out_parquet.exists()
    df = pd.read_parquet(out_parquet)

    # Correct columns and dtypes
    assert list(df.columns) == ["review_id", "nct"]
    assert df["review_id"].dtype == object
    assert df["nct"].dtype == object

    # Correct review_id format: bare CDxxxxxx, no _pub\d+ suffix
    assert set(df["review_id"].unique()) == {"CD000042", "CD000099"}

    # Correct NCTs
    assert set(df["nct"].tolist()) == {"NCT12345678", "NCT87654321", "NCT11112222"}

    # Review CD000042 should have 2 NCTs
    assert len(df[df["review_id"] == "CD000042"]) == 2

    # Review CD000099 should have 1 NCT
    assert len(df[df["review_id"] == "CD000099"]) == 1

    # Row count matches return value
    assert n == len(df)


# ---------------------------------------------------------------------------
# Test 3: build_cdsr_string_index on micro fixture directory
# ---------------------------------------------------------------------------

def test_build_cdsr_string_index_on_micro_fixture(tmp_path):
    """Synthetic CDE CSVs → sqlite with one row per review, body_text containing
    all source string fields.
    """
    # Review 1: 2 CSV files
    r1_study = tmp_path / _cde_filename("CD000042_pub2", "study-information")
    _write_csv(
        r1_study,
        "Study,Char: Notes\n"
        "Smith 2001,PACTR202012000000001 in Uganda\n"
        "Jones 2005,No registration\n"
    )
    r1_rob = tmp_path / _cde_filename("CD000042_pub2", "risk-of-bias")
    _write_csv(
        r1_rob,
        "Study,Judgement\n"
        "Smith 2001,Low\n"
        "Jones 2005,High\n"
    )

    # Review 2: 1 CSV file
    r2_study = tmp_path / _cde_filename("CD000099_pub1", "study-information")
    _write_csv(
        r2_study,
        "Study,Char: Notes\n"
        "Garcia 2015,Exercise intervention\n"
    )

    out_sqlite = tmp_path / "cdsr_string_index.sqlite"
    n = build_cdsr_string_index(tmp_path, out_sqlite)

    assert out_sqlite.exists()
    conn = sqlite3.connect(str(out_sqlite))
    rows = conn.execute(
        "SELECT review_id, body_text FROM review_strings ORDER BY review_id"
    ).fetchall()
    conn.close()

    # One row per review
    assert n == 2
    assert len(rows) == 2

    review_ids = [r[0] for r in rows]
    body_texts = [r[1] for r in rows]

    # Correct bare review_id format
    assert "CD000042" in review_ids
    assert "CD000099" in review_ids

    # body_text for CD000042 should contain content from both CSVs
    cd42_text = body_texts[review_ids.index("CD000042")]
    assert "PACTR202012000000001" in cd42_text
    assert "Smith 2001" in cd42_text
    assert "Low" in cd42_text  # from risk-of-bias CSV

    # body_text for CD000099 should contain its content
    cd99_text = body_texts[review_ids.index("CD000099")]
    assert "Garcia 2015" in cd99_text
    assert "Exercise intervention" in cd99_text


# ---------------------------------------------------------------------------
# Test 4: review_id format matches PACTR matcher expectation
# ---------------------------------------------------------------------------

def test_review_id_format_matches_pactr_matcher(fixture_path):
    """parse_review_id must return bare CDxxxxxx format — identical to the
    format used in the pairwise70_micro.parquet fixture that nct_bridge_match
    queries against.

    This confirms Bug 5 fix: the _pubN suffix is stripped so the join
    between our built parquet and cochrane_match.nct_bridge_match works.
    """
    fixture_parquet = fixture_path / "pairwise70_micro.parquet"
    df = pd.read_parquet(fixture_parquet)
    fixture_review_ids = set(df["review_id"].astype(str).tolist())

    # Verify the fixture uses bare CDxxxxxx (no _pub suffix)
    for rid in fixture_review_ids:
        assert "_pub" not in rid, (
            f"Fixture review_id '{rid}' contains _pub suffix — "
            "fixture format assumption violated."
        )

    # Verify parse_review_id strips _pub\d+ suffix correctly
    sample_filenames = [
        ("10_1002_14651858_CD000028_pub4_CD000028-study-information.csv", "CD000028"),
        ("10_1002_14651858_CD000143_pub2_CD000143-data-rows.csv", "CD000143"),
        ("10_1002_14651858_CD000214_pub3_CD000214-risk-of-bias.csv", "CD000214"),
        # Edge case: no pub suffix (hypothetical)
        ("10_1002_14651858_CD000999_CD000999-study-information.csv", "CD000999"),
    ]
    for filename, expected_id in sample_filenames:
        result = parse_review_id(filename)
        assert result == expected_id, (
            f"parse_review_id('{filename}') = '{result}', expected '{expected_id}'"
        )

    # Verify non-matching filename returns None
    assert parse_review_id("not_a_cde_file.csv") is None
    assert parse_review_id("") is None
