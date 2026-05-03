import pandas as pd

from pactr_atlas.results_posting import gate1_results_posted, gate1_all


def test_gate1_returns_true_for_non_null_url():
    assert gate1_results_posted("https://pactr.samrc.ac.za/results/X") is True


def test_gate1_returns_false_for_blank_or_none():
    assert gate1_results_posted("") is False
    assert gate1_results_posted(None) is False
    assert gate1_results_posted("   ") is False


def test_gate1_all_marks_each_row():
    df = pd.DataFrame({
        "Results URL": [
            "https://x.org/results", "", None, "   https://y.org/results  ",
        ],
    })
    out = gate1_all(df)
    assert list(out["gate1_results_posted"]) == [True, False, False, True]
