from pathlib import Path
import sqlite3

from pactr_atlas.cochrane_match import pactr_id_literal_match


def test_literal_hit(fixture_path):
    db = sqlite3.connect(fixture_path / "cdsr_string_micro.sqlite")
    v = pactr_id_literal_match("PACTR202012000000001", db)
    db.close()
    assert v.in_cochrane is True
    assert v.method == "pactr_id_literal"
    assert v.review_id == "CD000010"


def test_literal_miss(fixture_path):
    db = sqlite3.connect(fixture_path / "cdsr_string_micro.sqlite")
    v = pactr_id_literal_match("PACTR202099999999999", db)
    db.close()
    assert v.in_cochrane is False
    assert v.method == "none"


def test_literal_handles_blank(fixture_path):
    db = sqlite3.connect(fixture_path / "cdsr_string_micro.sqlite")
    v = pactr_id_literal_match("", db)
    db.close()
    assert v.in_cochrane is False
