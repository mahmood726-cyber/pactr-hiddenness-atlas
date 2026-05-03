"""ICTRP weekly export loader. Filters to PACTR-only and validates schema."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS: tuple[str, ...] = (
    "TrialID", "Source Register", "Conditions", "Secondary IDs",
    "Results URL", "Date registered", "Countries", "Primary Sponsor",
    "Recruitment Status",
)


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
    snapshot: Path, out_meta: Path, *, source_url: str
) -> dict:
    raw = snapshot.read_bytes()
    meta = {
        "snapshot_path": str(snapshot),
        "source_url": source_url,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    out_meta.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta
