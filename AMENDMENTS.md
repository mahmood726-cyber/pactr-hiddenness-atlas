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
