"""Shared pytest fixtures and deterministic-seed plumbing."""
from __future__ import annotations

import os
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _seed_random():
    random.seed(20260503)
    try:
        import numpy as np
        np.random.seed(20260503)
    except ImportError:
        pass


@pytest.fixture
def fixture_path():
    return FIXTURES


@pytest.fixture
def utf8_stdout(capsys):
    """Force UTF-8 on stdout per portfolio cp1252 lesson."""
    import io
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace"
    )
    yield
