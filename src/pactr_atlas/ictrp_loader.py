"""ICTRP weekly export loader. Filters to PACTR-only and validates schema."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS: tuple[str, ...] = (
    "TrialID", "Source Register", "Conditions", "Secondary IDs",
    "Results URL", "Date registered", "Countries", "Primary Sponsor",
    "Recruitment Status",
)

_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


class SchemaDriftError(ValueError):
    pass


def load_pactr_snapshot(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, low_memory=False)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise SchemaDriftError(
            f"ICTRP snapshot at {path} missing required columns: {missing}"
        )
    pactr = df[df["Source Register"].str.upper() == "PACTR"].copy()
    pactr.reset_index(drop=True, inplace=True)
    return pactr


def write_snapshot_metadata(
    snapshot: Path,
    out_meta: Path,
    *,
    source_url: str,
    n_pactr_trials: int | None = None,
) -> dict:
    """Write JSON metadata for the ICTRP snapshot to *out_meta*.

    Extended fields (Bug 3):
    - ``snapshot_date``: derived from a ``YYYY-MM-DD`` pattern in the filename
      stem; falls back to ``fetched_at[:10]`` when the filename carries no date.
    - ``n_pactr_trials``: caller-supplied count of PACTR rows after filtering.
    """
    raw = snapshot.read_bytes()
    fetched_at = datetime.now(timezone.utc).isoformat()
    m = _DATE_RE.search(snapshot.stem)
    snapshot_date = m.group(1) if m else fetched_at[:10]
    meta: dict = {
        "snapshot_path": str(snapshot),
        "source_url": source_url,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
        "fetched_at": fetched_at,
        "snapshot_date": snapshot_date,
    }
    if n_pactr_trials is not None:
        meta["n_pactr_trials"] = n_pactr_trials
    out_meta.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta
