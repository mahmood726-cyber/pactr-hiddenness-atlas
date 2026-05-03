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


def test_load_paths_missing_toml_file_fails_closed(tmp_path):
    cfg = tmp_path / "does_not_exist.toml"
    with pytest.raises(ConfigError, match="paths.toml not found"):
        load_paths(cfg)


def test_load_paths_missing_section_fails_closed(tmp_path):
    cfg = tmp_path / "paths.toml"
    # No required sections present at all — branch 2 (key absent) must fire
    # for the FIRST required section iterated (_REQUIRED[0] = ictrp.snapshot).
    cfg.write_text('[unrelated]\nfoo = "bar"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="missing required key"):
        load_paths(cfg)


def test_load_paths_referenced_file_missing_fails_closed(tmp_path):
    cfg = tmp_path / "paths.toml"
    cfg.write_text("""
[ictrp]
snapshot = "{tp}/ictrp.csv"

[pairwise70]
index = "{tp}/pairwise70.parquet"

[cdsr]
string_index = "{tp}/cdsr.sqlite"

[europe_pmc]
cache_dir = "{tp}/cache"
""".format(tp=str(tmp_path).replace("\\", "/")), encoding="utf-8")
    # All keys present, but the referenced files do not exist on disk.
    with pytest.raises(ConfigError, match="referenced path missing"):
        load_paths(cfg)
