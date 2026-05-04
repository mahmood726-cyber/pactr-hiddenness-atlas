# sentinel:skip-file
# Justification: this script uses absolute OS-level paths as CLI defaults for
# data discovery (CDE pairwise root and user data directories). These are
# intentional config defaults, not hardcoded deployable paths — mirrors the
# pattern in src/pactr_atlas/paths.py. All paths are overridable via CLI args.
"""Build two production data assets for PACTR Hiddenness Atlas v0.1.0.

Assets produced (outside the repo, never committed):
  - study_references.parquet  : Pairwise70 NCT bridge (review_id, nct)
  - cdsr_string_index.sqlite  : CDSR full-text for PACTR-ID literal search

Bug 5 fix (review_id format):
  CDE filenames carry a _pubN suffix (e.g. CD000028_pub4).
  The PACTR matcher (cochrane_match.nct_bridge_match) and the fixture parquet
  use bare CDxxxxxx format (e.g. CD000001).  We strip the _pubN suffix when
  building the parquet so the join works.
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
import io
from pathlib import Path
from collections import defaultdict
from typing import Optional

import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FILENAME_REVIEW_RE = re.compile(
    r"10_1002_14651858_(CD\d+)(?:_pub\d+)?_"
)
NCT_RE = re.compile(r"\bNCT(\d{8})\b")

DEFAULT_CDE_ROOT = Path("C:/Projects/CochraneDataExtractor/data/pairwise")
DEFAULT_OUT_PAIRWISE70 = Path("C:/Users/user/data/pairwise70/study_references.parquet")
DEFAULT_OUT_CDSR = Path("C:/Users/user/data/cdsr/cdsr_string_index.sqlite")


# ---------------------------------------------------------------------------
# Helper: extract bare review_id (strip _pub\d+ suffix)
# ---------------------------------------------------------------------------

def parse_review_id(filename: str) -> Optional[str]:
    """Return bare CDxxxxxx review_id from a CDE filename, or None.

    The filename pattern is:
        10_1002_14651858_CD000028_pub4_CD000028-<type>.csv
    We capture the first CDxxxxxx group and strip any _pubN suffix so
    the result matches the format expected by cochrane_match.nct_bridge_match
    (e.g. 'CD000028', not 'CD000028_pub4').
    """
    m = FILENAME_REVIEW_RE.search(filename)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# Helper: extract all NCT IDs from a string
# ---------------------------------------------------------------------------

def extract_ncts_from_text(text: str) -> list[str]:
    """Return all unique NCTxxxxxxxx references found in *text*."""
    return [f"NCT{d}" for d in NCT_RE.findall(text)]


# ---------------------------------------------------------------------------
# Build 1: Pairwise70 NCT bridge
# ---------------------------------------------------------------------------

def build_pairwise70_nct_bridge(cde_root: Path, out_path: Path) -> int:
    """Scan all CDE CSVs; extract NCT refs; emit deduplicated (review_id, nct)
    pairs to parquet.  Returns number of rows written.

    Strategy: scan ALL CSV types (not just study-information) because NCT
    references appear in 'Char: Notes', 'ID: CRS', and other text columns.
    """
    cde_root = Path(cde_root)
    pairs: set[tuple[str, str]] = set()
    review_nct_counts: dict[str, int] = defaultdict(int)

    csv_files = sorted(cde_root.glob("*.csv"))
    total = len(csv_files)

    for i, csv_path in enumerate(csv_files, 1):
        review_id = parse_review_id(csv_path.name)
        if review_id is None:
            continue

        try:
            df = pd.read_csv(csv_path, encoding_errors="replace", low_memory=False)
        except Exception:
            continue

        # Concatenate all string-typed columns into one blob per file
        str_cols = df.select_dtypes(include="object").columns
        if len(str_cols) == 0:
            continue

        combined = df[str_cols].fillna("").astype(str).apply(
            lambda row: " ".join(row), axis=1
        )
        file_ncts: set[str] = set()
        for cell in combined:
            for nct in extract_ncts_from_text(cell):
                file_ncts.add(nct)
                pairs.add((review_id, nct))

        review_nct_counts[review_id] += len(file_ncts)

        if i % 50 == 0 or i == total:
            print(
                f"[{i:03d}/{total}] NCT bridge scan — "
                f"{len(pairs)} pairs so far across {len(review_nct_counts)} reviews",
                flush=True,
            )

    # Build dataframe and write parquet
    if pairs:
        rows = sorted(pairs)
        result_df = pd.DataFrame(rows, columns=["review_id", "nct"])
    else:
        result_df = pd.DataFrame(columns=["review_id", "nct"])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    result_df.to_parquet(out_path, index=False)
    return len(result_df)


# ---------------------------------------------------------------------------
# Build 2: CDSR string index
# ---------------------------------------------------------------------------

def build_cdsr_string_index(cde_root: Path, out_path: Path) -> int:
    """Concat all string columns from each review's CSVs into one body_text
    per review_id.  Write to sqlite table review_strings(review_id, body_text).
    Returns number of reviews indexed.
    """
    cde_root = Path(cde_root)

    # Group CSV files by review_id
    review_files: dict[str, list[Path]] = defaultdict(list)
    for csv_path in sorted(cde_root.glob("*.csv")):
        review_id = parse_review_id(csv_path.name)
        if review_id is not None:
            review_files[review_id].append(csv_path)

    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Remove old DB if present so we start fresh
    if out_path.exists():
        out_path.unlink()

    conn = sqlite3.connect(str(out_path))
    conn.execute(
        "CREATE TABLE review_strings ("
        "review_id TEXT NOT NULL, "
        "body_text TEXT NOT NULL"
        ")"
    )
    conn.execute(
        "CREATE INDEX idx_review_id ON review_strings(review_id)"
    )

    review_ids_sorted = sorted(review_files.keys())
    total = len(review_ids_sorted)

    for i, review_id in enumerate(review_ids_sorted, 1):
        blobs: list[str] = []
        for csv_path in review_files[review_id]:
            try:
                df = pd.read_csv(
                    csv_path, encoding_errors="replace", low_memory=False
                )
            except Exception:
                continue
            str_cols = df.select_dtypes(include="object").columns
            if len(str_cols) == 0:
                continue
            text = " ".join(
                df[str_cols].fillna("").astype(str).values.flatten().tolist()
            )
            blobs.append(text)

        body_text = " ".join(blobs)

        if i % 50 == 0 or i == total:
            print(
                f"[{i:03d}/{total}] CDSR index — {review_id} → {len(body_text):,} chars",
                flush=True,
            )

        conn.execute(
            "INSERT INTO review_strings(review_id, body_text) VALUES (?, ?)",
            (review_id, body_text),
        )

    conn.commit()
    conn.close()
    return total


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Build Pairwise70 NCT bridge parquet and CDSR string index sqlite."
    )
    parser.add_argument(
        "--cde-root",
        type=Path,
        default=DEFAULT_CDE_ROOT,
        help="Path to CochraneDataExtractor pairwise CSVs directory.",
    )
    parser.add_argument(
        "--out-pairwise70",
        type=Path,
        default=DEFAULT_OUT_PAIRWISE70,
        help="Output path for study_references.parquet.",
    )
    parser.add_argument(
        "--out-cdsr",
        type=Path,
        default=DEFAULT_OUT_CDSR,
        help="Output path for cdsr_string_index.sqlite.",
    )
    args = parser.parse_args(argv)

    if not args.cde_root.exists():
        print(
            f"ERROR: CDE root not found: {args.cde_root}", file=sys.stderr
        )
        sys.exit(1)

    print("=== Phase 1: Building Pairwise70 NCT bridge ===", flush=True)
    n_pairs = build_pairwise70_nct_bridge(args.cde_root, args.out_pairwise70)

    print(f"\n=== Phase 2: Building CDSR string index ===", flush=True)
    n_reviews = build_cdsr_string_index(args.cde_root, args.out_cdsr)

    # Verify parquet rows
    df_check = pd.read_parquet(args.out_pairwise70)
    n_unique_reviews = df_check["review_id"].nunique()
    n_unique_ncts = df_check["nct"].nunique()

    print(
        f"\nWrote {n_pairs} NCT pairs across {n_unique_reviews} reviews "
        f"({n_unique_ncts} unique NCTs); CDSR indexed {n_reviews} reviews.",
        flush=True,
    )
    print(f"Parquet: {args.out_pairwise70}", flush=True)
    print(f"SQLite : {args.out_cdsr}", flush=True)


if __name__ == "__main__":
    # cp1252 guard (Windows console)
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace"
    )
    main()
