# tests/test_dashboard_builder.py
from pathlib import Path

import pandas as pd

from pactr_atlas.dashboard_builder import build_dashboard


def test_build_dashboard_writes_index_html(tmp_path):
    atlas = pd.DataFrame({
        "condition": ["tuberculosis","hiv","cholera","snakebite"],
        "n_registered": [200, 150, 80, 25],
        "n_gate1": [100, 75, 40, 5],
        "n_gate2": [60, 50, 20, 2],
        "n_gate3": [30, 20, 5, 1],
        "pct_gate0_to_gate3": [0.15, 0.13, 0.06, 0.04],
        "pct_gate0_to_gate3_ci_lo": [0.10, 0.08, 0.02, None],
        "pct_gate0_to_gate3_ci_hi": [0.20, 0.18, 0.10, None],
        "n_gate3_given_gate2": [20, 15, 4, 1],
        "pct_gate0_to_gate3_given_gate2": [0.10, 0.10, 0.05, 0.04],
        "n_tier0_invisible": [80, 50, 30, 20],
    })
    out = tmp_path / "dashboard"
    build_dashboard(atlas, out)
    idx = out / "index.html"
    assert idx.exists()
    text = idx.read_text(encoding="utf-8")
    # Per spec: inline-SVG only, NO external CDN
    assert "cdn." not in text.lower()
    assert "https://" not in text or "github.com" in text
    # Headline metric for each condition appears
    for c in ["tuberculosis","hiv","cholera","snakebite"]:
        assert c in text.lower()
    # Sankey ribbons exist
    assert "<svg" in text
    assert "Sankey" in text or "sankey" in text or "funnel" in text.lower()


def test_build_dashboard_no_external_dependency(tmp_path):
    atlas = pd.DataFrame({
        "condition": ["tuberculosis"], "n_registered": [10],
        "n_gate1": [5], "n_gate2": [3], "n_gate3": [1],
        "pct_gate0_to_gate3": [0.1],
        "pct_gate0_to_gate3_ci_lo": [None], "pct_gate0_to_gate3_ci_hi": [None],
        "n_gate3_given_gate2": [1],
        "pct_gate0_to_gate3_given_gate2": [0.1],
        "n_tier0_invisible": [4],
    })
    build_dashboard(atlas, tmp_path)
    text = (tmp_path / "index.html").read_text(encoding="utf-8")
    forbidden = ["d3.js", "plotly", "chart.js", "highcharts", "jquery", "<link rel"]
    for token in forbidden:
        assert token.lower() not in text.lower(), f"{token} leaked into dashboard"
