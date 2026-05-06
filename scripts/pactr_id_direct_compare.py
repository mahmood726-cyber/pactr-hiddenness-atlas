"""PACTR Hiddenness Atlas v0.2 — Calibration comparator.

Reads:
  - data/v0.2/pactr_id_direct_results.json (PACTR-ID-direct hits)
  - data/processed/spotcheck_v0.1.0_auditor.csv (blinded-auditor gold standard)

Computes:
  - 2x2 table: TP, FN, FP, TN
  - Sensitivity + Wilson 95% CI
  - Specificity + Wilson 95% CI
  - Cohen's kappa
  - Comparison table: NCT-bridge | PACTR-ID-direct | Auditor

Writes: data/v0.2/v0.2_calibration_report.json
"""
from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent
RESULTS_PATH = REPO_ROOT / "data" / "v0.2" / "pactr_id_direct_results.json"
AUDITOR_PATH = REPO_ROOT / "data" / "processed" / "spotcheck_v0.1.0_auditor.csv"
OUTPUT_PATH = REPO_ROOT / "data" / "v0.2" / "v0.2_calibration_report.json"

# v0.1.0 NCT-bridge result (pre-registered)
# NCT-bridge TP=1 (auditor positive + algorithm hit), FN=15 (auditor positive + algorithm no_hit)
# Sensitivity = TP/(TP+FN) = 1/16 = 6.25%  <-- the pre-registered headline "6.2%"
NCT_BRIDGE_TP = 1
NCT_BRIDGE_HITS = 1  # total hits
NCT_BRIDGE_N = 30
# v0.1.0 auditor result (pre-registered gold standard)
AUDITOR_HITS = 16
AUDITOR_N = 30
AUDITOR_SENSITIVITY = AUDITOR_HITS / AUDITOR_N  # = 53.3%
# NCT-bridge sensitivity = TP/(TP+FN) = 1/(1+15) = 6.25%
NCT_BRIDGE_SENSITIVITY = NCT_BRIDGE_TP / AUDITOR_HITS  # = 1/16 = 6.25%

# ---------------------------------------------------------------------------
# Statistics helpers
# ---------------------------------------------------------------------------


def wilson_ci(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Wilson score 95% CI for a proportion k/n."""
    if n == 0:
        return (0.0, 0.0)
    from math import sqrt
    # z for alpha/2 = 0.025 -> z = 1.96
    z = 1.95996
    p_hat = k / n
    centre = (p_hat + z**2 / (2 * n)) / (1 + z**2 / n)
    half = (z * sqrt(p_hat * (1 - p_hat) / n + z**2 / (4 * n**2))) / (1 + z**2 / n)
    return (max(0.0, centre - half), min(1.0, centre + half))


def cohen_kappa(tp: int, fp: int, fn: int, tn: int) -> float:
    """Cohen's kappa between auditor and algorithm binary classifications."""
    n = tp + fp + fn + tn
    if n == 0:
        return 0.0
    p_o = (tp + tn) / n  # observed agreement
    # Expected agreement
    p_yes_alg = (tp + fp) / n
    p_yes_aud = (tp + fn) / n
    p_no_alg = (tn + fn) / n
    p_no_aud = (tn + fp) / n
    p_e = p_yes_alg * p_yes_aud + p_no_alg * p_no_aud
    if 1 - p_e == 0:
        return 1.0
    return (p_o - p_e) / (1 - p_e)


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------


def load_auditor_positives(auditor_path: Path) -> set[str]:
    """Return set of trial_ids where auditor found at least one T (any gate)."""
    positives: set[str] = set()
    with auditor_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            verdict = row.get("auditor_verdict", "")
            if "T" in verdict.upper():
                positives.add(row["trial_id"])
    return positives


def load_algorithm_hits(results_path: Path) -> dict[str, str]:
    """Return dict trial_id -> classification ('hit'|'no_hit')."""
    data = json.loads(results_path.read_text(encoding="utf-8"))
    return {t["trial_id"]: t["classification"] for t in data["trials"]}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    print("[compare] loading auditor gold standard...", flush=True)
    auditor_positives = load_auditor_positives(AUDITOR_PATH)
    print(f"  Auditor positives: {len(auditor_positives)}/30", flush=True)

    print("[compare] loading PACTR-ID-direct results...", flush=True)
    algo_hits = load_algorithm_hits(RESULTS_PATH)
    print(f"  Algorithm hits: {sum(1 for v in algo_hits.values() if v == 'hit')}/30", flush=True)

    # Build 2x2 table
    tp = fp = fn = tn = 0
    trial_details: list[dict] = []
    for trial_id, algo_verdict in algo_hits.items():
        auditor_pos = trial_id in auditor_positives
        algo_pos = algo_verdict == "hit"
        if auditor_pos and algo_pos:
            cell = "TP"
            tp += 1
        elif auditor_pos and not algo_pos:
            cell = "FN"
            fn += 1
        elif not auditor_pos and algo_pos:
            cell = "FP"
            fp += 1
        else:
            cell = "TN"
            tn += 1
        trial_details.append({
            "trial_id": trial_id,
            "auditor_positive": auditor_pos,
            "algorithm_hit": algo_pos,
            "cell": cell,
        })

    n = tp + fp + fn + tn
    assert n == 30, f"Expected 30 trials, got {n}"

    # Sensitivity (recall)
    sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    sens_lo, sens_hi = wilson_ci(tp, tp + fn)

    # Specificity
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    spec_lo, spec_hi = wilson_ci(tn, tn + fp)

    # Cohen's kappa
    kappa = cohen_kappa(tp, fp, fn, tn)

    # NCT-bridge reference: sensitivity = TP/(TP+FN) = 1/(1+15) = 1/16
    nct_sensitivity = NCT_BRIDGE_SENSITIVITY  # 6.25%
    nct_sens_lo, nct_sens_hi = wilson_ci(NCT_BRIDGE_TP, AUDITOR_HITS)

    # Improvement vs NCT-bridge
    improvement_x = sensitivity / (NCT_BRIDGE_SENSITIVITY) if NCT_BRIDGE_SENSITIVITY > 0 else float("inf")

    # Print comparison table
    print("\n" + "=" * 70)
    print("PACTR Hiddenness Atlas v0.2 — Calibration Report")
    print("=" * 70)
    print(f"{'':30s}  {'NCT-bridge':>14s}  {'PACTR-ID-direct':>16s}  {'Auditor':>8s}")
    print("-" * 70)
    print(f"{'Hits / 30:':30s}  {NCT_BRIDGE_HITS:>14d}  {tp + fp:>16d}  {AUDITOR_HITS:>8d}")
    print(f"{'TP:':30s}  {'n/a':>14s}  {tp:>16d}  {'(gold std)':>8s}")
    print(f"{'FP:':30s}  {'n/a':>14s}  {fp:>16d}  {'':>8s}")
    print(f"{'FN:':30s}  {'n/a':>14s}  {fn:>16d}  {'':>8s}")
    print(f"{'TN:':30s}  {'n/a':>14s}  {tn:>16d}  {'':>8s}")
    print(f"{'Sensitivity (TP/(TP+FN)):':30s}  {NCT_BRIDGE_SENSITIVITY*100:>13.1f}%  {sensitivity*100:>15.1f}%  {AUDITOR_SENSITIVITY*100:>7.1f}%")
    print(f"{'Wilson 95% CI:':30s}  [{nct_sens_lo*100:.1f},{nct_sens_hi*100:.1f}]%  [{sens_lo*100:.1f},{sens_hi*100:.1f}]%     n/a")
    print(f"{'Specificity (TN/(TN+FP)):':30s}  {'n/a':>14s}  {specificity*100:>15.1f}%")
    print(f"{'Wilson 95% CI (spec):':30s}  {'n/a':>14s}  [{spec_lo*100:.1f},{spec_hi*100:.1f}]%")
    print(f"{'Cohen kappa vs auditor:':30s}  {'n/a':>14s}  {kappa:>16.3f}")
    print(f"{'Improvement vs NCT-bridge:':30s}  {'baseline':>14s}  {improvement_x:>15.1f}x")
    print("=" * 70)
    print(f"\nConclusion: PACTR-ID-direct sensitivity = {sensitivity*100:.1f}% ({tp}/{tp+fn})")
    print(f"vs NCT-bridge baseline {NCT_BRIDGE_SENSITIVITY*100:.1f}% ({NCT_BRIDGE_HITS}/{AUDITOR_HITS})")
    print(f"vs auditor gold standard {AUDITOR_SENSITIVITY*100:.1f}% ({AUDITOR_HITS}/{AUDITOR_N})")
    print(f"Improvement: {improvement_x:.1f}x vs NCT-bridge")
    print(f"False positives (FP): {fp} — specificity {specificity*100:.1f}% ({tn}/{tn+fp})")
    print(f"(R3 caveat: FPs may include SRs citing multiple PACTR IDs; "
          f"upper-bound interpretation applies)")

    # Build report
    report = {
        "spec_version": "v0.2",
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "gold_standard": {
            "auditor_positives": AUDITOR_HITS,
            "auditor_negatives": AUDITOR_N - AUDITOR_HITS,
            "n_total": AUDITOR_N,
        },
        "nct_bridge_baseline": {
            "tp": NCT_BRIDGE_TP,
            "fn": AUDITOR_HITS - NCT_BRIDGE_TP,
            "n_auditor_positives": AUDITOR_HITS,
            "sensitivity": round(NCT_BRIDGE_SENSITIVITY, 4),
            "sensitivity_pct": round(NCT_BRIDGE_SENSITIVITY * 100, 1),
            "note": "pre-registered v0.1.0 headline: 6.2% (1/16 auditor-positive trials)",
        },
        "pactr_id_direct": {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "tn": tn,
            "n_total": n,
            "sensitivity": round(sensitivity, 4),
            "sensitivity_pct": round(sensitivity * 100, 1),
            "sensitivity_wilson_lo": round(sens_lo, 4),
            "sensitivity_wilson_hi": round(sens_hi, 4),
            "specificity": round(specificity, 4),
            "specificity_pct": round(specificity * 100, 1),
            "specificity_wilson_lo": round(spec_lo, 4),
            "specificity_wilson_hi": round(spec_hi, 4),
            "cohen_kappa": round(kappa, 4),
            "improvement_vs_nct_x": round(improvement_x, 2),
        },
        "comparison_table": {
            "nct_bridge_hits_30": NCT_BRIDGE_HITS,
            "pactr_id_direct_hits_30": tp + fp,
            "auditor_hits_30": AUDITOR_HITS,
            "nct_bridge_sensitivity_pct": round(NCT_BRIDGE_SENSITIVITY * 100, 1),
            "nct_bridge_sensitivity_note": "6.2% = TP/auditor_positives = 1/16",
            "pactr_id_direct_sensitivity_pct": round(sensitivity * 100, 1),
            "auditor_sensitivity_pct": round(AUDITOR_SENSITIVITY * 100, 1),
        },
        "trial_details": trial_details,
        "r3_caveat": (
            "FPs may include systematic reviews citing multiple PACTR IDs. "
            "Sensitivity estimate is an upper bound; specificity measures over-inclusion. "
            "v0.3 will add primary-publication filter."
        ),
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n[output] written to {OUTPUT_PATH}", flush=True)


if __name__ == "__main__":
    main()
