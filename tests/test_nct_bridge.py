import pytest

from pactr_atlas.nct_bridge import extract_nct, is_tier0_invisible


def test_extract_nct_clean():
    assert extract_nct("NCT04123456") == "NCT04123456"


def test_extract_nct_in_secondary_id_string():
    assert extract_nct("WHO ICTRP: NCT04123456; ISRCTN12345") == "NCT04123456"


def test_extract_nct_rejects_non_nct_prefix():
    # NCTH is not NCT
    assert extract_nct("NCTH04123456") is None


def test_extract_nct_rejects_short_digits():
    assert extract_nct("NCT0412") is None


def test_extract_nct_handles_empty_and_none():
    assert extract_nct("") is None
    assert extract_nct(None) is None


def test_is_tier0_invisible_when_no_nct():
    assert is_tier0_invisible(None) is True
    assert is_tier0_invisible("") is True
    assert is_tier0_invisible("NCT04123456") is False
