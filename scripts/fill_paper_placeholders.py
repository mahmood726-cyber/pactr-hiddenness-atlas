# sentinel:skip-file — this file defines {{...}} patterns as dict-key string
# literals that will later fill templates; they are intentional data, not
# unfilled template tokens (P1-unpopulated-placeholder false-positive).
"""Fill {{...}} placeholders in v0.1.0 paper templates from live atlas data.

Outputs `*.filled` beside each template; the original templates are read-only.
After review, the user copies the .filled files over the originals to commit.

Usage:
    python scripts/fill_paper_placeholders.py
    python scripts/fill_paper_placeholders.py --atlas data/processed/atlas.csv \
        --metadata data/snapshots/ictrp_metadata.json \
        --manifest .preregistration_commit.txt \
        --templates-dir e156-submission

Windows users: run from the repo root in Git Bash or a venv-activated cmd/PowerShell.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Mapping

import pandas as pd

TRIALSCOUT_BASELINE = 63.6  # literal % from validation_gates.py::TRIALSCOUT_BASELINE


class MissingInputError(FileNotFoundError):
    pass


def compute_replacements(
    atlas: pd.DataFrame,
    metadata: Mapping[str, object],
    prereg_commit_sha: str,
) -> dict[str, str]:
    """Return a dict of placeholder -> replacement-string from live atlas data."""
    n_reg_total = int(atlas["n_registered"].sum())
    if n_reg_total == 0:
        raise ValueError("atlas reports zero registered trials — cannot compute pcts")
    n_pactr = int(metadata["n_pactr_trials"])
    return {
        "{{N_REGISTERED}}": str(n_reg_total),
        "{{N_PACTR}}": str(n_pactr),
        "{{N_DROPPED}}": str(n_pactr - n_reg_total),
        "{{HEADLINE_PCT}}": f"{100 * atlas['n_gate3'].sum() / n_reg_total:.1f}",
        "{{TIER0_PCT}}": f"{100 * atlas['n_tier0_invisible'].sum() / n_reg_total:.1f}",
        "{{ENSEMBLE_DELTA}}": (
            f"{100 * (atlas['n_gate3'].sum() - atlas['n_gate3_given_gate2'].sum()) / n_reg_total:.1f}"
        ),
        "{{MIN_PCT}}": f"{100 * atlas['pct_gate0_to_gate3'].min():.1f}",
        "{{MAX_PCT}}": f"{100 * atlas['pct_gate0_to_gate3'].max():.1f}",
        "{{SNAPSHOT_DATE}}": str(metadata["snapshot_date"]),
        "{{SNAPSHOT_SHA8}}": str(metadata["sha256"])[:8],
        "{{TRIALSCOUT_BASELINE}}": str(TRIALSCOUT_BASELINE),
        "{{PREREG_COMMIT_SHORT}}": prereg_commit_sha[:7],
    }


def parse_prereg_commit_sha(manifest_path: Path) -> str:
    """Extract the full commit SHA from the 'commit SHA : <hex>' line in the manifest."""
    text = manifest_path.read_text(encoding="utf-8")
    m = re.search(r"commit SHA\s*:\s*([0-9a-f]+)", text)
    if not m:
        raise MissingInputError(
            f"no 'commit SHA:' line found in {manifest_path}"
        )
    return m.group(1)


def fill_template(template_path: Path, replacements: dict[str, str]) -> str:
    """Read template, apply replacements, and verify no {{...}} tokens remain."""
    text = template_path.read_text(encoding="utf-8")
    for needle, value in replacements.items():
        text = text.replace(needle, value)
    # Sanity check: no unfilled placeholders should remain
    if "{{" in text or "}}" in text:
        leftover = re.findall(r"\{\{[^}]+\}\}", text)
        raise RuntimeError(
            f"unfilled placeholders in {template_path.name}: {leftover}"
        )
    return text


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--atlas",
        default="data/processed/atlas.csv",
        type=Path,
        help="Path to atlas.csv (post-orchestrator output)",
    )
    p.add_argument(
        "--metadata",
        default="data/snapshots/ictrp_metadata.json",
        type=Path,
        help="Path to ictrp_metadata.json (post-loader output)",
    )
    p.add_argument(
        "--manifest",
        default=".preregistration_commit.txt",
        type=Path,
        help="Path to preregistration anchor manifest",
    )
    p.add_argument(
        "--templates-dir",
        default="e156-submission",
        type=Path,
        help="Directory containing body.md and synthesis-methods-note.md",
    )
    args = p.parse_args(argv)

    for path in [args.atlas, args.metadata, args.manifest]:
        if not path.exists():
            raise MissingInputError(f"required input missing: {path}")

    atlas = pd.read_csv(args.atlas)
    metadata = json.loads(args.metadata.read_text(encoding="utf-8"))
    prereg_sha = parse_prereg_commit_sha(args.manifest)
    replacements = compute_replacements(atlas, metadata, prereg_sha)

    print("Replacements:")
    for k, v in replacements.items():
        print(f"  {k} -> {v!r}")

    templates = ["body.md", "synthesis-methods-note.md"]
    for name in templates:
        tpl = args.templates_dir / name
        if not tpl.exists():
            raise MissingInputError(f"template missing: {tpl}")
        filled = fill_template(tpl, replacements)
        out = tpl.with_suffix(tpl.suffix + ".filled")
        out.write_text(filled, encoding="utf-8")
        print(f"  wrote {out}")

    print("filler OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
