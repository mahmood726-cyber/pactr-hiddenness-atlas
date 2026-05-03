import pandas as pd
import pytest

from pactr_atlas.condition_matcher import assign_condition, assign_all
from pactr_atlas.conditions_table import CONDITIONS_10


def _row(text: str) -> pd.Series:
    return pd.Series({"Conditions": text})


def test_assign_condition_strict_keyword_tb():
    out = assign_condition(_row("Tuberculosis"))
    assert out == ("tuberculosis", "keyword_strict")


def test_assign_condition_unknown_returns_none():
    out = assign_condition(_row("diabetes mellitus type 2"))
    assert out == (None, "no_match")


def test_assign_condition_drops_when_two_match():
    out = assign_condition(_row("HIV and tuberculosis co-infection"))
    assert out == (None, "multi_condition")


def test_conditions_table_has_exactly_ten():
    assert len(CONDITIONS_10) == 10
    expected = {
        "tuberculosis", "hiv", "sickle cell", "schistosomiasis",
        "maternal sepsis", "neonatal sepsis", "snakebite",
        "soil-transmitted helminths", "cervical cancer", "cholera",
    }
    assert set(CONDITIONS_10.keys()) == expected


def test_assign_all_drops_multi_and_unknown():
    df = pd.DataFrame({"Conditions": [
        "Tuberculosis", "HIV", "diabetes",
        "HIV and tuberculosis", "neonatal sepsis",
    ]})
    matched, dropped = assign_all(df)
    assert len(matched) == 3
    assert set(matched["condition"]) == {"tuberculosis", "hiv", "neonatal sepsis"}
    assert len(dropped) == 2


def test_conditions_table_keys_match_preflight_canonical():
    """Drift guard: conditions_table.CONDITIONS_10 keys must equal pilots.preflight.CONDITIONS."""
    from pilots.preflight import CONDITIONS as _CANONICAL
    assert tuple(sorted(CONDITIONS_10.keys())) == tuple(sorted(_CANONICAL))
