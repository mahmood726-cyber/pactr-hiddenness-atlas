"""Map a trial row to one of the 10 conditions, or drop it.

Trials matching 0 or >=2 conditions are dropped (returning None) with
a method tag so the orchestrator can record them. Multi-match drops
are preserved in a separate audit CSV by the caller.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from pactr_atlas.conditions_table import CONDITIONS_10


def _matches_one(text_lc: str, condition_key: str) -> tuple[bool, str]:
    table = CONDITIONS_10[condition_key]
    for kw in table["keywords_strict"]:
        if kw in text_lc:
            return True, "keyword_strict"
    for kw in table["keywords_fuzzy"]:
        if kw in text_lc:
            return True, "keyword_fuzzy"
    return False, ""


def assign_condition(row: pd.Series) -> tuple[Optional[str], str]:
    text = str(row.get("Conditions", "") or "").lower()
    hits: list[tuple[str, str]] = []
    for cond in CONDITIONS_10:
        ok, method = _matches_one(text, cond)
        if ok:
            hits.append((cond, method))
    if len(hits) == 0:
        return None, "no_match"
    if len(hits) >= 2:
        return None, "multi_condition"
    cond, method = hits[0]
    return cond, method


def assign_all(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (matched_with_condition, dropped_with_reason)."""
    rows: list[dict] = []
    drops: list[dict] = []
    for _, r in df.iterrows():
        cond, method = assign_condition(r)
        rec = r.to_dict()
        if cond is None:
            rec["drop_reason"] = method
            drops.append(rec)
        else:
            rec["condition"] = cond
            rec["condition_match_method"] = method
            rows.append(rec)
    matched = pd.DataFrame(rows) if rows else pd.DataFrame()
    dropped = pd.DataFrame(drops) if drops else pd.DataFrame()
    return matched, dropped
