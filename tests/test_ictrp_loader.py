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
