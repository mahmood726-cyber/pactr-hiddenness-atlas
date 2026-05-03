"""Cochrane-MA match: 3-strategy ensemble.

Primary:    NCT-bridge      (this task)
Sensitivity: PACTR-ID literal (Task 10)
Validation: Pairwise70-restricted manual audit cohort (Task 11)
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass(frozen=True)
class MatchVerdict:
    in_cochrane: bool
    method: str
    review_id: Optional[str] = None
    review_ids_all: Optional[tuple[str, ...]] = None
    ensemble_disagree: bool = False


def nct_bridge_match(nct: Optional[str], pairwise70_index: pd.DataFrame) -> MatchVerdict:
    if not nct:
        return MatchVerdict(in_cochrane=False, method="none")
    hits = pairwise70_index[pairwise70_index["nct"] == nct]
    if hits.empty:
        return MatchVerdict(in_cochrane=False, method="none")
    review_ids = tuple(sorted(set(hits["review_id"].astype(str))))
    return MatchVerdict(
        in_cochrane=True, method="nct_bridge",
        review_id=review_ids[0], review_ids_all=review_ids,
    )


def pactr_id_literal_match(
    pactr_id: str, cdsr_conn: sqlite3.Connection
) -> MatchVerdict:
    if not pactr_id:
        return MatchVerdict(in_cochrane=False, method="none")
    cur = cdsr_conn.execute(
        "SELECT review_id FROM review_strings WHERE body_text LIKE ? LIMIT 5",
        (f"%{pactr_id}%",),
    )
    review_ids = tuple(sorted({row[0] for row in cur.fetchall()}))
    if not review_ids:
        return MatchVerdict(in_cochrane=False, method="none")
    return MatchVerdict(
        in_cochrane=True, method="pactr_id_literal",
        review_id=review_ids[0], review_ids_all=review_ids,
    )


def match_trial(
    *,
    nct: Optional[str],
    pactr_id: str,
    pairwise70_index: pd.DataFrame,
    cdsr_conn: sqlite3.Connection,
) -> MatchVerdict:
    """Ensemble combiner: NCT-bridge primary + PACTR-ID literal sensitivity.

    Algorithm (semantic-locked, not a simple xor):
      1. Primary (NCT bridge) hits -> authoritative; literal-miss is expected
         for a lower-recall sensitivity check; ensemble_disagree=False.
      2. nct is None -> tier0_invisible; primary couldn't run, so the literal
         becomes the verdict if it hits; ensemble_disagree=False.
      3. NCT present, primary missed, literal hit -> genuine disagreement;
         primary verdict (False) wins per spec; ensemble_disagree=True so
         atlas.csv can surface this as a sensitivity column.
      4. Both missed -> method="none", no disagreement.
    """
    primary = nct_bridge_match(nct, pairwise70_index)
    secondary = pactr_id_literal_match(pactr_id, cdsr_conn)

    # Case 1: primary (NCT bridge) hits — authoritative, literal-miss is
    # expected behaviour for a lower-recall sensitivity check.
    if primary.in_cochrane:
        return MatchVerdict(
            in_cochrane=True, method="nct_bridge",
            review_id=primary.review_id, review_ids_all=primary.review_ids_all,
            ensemble_disagree=False,
        )

    # Case 2: tier0_invisible (no NCT) — primary couldn't check.
    # Literal becomes the verdict when it hits.
    if not nct:
        if secondary.in_cochrane:
            return MatchVerdict(
                in_cochrane=True, method="pactr_id_literal",
                review_id=secondary.review_id,
                review_ids_all=secondary.review_ids_all,
                ensemble_disagree=False,
            )
        return MatchVerdict(in_cochrane=False, method="none", ensemble_disagree=False)

    # Case 3: NCT present, primary missed, literal hit — genuine disagreement.
    # Primary verdict (False) wins per spec; flag ensemble_disagree=True so
    # atlas.csv can surface this as a sensitivity column.
    if secondary.in_cochrane:
        return MatchVerdict(
            in_cochrane=False, method="nct_bridge",
            review_id=None, review_ids_all=None,
            ensemble_disagree=True,
        )

    # Case 4: both missed.
    return MatchVerdict(in_cochrane=False, method="none", ensemble_disagree=False)
