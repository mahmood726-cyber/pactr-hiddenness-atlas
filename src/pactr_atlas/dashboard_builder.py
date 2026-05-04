"""Static HTML dashboard with inline-SVG Sankey + per-condition forest.

Single self-contained file (responder-floor pattern). NO external CDN,
NO JS framework. Renders offline.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<title>PACTR Hiddenness Atlas — preregistration v0.0.1</title>
<style>
  body {{ font: 14px/1.45 system-ui, -apple-system, sans-serif; margin: 24px; color:#222; }}
  h1 {{ margin-bottom: 4px; }} h2 {{ margin-top: 24px; }}
  table {{ border-collapse: collapse; margin-top: 8px; }}
  th, td {{ border: 1px solid #ccc; padding: 4px 8px; text-align: right; }}
  th:first-child, td:first-child {{ text-align: left; }}
  .funnel-svg {{ display: block; margin: 12px 0; }}
</style>
</head><body>
<h1>PACTR Hiddenness Atlas</h1>
<p><em>Preregistration v0.0.1 — fixture-mode dashboard.</em></p>
<h2>Headline funnel (Sankey)</h2>
{sankey_svg}
<h2>Per-condition table</h2>
{table_html}
<h2>Tier-0 invisibility (no NCT cross-registration)</h2>
{tier0_svg}
<p style="font-size:12px;color:#666;margin-top:24px">Source: WHO ICTRP weekly export. Snapshot pinned by sha256 in <code>data/snapshots/ictrp_metadata.json</code>. Anchored on Bitcoin via OpenTimestamps; see <code>.preregistration_commit.txt</code>.</p>
</body></html>
"""


def _sankey_svg(atlas: pd.DataFrame) -> str:
    n_reg = int(atlas["n_registered"].sum())
    n_g1 = int(atlas["n_gate1"].sum())
    n_g2 = int(atlas["n_gate2"].sum())
    n_g3 = int(atlas["n_gate3"].sum())
    if n_reg == 0:
        return "<svg class='funnel-svg'></svg>"
    h = lambda n: max(2, int(120 * n / n_reg))
    return (
        "<svg class='funnel-svg' width='720' height='180'>"
        f"<rect x='0'   y='30' width='80' height='{h(n_reg)}' fill='#3a6'/>"
        f"<rect x='200' y='30' width='80' height='{h(n_g1)}'  fill='#69b'/>"
        f"<rect x='400' y='30' width='80' height='{h(n_g2)}'  fill='#a86'/>"
        f"<rect x='600' y='30' width='80' height='{h(n_g3)}'  fill='#c63'/>"
        f"<text x='40'  y='170' text-anchor='middle'>registered ({n_reg})</text>"
        f"<text x='240' y='170' text-anchor='middle'>results ({n_g1})</text>"
        f"<text x='440' y='170' text-anchor='middle'>published ({n_g2})</text>"
        f"<text x='640' y='170' text-anchor='middle'>cochrane ({n_g3})</text>"
        f"<text x='360' y='15' text-anchor='middle' font-weight='bold'>Sankey funnel: gate 0 -> gate 3</text>"
        "</svg>"
    )


def _table_html(atlas: pd.DataFrame) -> str:
    cols = ["condition", "n_registered", "n_gate1", "n_gate2", "n_gate3",
            "pct_gate0_to_gate3", "n_tier0_invisible"]
    df = atlas[cols].copy()
    df["pct_gate0_to_gate3"] = (df["pct_gate0_to_gate3"] * 100).round(1).astype(str) + "%"
    return df.to_html(index=False, border=0)


def _tier0_svg(atlas: pd.DataFrame) -> str:
    rows = atlas[["condition", "n_registered", "n_tier0_invisible"]].copy()
    rows["pct"] = rows["n_tier0_invisible"] / rows["n_registered"].replace({0: 1})
    rows = rows.sort_values("pct", ascending=False)
    bars = []
    for i, (_, r) in enumerate(rows.iterrows()):
        w = max(2, int(400 * r["pct"]))
        bars.append(
            f"<rect x='160' y='{20 + i * 22}' width='{w}' height='16' fill='#933'/>"
            f"<text x='150' y='{32 + i * 22}' text-anchor='end'>{r['condition']}</text>"
            f"<text x='{170 + w}' y='{32 + i * 22}'>{r['n_tier0_invisible']}/{r['n_registered']}</text>"
        )
    return f"<svg class='funnel-svg' width='720' height='{40 + len(rows) * 22}'>{''.join(bars)}</svg>"


def build_dashboard(atlas: pd.DataFrame, out_dir: Path) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    html = _HTML_TEMPLATE.format(
        sankey_svg=_sankey_svg(atlas),
        table_html=_table_html(atlas),
        tier0_svg=_tier0_svg(atlas),
    )
    target = out_dir / "index.html"
    target.write_text(html, encoding="utf-8")
    return target
