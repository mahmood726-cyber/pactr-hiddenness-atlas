# Amendments to the prereg-v0.0.1 protocol

This file documents every change to anchored protocol files made
**after** the `prereg-v0.0.1` tag (commit `c9cd90b3`, dated 2026-05-03).

Each amendment requires:
1. A new git tag (`prereg-v0.1.0-amend-N`).
2. An entry below describing what changed and **why**.
3. Re-stamp via `scripts/stamp_file.py` (3 OTS calendars).
4. New Internet Archive snapshot of the amended file.
5. Updated sha256 + receipt + IA URL in `.preregistration_commit.txt`,
   committed in the same SHA as the new tag.

Per the manifest's Anti-HARK commitment (lines 70–82), this is the only
permitted path for any change to a protocol-anchored file.

---

## Amendment 1 — `prereg-v0.1.0-amend-1` (2026-05-04)

**Anchored file changed:**
`docs/superpowers/specs/2026-05-03-pactr-hiddenness-atlas-design.md`

**What changed (diff vs prereg-v0.0.1):**
1. §8 atlas.csv schema table — added two rows:
   - `n_gate3_given_gate2` — nested-gate count: trials in Cochrane AND
     independently detected in Europe PMC.
   - `pct_gate0_to_gate3_given_gate2` — nested-gate headline (sensitivity
     companion to the independent `pct_gate0_to_gate3`).
2. §8 Constraints — added one bullet:
   > Gate3 is reported in two flavours: independent (`n_gate3`, headline)
   > and nested-on-Gate2 (`n_gate3_given_gate2`, used for monotone Sankey
   > + sensitivity).

The independent `n_gate3` and `pct_gate0_to_gate3` headline metric and
all other gate semantics are **unchanged**. No HARK risk: this is a
schema addition for sensitivity reporting, not a redefinition of any
preregistered metric.

**Why (root cause):**
Mid-implementation review of Task 16's snapshot baseline against the
50-trial fixture showed `n_gate3 > n_gate2` for 5 of 10 conditions.
This is mathematically correct under the spec — Gate2 (Europe PMC
publication detection) and Gate3 (Cochrane NCT-bridge match) were
always defined as independent measurements, not nested filters — but
the dashboard's sequential Sankey visual implicitly assumed monotone
funnel ribbons. Three resolution options were considered:

| Option | Action | Cost | Why rejected/chosen |
|--------|--------|------|---------------------|
| (i)    | Ship as-is + note in caption | 0 | Visually misleading in fixture mode |
| (ii)   | Make Gate3 a subset of Gate2 (require gate2_published=True first) | medium | Destroys real signal: an African-led trial in Cochrane that Europe PMC misses (e.g. national-journal publication not indexed) becomes invisible — exactly the population we're auditing |
| **(iii)** | **Emit BOTH flavours; Sankey uses nested, table+headline use independent** | medium | **CHOSEN.** Preserves the original headline metric, makes the visual monotone, exposes the discrepancy as a first-class sensitivity finding |

**Decision authority:** project lead (Mahmood Ahmad), 2026-05-04, in-session.

**Files touched in the amendment commit:**
- `docs/superpowers/specs/2026-05-03-pactr-hiddenness-atlas-design.md` (the change itself, already in commit `efbc9d5`)
- `docs/superpowers/specs/2026-05-03-pactr-hiddenness-atlas-design.md.ots` (new OTS receipt)
- `.preregistration_commit.txt` (new sha256 + receipt + IA URL appended in a new "Amendment 1" section)
- `AMENDMENTS.md` (this file, created)

**Implementation references (where the change is reflected in code):**
- `src/pactr_atlas/funnel.py::compute_funnel` — emits both columns (commit `70cb0dc`)
- `src/pactr_atlas/dashboard_builder.py` — Sankey uses nested column, table shows both (commit `75fd2e0`)
- `data/processed/atlas_baseline.csv` — regenerated with both columns (commit `6333736`)
- `tests/test_snapshot_regression.py` — both columns added to deterministic comparison set (commit `6333736`)
- `tests/test_funnel.py` — 2 new tests for the nested column + invariant `n_gate3_given_gate2 ≤ min(n_gate2, n_gate3)` (commit `70cb0dc`)

**Verifier expectation after amendment:**
`python scripts/verify_prereg.py` must report all anchors OK.

---

## Amendment 2 — `prereg-v0.1.0-amend-2` (2026-05-05)

**No anchored protocol file changed.** This amendment documents an explicit
**release decision**: v0.1.0 ships despite the validation_gates 30-trial
spot-check returning 0/30 verdict-level agreement (preregistered threshold:
≥27/30). The disagreement is the substantive v0.1.0 finding.

### What the spot-check found

A blinded 30-trial audit (sampled with seed=20260503 from `trials.parquet`,
auditor independently web-verified each gate against PACTR / Europe PMC /
Cochrane Library; algorithm verdicts withheld from auditor) produced:

| Gate | Algorithm True | Auditor True | Cell agreement |
|------|---:|---:|---:|
| Gate1 (results posted) | 30/30 | 3/30 | 10% |
| Gate2 (peer-published) | 1/30 | 16/30 | 50% |
| Gate3 (in Cochrane MA) | 0/30 | 1/30 | 97% |
| **Verdict-level (3-char string)** | — | — | **0/30 (0%)** |

### Why this is a finding, not a bug

- **Gate1**: algorithm uses spec lower-bound definition (`Results URL`
  non-null); auditor used strict content verification. Disagreement
  quantifies PACTR's `Results URL` over-broadness (90%).
- **Gate2**: algorithm uses NCT-bridge (`EXT_ID` query of Europe PMC);
  most PACTR trials lack NCT cross-registration so they are unreachable.
  Auditor used direct title / PI / PACTR-ID free-text search, finding
  16 publications. **Algorithm sensitivity = 1/16 = 6.3%.** This is the
  central v0.1.0 methodological finding: NCT-bridge methodology — used
  by every existing CT.gov-style synthesis audit (TrialScout, Hiddenness
  Atlas CT.gov, Trial Truthfulness Atlas, etc.) — is structurally blind
  to African evidence even when published.
- **Gate3**: 1 disagreement (WOMAN trial PACTR201007000192283 →
  Cochrane CD012964). Verified root cause: Pairwise70
  `study_references.parquet` (built from CDE) has zero rows for CD012964.
  CDE coverage gap, not matcher bug.

### HARK protection

This amendment does NOT lower the preregistered spot-check threshold;
the threshold remains ≥27/30. The amendment records that v0.1.0
EXPLICITLY ACKNOWLEDGES the threshold failure as the substantive
output of the release. The gate fired; the release does not pretend
otherwise. The full spot-check artifacts are committed as evidence
(`data/processed/spotcheck_v0.1.0_blinded.csv`,
`spotcheck_v0.1.0_auditor.csv`, `spotcheck_v0.1.0.csv`) so any reader
can independently verify the disagreement.

### What v0.1.0 paper claims

NOT: "0.5% of PACTR-registered African trials reach Cochrane synthesis."
INSTEAD: "Existing NCT-bridge methodology has ~6% sensitivity for
PACTR-registered African publications. The methodology is structurally
blind to African evidence even when published. PACTR-ID-direct EuropePMC
search (proposed v0.2) is needed."

### What's locked vs deferred

Locked at v0.1.0:
- 10-condition prereg (5 conditions are below n=20 floor; documented in
  `docs/extraction_audit.md` but not dropped).
- Algorithm pipeline (orchestrator, gate1/2/3, NCT-bridge to Pairwise70).
- Spot-check disagreement artifacts.

Deferred to v0.2:
- Add PACTR-ID-direct EuropePMC free-text search to gate2.
- Expand CDE coverage to include African-relevant Cochrane reviews
  (e.g., CD012964).
- Re-run with second human auditor for inter-auditor reliability.
- Refactor `validation_gates.py` to accept "documented disagreement
  profile" overrides instead of hard-failing.

### No file re-stamping needed

The two anchored protocol files (spec, protocol.md) remain unchanged
between Amendment 1 and Amendment 2. No new OTS receipts or IA snapshots
required for the manifest. The v0.1.0 tag itself will be OTS-stamped per
Task 22 Step 9.

### Release command path

```bash
# explicit acknowledgment flag required to ship past the gate failure
bash scripts/release_v010.sh --execute --ack-spotcheck-disagreement
```

The flag MUST be paired with this AMENDMENTS.md entry; the script
records the override into the v0.1.0 tag annotation.
