"""Per-condition gate counts + clustered bootstrap CI.

Cluster = country_lead, per spec §9 ordering rule 4. CI undefined when
the cluster count < 3.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from pactr_atlas.conditions_table import CONDITIONS_10


class EmptyFunnelInput(ValueError):
    pass


def clustered_bootstrap_ci(
    df: pd.DataFrame, col: str, cluster_col: str, *,
    n: int = 1000, seed: int = 20260503, alpha: float = 0.05,
) -> tuple[float | None, float | None]:
    clusters = df[cluster_col].unique()
    if len(clusters) < 3:
        return None, None
    rng = np.random.default_rng(seed)
    samples = []
    for _ in range(n):
        picked = rng.choice(clusters, size=len(clusters), replace=True)
        sub = pd.concat([df[df[cluster_col] == c] for c in picked])
        if sub.empty:
            continue
        samples.append(sub[col].mean())
    if not samples:
        return None, None
    arr = np.array(samples)
    lo = float(np.quantile(arr, alpha / 2))
    hi = float(np.quantile(arr, 1 - alpha / 2))
    return lo, hi


def compute_funnel(df: pd.DataFrame, *, n_bootstrap: int = 1000) -> pd.DataFrame:
    if df.empty:
        raise EmptyFunnelInput("compute_funnel called on empty DataFrame")
    rows = []
    for cond in CONDITIONS_10:
        sub = df[df["condition"] == cond]
        if sub.empty:
            continue
        n_reg = int(sub["gate0_registered"].sum())
        n_g1 = int(sub["gate1_results_posted"].sum())
        n_g2 = int(sub["gate2_published"].sum())
        n_g3 = int(sub["gate3_in_cochrane"].sum())
        n_t0 = int(sub["tier0_invisible"].sum())
        pct = n_g3 / n_reg if n_reg else float("nan")
        ci_lo, ci_hi = clustered_bootstrap_ci(
            sub, "gate3_in_cochrane", "country_lead", n=n_bootstrap,
        )
        rows.append({
            "condition": cond, "n_registered": n_reg,
            "n_gate1": n_g1, "n_gate2": n_g2, "n_gate3": n_g3,
            "pct_gate0_to_gate3": pct,
            "pct_gate0_to_gate3_ci_lo": ci_lo,
            "pct_gate0_to_gate3_ci_hi": ci_hi,
            "n_tier0_invisible": n_t0,
        })
    return pd.DataFrame(rows)
