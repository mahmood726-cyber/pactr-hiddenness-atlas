"""Bug 1 smoke test: `python -m pilots.run_all` must expose a CLI entry point.

The test invokes the module as a subprocess with paths.toml pointing at
the fixture snapshot so it can run offline.  Europe PMC is NOT reachable
in CI — the test only verifies the entry point wires up and exits cleanly
when a valid paths.toml is provided.

Because the subprocess uses the fixture snapshot (50 rows, no real network),
this is safe and fast.  The test does NOT use monkeypatch (subprocess
boundary) — instead it creates a temporary paths.toml pointing at fixtures.
"""
from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
ROOT = Path(__file__).parent.parent


@pytest.mark.integration
def test_run_all_main_block_exits_cleanly(tmp_path):
    """python -m pilots.run_all with a valid paths.toml must exit 0."""
    cache = tmp_path / "cache"
    cache.mkdir()
    toml = tmp_path / "paths.toml"
    toml.write_text(
        textwrap.dedent(f"""\
            [ictrp]
            snapshot = "{(FIXTURES / 'ictrp_50trial.csv').as_posix()}"

            [pairwise70]
            index = "{(FIXTURES / 'pairwise70_micro.parquet').as_posix()}"

            [cdsr]
            string_index = "{(FIXTURES / 'cdsr_string_micro.sqlite').as_posix()}"

            [europe_pmc]
            cache_dir = "{cache.as_posix()}"
        """),
        encoding="utf-8",
    )
    import os
    env_patch = {"PYTHONPATH": os.pathsep.join([str(ROOT / "src"), str(ROOT)])}
    env = {**os.environ, **env_patch}

    result = subprocess.run(
        [sys.executable, "-m", "pilots.run_all", "--paths", str(toml),
         "--out-dir", str(tmp_path / "out"), "--n-bootstrap", "50"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=env,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"pilots.run_all exited {result.returncode}:\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )
    assert "atlas.csv" in result.stdout or (tmp_path / "out" / "atlas.csv").exists()
