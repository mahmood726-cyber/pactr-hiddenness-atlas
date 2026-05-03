"""Path configuration loader. Single source of truth for external paths.

No source file under src/, tests/, or pilots/ may contain a hardcoded
absolute path. Every external reference resolves through Paths.
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Paths:
    ictrp_snapshot: Path
    pairwise70_index: Path
    cdsr_string_index: Path
    europe_pmc_cache_dir: Path


_REQUIRED = (
    ("ictrp", "snapshot", "ictrp_snapshot"),
    ("pairwise70", "index", "pairwise70_index"),
    ("cdsr", "string_index", "cdsr_string_index"),
    ("europe_pmc", "cache_dir", "europe_pmc_cache_dir"),
)


def load_paths(toml_path: Path) -> Paths:
    if not toml_path.exists():
        raise ConfigError(f"paths.toml not found at {toml_path}")
    with toml_path.open("rb") as fh:
        raw = tomllib.load(fh)
    fields: dict[str, Path] = {}
    for section, key, dest in _REQUIRED:
        sub = raw.get(section)
        if not isinstance(sub, dict) or key not in sub:
            raise ConfigError(f"missing required key [{section}].{key}")
        p = Path(sub[key]).expanduser()
        if dest == "europe_pmc_cache_dir":
            p.mkdir(parents=True, exist_ok=True)
        elif not p.exists():
            raise ConfigError(f"missing required key [{section}].{key}: {p} not found")
        fields[dest] = p
    return Paths(**fields)
