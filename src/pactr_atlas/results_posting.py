"""Gate 1: results posted on PACTR.

ICTRP "Results URL" non-null is a LOWER BOUND on results-posting; some
PACTR results pages exist without a Results URL in ICTRP. v0.2 will
escalate to PACTR scrape for fidelity. v0.1.0 reports this as a
documented lower bound in extraction_audit.md.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd


def gate1_results_posted(results_url: Optional[str]) -> bool:
    if not results_url:
        return False
    return bool(str(results_url).strip())


def gate1_all(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["gate1_results_posted"] = out["Results URL"].map(gate1_results_posted)
    return out
