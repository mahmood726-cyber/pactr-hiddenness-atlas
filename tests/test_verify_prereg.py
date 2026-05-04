"""Tests for scripts/verify_prereg.py — sha256 anchor re-checker.

Plan defect fix (Task 19): manifest sha values must be real 64-char hexdigests.
The regex _FILE_RE requires [0-9a-f]{64}; 6-char stubs like 'abc123' do not
match, so test_parse_manifest_extracts_sha_lines uses 'a'*64 and 'b'*64.
"""
import hashlib
from pathlib import Path

import pytest

from scripts.verify_prereg import (
    verify_sha256,
    parse_manifest,
    ManifestMismatch,
)


def test_verify_sha256_match(tmp_path):
    f = tmp_path / "x.md"
    f.write_text("hello", encoding="utf-8")
    expected = hashlib.sha256(b"hello").hexdigest()
    assert verify_sha256(f, expected) is True


def test_verify_sha256_mismatch_raises(tmp_path):
    f = tmp_path / "x.md"
    f.write_text("hello", encoding="utf-8")
    with pytest.raises(ManifestMismatch):
        verify_sha256(f, "0" * 64)


def test_parse_manifest_extracts_sha_lines(tmp_path):
    """Plan defect fix: manifest sha values must be real 64-char hexdigests."""
    m = tmp_path / "manifest.txt"
    sha_x = "a" * 64
    sha_y = "b" * 64
    m.write_text(
        f"File: docs/x.md\n  sha256: {sha_x}\n"
        f"File: docs/y.md\n  sha256: {sha_y}\n",
        encoding="utf-8",
    )
    parsed = parse_manifest(m)
    assert parsed == {"docs/x.md": sha_x, "docs/y.md": sha_y}
