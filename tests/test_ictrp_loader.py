import hashlib
import json
from pathlib import Path
import pandas as pd
import pytest

from pactr_atlas.ictrp_loader import (
    load_pactr_snapshot,
    write_snapshot_metadata,
    SchemaDriftError,
    REQUIRED_COLUMNS,
)


def test_load_pactr_snapshot_filters_to_pactr_only(fixture_path):
    df = load_pactr_snapshot(fixture_path / "ictrp_50trial.csv")
    assert len(df) == 50
    assert set(df["Source Register"].str.upper().unique()) == {"PACTR"}


def test_load_pactr_snapshot_keeps_required_columns(fixture_path):
    df = load_pactr_snapshot(fixture_path / "ictrp_50trial.csv")
    for col in REQUIRED_COLUMNS:
        assert col in df.columns


def test_load_pactr_snapshot_schema_drift_raises(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("TrialID,Source Register\nPACTR000,PACTR\n", encoding="utf-8")
    with pytest.raises(SchemaDriftError, match="missing"):
        load_pactr_snapshot(bad)


def test_write_snapshot_metadata(tmp_path, fixture_path):
    src = fixture_path / "ictrp_50trial.csv"
    meta = write_snapshot_metadata(src, tmp_path / "meta.json", source_url="file://test")
    assert meta["sha256"] == hashlib.sha256(src.read_bytes()).hexdigest()
    on_disk = json.loads((tmp_path / "meta.json").read_text(encoding="utf-8"))
    assert on_disk["sha256"] == meta["sha256"]
    assert on_disk["source_url"] == "file://test"


# ---------------------------------------------------------------------------
# Bug 3: snapshot_date derivation + n_pactr_trials in write_snapshot_metadata
# ---------------------------------------------------------------------------

def test_write_snapshot_metadata_date_from_filename(tmp_path):
    """snapshot_date is derived from a YYYY-MM-DD pattern in the filename."""
    src = tmp_path / "ictrp_export_2026-05-04.csv"
    src.write_text("TrialID,Source Register\n", encoding="utf-8")
    meta = write_snapshot_metadata(
        src, tmp_path / "meta.json",
        source_url="https://trialsearch.who.int/",
        n_pactr_trials=5234,
    )
    assert meta["snapshot_date"] == "2026-05-04"
    assert meta["n_pactr_trials"] == 5234
    on_disk = json.loads((tmp_path / "meta.json").read_text(encoding="utf-8"))
    assert on_disk["snapshot_date"] == "2026-05-04"
    assert on_disk["n_pactr_trials"] == 5234


def test_write_snapshot_metadata_date_fallback_to_fetched_at(tmp_path):
    """When filename has no date, snapshot_date falls back to fetched_at[:10]."""
    src = tmp_path / "ictrp_50trial.csv"
    src.write_text("TrialID,Source Register\n", encoding="utf-8")
    meta = write_snapshot_metadata(
        src, tmp_path / "meta.json",
        source_url="https://trialsearch.who.int/",
        n_pactr_trials=42,
    )
    # fetched_at is an ISO timestamp like "2026-05-04T..."
    expected_date = meta["fetched_at"][:10]
    assert meta["snapshot_date"] == expected_date
    assert meta["n_pactr_trials"] == 42
