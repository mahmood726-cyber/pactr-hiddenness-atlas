"""Tests for scripts/fill_paper_placeholders.py."""
import json
from pathlib import Path

import pandas as pd
import pytest

from scripts.fill_paper_placeholders import (
    MissingInputError,
    compute_replacements,
    fill_template,
    parse_prereg_commit_sha,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_FULL_SHA = "c9cd90b3355974254232a4b67ce2920bc39d6e0d"


def _atlas() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "condition": ["a", "b", "c"],
            "n_registered": [100, 200, 50],
            "n_gate3": [10, 30, 5],
            "n_gate3_given_gate2": [8, 25, 4],
            "n_tier0_invisible": [40, 60, 20],
            "pct_gate0_to_gate3": [0.10, 0.15, 0.10],
        }
    )


def _meta() -> dict:
    return {
        "snapshot_date": "2026-05-04",
        "sha256": "abcdef0123456789",
        "n_pactr_trials": 500,
    }


# ---------------------------------------------------------------------------
# compute_replacements
# ---------------------------------------------------------------------------


def test_compute_replacements_correct_arithmetic():
    r = compute_replacements(_atlas(), _meta(), _FULL_SHA)
    # n_reg_total = 350; n_gate3_total = 45; 100*45/350 = 12.857... -> 12.9
    assert r["{{HEADLINE_PCT}}"] == "12.9"
    # tier0 = 120; 100*120/350 = 34.285... -> 34.3
    assert r["{{TIER0_PCT}}"] == "34.3"
    # ensemble_delta = 100*(45-37)/350 = 2.285... -> 2.3
    assert r["{{ENSEMBLE_DELTA}}"] == "2.3"
    # min/max per-condition pct_gate0_to_gate3: 0.10 and 0.15 -> 10.0 and 15.0
    assert r["{{MIN_PCT}}"] == "10.0"
    assert r["{{MAX_PCT}}"] == "15.0"
    assert r["{{N_REGISTERED}}"] == "350"
    assert r["{{N_PACTR}}"] == "500"
    assert r["{{N_DROPPED}}"] == "150"
    assert r["{{SNAPSHOT_DATE}}"] == "2026-05-04"
    assert r["{{SNAPSHOT_SHA8}}"] == "abcdef01"
    assert r["{{TRIALSCOUT_BASELINE}}"] == "63.6"
    assert r["{{PREREG_COMMIT_SHORT}}"] == "c9cd90b"


def test_compute_replacements_zero_registered_raises():
    df = pd.DataFrame(
        {
            "condition": ["x"],
            "n_registered": [0],
            "n_gate3": [0],
            "n_gate3_given_gate2": [0],
            "n_tier0_invisible": [0],
            "pct_gate0_to_gate3": [0.0],
        }
    )
    with pytest.raises(ValueError, match="zero registered"):
        compute_replacements(df, _meta(), _FULL_SHA)


def test_compute_replacements_sha_truncated_to_7():
    r = compute_replacements(_atlas(), _meta(), "abcdef1234567890")
    assert r["{{PREREG_COMMIT_SHORT}}"] == "abcdef1"


def test_compute_replacements_sha8_uses_first_8_of_metadata_sha():
    meta = dict(_meta())
    meta["sha256"] = "1234567890abcdef"
    r = compute_replacements(_atlas(), meta, _FULL_SHA)
    assert r["{{SNAPSHOT_SHA8}}"] == "12345678"


# ---------------------------------------------------------------------------
# parse_prereg_commit_sha
# ---------------------------------------------------------------------------


def test_parse_prereg_commit_sha_extracts(tmp_path: Path):
    m = tmp_path / "manifest.txt"
    m.write_text(
        "PACTR header\n========\n\ntag : prereg-v0.0.1\n"
        "commit SHA  : c9cd90b3355974254232a4b67ce2920bc39d6e0d\n"
        "date : 2026-05-03\n",
        encoding="utf-8",
    )
    assert parse_prereg_commit_sha(m) == "c9cd90b3355974254232a4b67ce2920bc39d6e0d"


def test_parse_prereg_commit_sha_missing_raises(tmp_path: Path):
    m = tmp_path / "manifest.txt"
    m.write_text("no commit field here\n", encoding="utf-8")
    with pytest.raises(MissingInputError, match="commit SHA"):
        parse_prereg_commit_sha(m)


# ---------------------------------------------------------------------------
# fill_template
# ---------------------------------------------------------------------------


def test_fill_template_replaces_and_validates_no_leftover(tmp_path: Path):
    tpl = tmp_path / "body.md"
    tpl.write_text(
        "Of {{N_REGISTERED}} trials, {{HEADLINE_PCT}}% reached gate 3.",
        encoding="utf-8",
    )
    result = fill_template(
        tpl, {"{{N_REGISTERED}}": "350", "{{HEADLINE_PCT}}": "12.9"}
    )
    assert result == "Of 350 trials, 12.9% reached gate 3."


def test_fill_template_unfilled_placeholder_raises(tmp_path: Path):
    tpl = tmp_path / "body.md"
    tpl.write_text(
        "Of {{N_REGISTERED}} trials, {{MISSING_KEY}} is unfilled.",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="unfilled placeholders"):
        fill_template(tpl, {"{{N_REGISTERED}}": "350"})


def test_fill_template_no_placeholders_returns_text_unchanged(tmp_path: Path):
    tpl = tmp_path / "body.md"
    tpl.write_text("Plain text, no placeholders.", encoding="utf-8")
    result = fill_template(tpl, {})
    assert result == "Plain text, no placeholders."
