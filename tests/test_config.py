from pathlib import Path

import pytest

from pactr_atlas.config import Paths, load_paths, ConfigError


def test_load_paths_resolves_all_keys(tmp_path):
    cfg = tmp_path / "paths.toml"
    cfg.write_text("""
[ictrp]
snapshot = "{}/ictrp.csv"

[pairwise70]
index = "{}/pairwise70.parquet"

[cdsr]
string_index = "{}/cdsr.sqlite"

[europe_pmc]
cache_dir = "{}/cache"
""".format(*([str(tmp_path).replace("\\", "/")] * 4)), encoding="utf-8")
    (tmp_path / "ictrp.csv").touch()
    (tmp_path / "pairwise70.parquet").touch()
    (tmp_path / "cdsr.sqlite").touch()

    paths = load_paths(cfg)
    assert isinstance(paths, Paths)
    assert paths.ictrp_snapshot.exists()
    assert paths.pairwise70_index.exists()
    assert paths.cdsr_string_index.exists()
    assert paths.europe_pmc_cache_dir.exists()  # auto-created


def test_load_paths_missing_file_fails_closed(tmp_path):
    cfg = tmp_path / "paths.toml"
    cfg.write_text('[ictrp]\nsnapshot = "/nonexistent/x.csv"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="missing required key"):
        load_paths(cfg)
