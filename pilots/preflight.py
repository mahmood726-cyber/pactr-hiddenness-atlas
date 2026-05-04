"""Fail-closed preflight verifier.

Per spec §5: implementation cannot begin until every check passes.
Any failure halts the entire pipeline; downstream module imports
will raise PreflightFailed if invoked without a green preflight.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable

import pandas as pd

from pactr_atlas.config import Paths
from pactr_atlas.conditions_table import CONDITIONS_10

CONDITIONS: tuple[str, ...] = tuple(CONDITIONS_10.keys())


class PreflightFailed(RuntimeError):
    pass


def check_paths_resolve(paths: Paths) -> None:
    for name in ("ictrp_snapshot", "pairwise70_index", "cdsr_string_index"):
        p: Path = getattr(paths, name)
        if not p.exists():
            raise PreflightFailed(f"path {name} does not resolve: {p}")
    paths.europe_pmc_cache_dir.mkdir(parents=True, exist_ok=True)


def check_ictrp_filter_size(ictrp_csv: Path, min_rows: int = 5000) -> int:
    df = pd.read_csv(ictrp_csv, dtype=str, low_memory=False)
    pactr = df[df["Source Register"].str.upper() == "PACTR"]
    n = len(pactr)
    if n < min_rows:
        raise PreflightFailed(
            f"ICTRP PACTR filter returned {n} rows, below minimum {min_rows}"
        )
    return n


def check_condition_denominators(ictrp_csv: Path, min_per_condition: int = 20) -> dict[str, int]:
    df = pd.read_csv(ictrp_csv, dtype=str, low_memory=False)
    pactr = df[df["Source Register"].str.upper() == "PACTR"]
    cond_lc = pactr["Conditions"].fillna("").str.lower()
    counts: dict[str, int] = {}
    for c in CONDITIONS:
        n = int(cond_lc.str.contains(c, regex=False).sum())
        counts[c] = n
        if n < min_per_condition:
            raise PreflightFailed(
                f"condition {c!r}: {n} trials, below minimum {min_per_condition}"
            )
    return counts


def run(paths: Paths) -> None:
    check_paths_resolve(paths)
    check_ictrp_filter_size(paths.ictrp_snapshot)
    check_condition_denominators(paths.ictrp_snapshot)


if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    from pactr_atlas.config import load_paths
    from pactr_atlas.ictrp_loader import write_snapshot_metadata
    cfg = Path("paths.toml")
    if not cfg.exists():
        print(f"FAIL: {cfg} does not exist; copy paths.toml.example and edit")
        raise SystemExit(2)
    try:
        paths = load_paths(cfg)
        run(paths)
        # Bug 2 fix: write snapshot metadata after preflight passes so the
        # orchestrator and fill_paper_placeholders can read snapshot_date +
        # n_pactr_trials.  We re-read and count here because check_ictrp_filter_size
        # already validated the minimum; the count is cheap to recompute.
        import pandas as pd
        _df = pd.read_csv(paths.ictrp_snapshot, dtype=str, low_memory=False)
        _n_pactr = int((_df["Source Register"].str.upper() == "PACTR").sum())
        _meta_dir = Path("data/snapshots")
        _meta_dir.mkdir(parents=True, exist_ok=True)
        write_snapshot_metadata(
            paths.ictrp_snapshot,
            _meta_dir / "ictrp_metadata.json",
            source_url="https://trialsearch.who.int/",
            n_pactr_trials=_n_pactr,
        )
        print(f"snapshot metadata written to {_meta_dir / 'ictrp_metadata.json'}")
    except PreflightFailed as exc:
        print(f"PREFLIGHT_FAILED: {exc}")
        raise SystemExit(1)
    print("preflight OK")
