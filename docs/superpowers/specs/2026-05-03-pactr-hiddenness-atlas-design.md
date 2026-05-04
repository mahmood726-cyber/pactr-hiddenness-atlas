# PACTR Hiddenness Atlas — Design & Preregistration Protocol

| Field | Value |
|---|---|
| **Version** | v0.0.1 (preregistration; zero implementation) |
| **Date** | 2026-05-03 |
| **Status** | preregistered |
| **Successor of** | none |
| **Sister projects** | ARAC (representation in Cochrane), Hiddenness Atlas (CT.gov), Trial-Truthfulness Atlas, malaria-ct-recon |
| **Local path** | `C:/Projects/pactr-hiddenness-atlas/` |
| **GitHub repo** | `github.com/mahmood726-cyber/pactr-hiddenness-atlas` |
| **Pages** | `https://mahmood726-cyber.github.io/pactr-hiddenness-atlas/` |

## 0. Purpose

Every atlas in the portfolio (Hiddenness, Repro-Floor, PI, Responder-Floor, Cochrane-Modern-RE, Trial-Truthfulness, ARAC) draws from CT.gov + Cochrane. None ingests PACTR — the WHO-recognised Pan-African Clinical Trials Registry, where Africa-led / Africa-sited trials register. That is a structural blind spot for a portfolio explicitly focused on global evidence equity. PACTR Hiddenness Atlas is a 10-condition Africa-burden audit of the WHO ICTRP weekly export, computing a four-gate hiddenness funnel (PACTR registered → results posted → published → cited in any Cochrane MA) per condition, with the NCT-bridge as the primary Cochrane-match method.

Headline question: **of N PACTR-registered African trials in 10 high-burden conditions, what fraction are ever cited in a Cochrane meta-analysis?** Compares against TrialScout's CT.gov baseline of ~63.6% to quantify the African-evidence-to-global-synthesis gap.

## 1. Scope (Africa-condition slice; v0.1.0)

The v0.1.0 corpus is restricted to PACTR-registered trials matching one of 10 conditions:

| # | Condition | Why included |
|---|---|---|
| 1 | Tuberculosis | Largest single-cause death in SSA pre-COVID; well-Cochraned |
| 2 | HIV | Huge African trial volume; PEPFAR-driven |
| 3 | Sickle cell disease | West/Central Africa epicentre; Cochrane-thin → strong "hidden" signal expected |
| 4 | Schistosomiasis | NTD, almost entirely African registrations; Cochrane MAs exist |
| 5 | Maternal sepsis / postpartum haemorrhage | Lancet maternal-health priority; Cochrane Pregnancy/Childbirth deep |
| 6 | Neonatal sepsis | Same axis, separate evidence base |
| 7 | Snakebite envenoming | WHO NTD priority since 2017; almost no synthesis infra → expected hidden |
| 8 | Soil-transmitted helminths | NTD; mass-drug-administration trials; WHO-PRP MAs |
| 9 | Cervical cancer / HPV | Rising African burden; vaccine + screening trials |
| 10 | Cholera | Outbreak-driven; OCV trials; Africa-heavy |

**Deliberate exclusions:**
- **Malaria** — covered by `malaria-ct-recon`; would duplicate. Cross-validation deferred to v0.2.
- **Diabetes / hypertension** — thin PACTR denominators despite epidemiological transition relevance.
- **Onchocerciasis / Buruli ulcer / Lassa fever** — too few PACTR registrations for stable per-condition statistics.

## 2. Headline metric

Each condition row is measured along a four-gate funnel:

```
PACTR registered → Results posted on PACTR → Peer-reviewed publication → Cited in any Cochrane MA
   (gate 0)            (gate 1)                  (gate 2)                       (gate 3)
```

- **Headline number for paper abstracts:** Gate 0→3 ("synthesis loss"). One quotable percentage per condition + a single pooled headline.
- **Primary dashboard visual:** Sankey funnel decomposing all four gates by condition.
- **Secondary metrics:** Gate 0→1 (results-posting compliance, lower bound from `Results URL` field); Gate 1→2 (publication-of-results conversion); `tier0_invisible` (no NCT cross-registration — the equity finding).

## 3. Cochrane match method (the methodologically critical decision)

Three-strategy ensemble with explicit primacy:

1. **NCT cross-registration bridge (PRIMARY).** For each PACTR trial, parse `Secondary IDs` for an NCT identifier. If found, look up the NCT against a Pairwise70 + Cochrane CDSR study-reference index. Inclusion verdict driven entirely by NCT match.
2. **PACTR-ID literal match (SENSITIVITY).** Search CDSR for the literal PACTR identifier string. Expected low recall (Cochrane historically cites NCT, not PACTR), but catches reviews that did cite PACTR directly. Reported as a separate column in `atlas.csv`; not used for the primary verdict.
3. **Pairwise70-validated subset (BOUNDED VALIDATION).** Restrict to Cochrane MAs covered by the Pairwise70 corpus and manually verify the algorithmic verdict on every trial in that subset. Closed-form audit cohort.

**`tier0_invisible` is a first-class equity finding.** Trials with no NCT cross-registration cannot, by construction, be matched via NCT bridge. Rather than hide this in fuzzy matching, the atlas surfaces them as Tier-0: "not even visible to global registry infrastructure." This subset's size and per-condition distribution is a primary paper finding.

**Fuzzy title+author+year matching is deliberately rejected** — the LLM-screening false-include rate is documented at ~92% over-inclusion in this portfolio's lessons, and would explode v0.1.0 scope without proportionate epistemic gain.

## 4. Cohort involvement (deferred)

v0.1.0 ships engine-only. The Makerere PhD verification UI (ARAC pattern: one-trial-at-a-time confirmation, localStorage, JSON export) is deferred to **v0.2**. Reasons: (a) engine-first surfaces *which* algorithmic decisions are most contested, so v0.2 cohort effort targets the borderline trials rather than uniformly across all rows; (b) ARAC Plan 3C provides a verification-UI template that clones in days; (c) ship-and-iterate is the portfolio's strongest pattern.

## 5. Data source

- **PRIMARY (v0.1.0):** WHO ICTRP weekly export (CSV bulk dump, all 17 primary registries combined, ~600 MB). Filter `Source Register == "PACTR"`. Includes Secondary IDs (NCT cross-references), conditions, recruitment status, sponsor, locations, `Results URL`. One HTTP GET, freezable as a snapshot exactly like AACT 2026-04-12.
- **DEFERRED to v0.2:** PACTR website scrape for results-posting timestamps (more fidelity on Gate 1 than ICTRP's `Results URL` lower-bound).

**Task 0 preflight verifier (fail-closed prerequisite):**
- `paths.toml` exists; every key resolves to a readable file or directory.
- ICTRP URL responds 200; CSV parseable; PACTR filter returns ≥5,000 rows.
- `Secondary IDs` and `Conditions` fields populated and non-trivial.
- Each of the 10 conditions has ≥20 PACTR-tagged trials.
- Pairwise70 study-reference index at `paths.toml::pairwise70_index` is readable; sample lookup of 5 known NCTs returns expected reviews.
- CDSR string index at `paths.toml::cdsr_string_index` is readable.
- Europe PMC API responds 200 to a probe query.
- All required Python imports resolve.
- Snapshot sha256 validates against on-disk metadata.

If any check fails, the entire pipeline halts. No tests, no implementation, no run.

## 6. Ship bundle (v0.1.0 release contract)

| Slot | Value |
|---|---|
| Local path | `C:/Projects/pactr-hiddenness-atlas/` |
| GitHub repo | `mahmood726-cyber/pactr-hiddenness-atlas` |
| GitHub Pages | live, `index.html` redirect → `dashboard/index.html`, no external CDN |
| Snapshot | ICTRP weekly export frozen at the date Task 0 first succeeds |
| Path config | Single `paths.toml.example` carries `ictrp_snapshot`, `pairwise70_index`, `cdsr_string_index`, and `europe_pmc_cache_dir`. Real `paths.toml` is gitignored. No hardcoded `C:/...` paths anywhere in `src/` or `tests/` per portfolio rule. |
| Preregistration | framework-HEAD commit pin + OpenTimestamps Bitcoin anchoring + Internet Archive snapshot |
| Tests | pytest, target 60–100 tests, Sentinel pre-push hook installed, 0 BLOCK at v0.1.0 |
| Spec location | `docs/superpowers/specs/2026-05-03-pactr-hiddenness-atlas-design.md` (this file) |
| Paper targets | (1) E156 micro-paper for `C:/E156/rewrite-workbook.txt`; (2) Synthēsis Methods Note ≤400w |
| Authorship | E156: middle-author-only for MA per consolidated feedback memory; Synthēsis: standard byline (board COI retired 2026-04-20) |
| Output artefacts | `data/processed/atlas.csv`, `data/processed/atlas_baseline.csv`, `dashboard/index.html`, `e156-submission/protocol.md`, `e156-submission/body.md` |

## 7. Architecture

```
pactr-hiddenness-atlas/
├── pilots/
│   ├── preflight.py             # Task 0: prereq verifier; fail-closed
│   └── run_all.py               # orchestrator
├── src/pactr_atlas/
│   ├── ictrp_loader.py          # ICTRP CSV → DataFrame; filter Source Register == "PACTR"
│   ├── condition_matcher.py     # condition keyword → trial subset (10 conditions, MeSH + free-text)
│   ├── nct_bridge.py            # parse Secondary IDs → NCT extraction
│   ├── cochrane_match.py        # ensemble: NCT-bridge + PACTR-ID literal + Pairwise70 validation
│   ├── results_posting.py       # ICTRP "Results URL" → Gate 1 lower bound
│   ├── publication_match.py     # Europe PMC / PubMed lookup → Gate 2
│   ├── funnel.py                # per-condition × per-gate counts → atlas.csv
│   └── dashboard_builder.py     # render Sankey + per-condition forest into static HTML
├── data/
│   ├── raw/                     # ICTRP weekly snapshot (gitignored except metadata)
│   ├── processed/               # atlas.csv, per-condition parquet
│   └── snapshots/               # ictrp_metadata.json (URL, sha256, fetched-at)
├── dashboard/                   # built site (Pages root)
├── e156-submission/             # protocol.md + the 156w body + Synthēsis methods note
├── tests/                       # pytest, ~60-100 tests
├── docs/superpowers/specs/      # this design
├── ictrp_path.toml.example      # local snapshot path config
└── .preregistration_commit.txt  # framework-HEAD pin + OTS receipt + IA URL
```

**Boundary contract per module:**

| Module | What | Public interface | Depends on |
|---|---|---|---|
| `ictrp_loader` | Load frozen ICTRP CSV → PACTR-only DataFrame | `load_pactr_snapshot(path) -> pd.DataFrame` | filesystem, schema validator |
| `condition_matcher` | Map trial → 0..1 of 10 conditions | `assign_condition(trial_row) -> Optional[str]` | static keyword + MeSH lookup table |
| `nct_bridge` | Extract NCT cross-references | `extract_nct(secondary_ids: str) -> Optional[str]` | regex only |
| `cochrane_match` | Decide if a trial appears in any Cochrane MA | `match_trial(nct, pactr_id) -> MatchVerdict` | Pairwise70 study refs, CDSR string index |
| `funnel` | Per-condition gate counts | `compute_funnel(trials_df) -> pd.DataFrame` | upstream modules |
| `dashboard_builder` | Static HTML render | `build(atlas_df, out_dir)` | `atlas.csv` only |

## 8. Data model

**`trials.parquet` (one row per PACTR-registered trial in the 10 conditions):**

| column | type | notes |
|---|---|---|
| `trial_id` | str | ICTRP `TrialID` |
| `pactr_id_normalized` | str | cleaned form |
| `condition` | str ∈ 10-set | from `condition_matcher` |
| `condition_match_method` | str | `mesh` / `keyword_strict` / `keyword_fuzzy` |
| `country_lead` | str (ISO-3) | first listed country |
| `countries_all` | list[str] | all listed countries |
| `sponsor_class` | str | `industry` / `academic` / `pdp` / `government` / `other` |
| `recruitment_status` | str | from ICTRP |
| `submit_date` | date | `Date registered` |
| `expected_completion_date` | date \| null | from ICTRP |
| `nct_secondary` | str \| null | extracted via `nct_bridge` |
| `gate0_registered` | bool | denominator; always True |
| `gate1_results_posted` | bool | `Results URL` non-null (lower bound) |
| `gate2_published` | bool | Europe PMC verdict |
| `gate2_pmid` | str \| null | resolved PMID |
| `gate3_in_cochrane` | bool | `cochrane_match` primary verdict |
| `gate3_match_method` | str | `nct_bridge` / `pactr_id_literal` / `pairwise70_validated` / `none` |
| `gate3_cochrane_review_id` | str \| null | CDSR ID if matched |
| `gate3_ensemble_disagree` | bool | NCT-bridge and PACTR-ID literal disagree |
| `tier0_invisible` | bool | `nct_secondary is None` |
| `multi_condition_drop_flag` | bool | dropped because matched ≥2 conditions |

**`atlas.csv` (one row per condition):**

| column | meaning |
|---|---|
| `condition` | one of 10 |
| `n_registered` | denominator |
| `n_gate1` | results-posted count |
| `n_gate2` | published count |
| `n_gate3` | in-Cochrane count |
| `pct_gate0_to_gate3` | **headline metric per condition** |
| `pct_gate0_to_gate3_ci_lo`, `_hi` | clustered bootstrap 95% CI (cluster = `country_lead`) |
| `n_gate3_given_gate2` | nested-gate count: trials in Cochrane AND independently detected in Europe PMC (for monotone Sankey rendering) |
| `pct_gate0_to_gate3_given_gate2` | nested-gate headline (sensitivity for the independent `pct_gate0_to_gate3`) |
| `n_tier0_invisible` | trials with no NCT cross-registration |
| `nct_bridge_share` | fraction of `gate3_in_cochrane` discovered via NCT bridge vs PACTR-ID literal |
| `gate3_ensemble_disagree_count` | sensitivity column |
| `snapshot_date` | ICTRP weekly export date (denormalised onto every row) |

**Constraints:**
- Gates are boolean. Soft / partial matches go in `gate3_match_method`, never blur the gate itself.
- `tier0_invisible` is a first-class column, not a derived view.
- Snapshot date is denormalised onto every row; v0.2 refresh joins on `(trial_id, snapshot_date)`.
- Gate3 is reported in two flavours: independent (`n_gate3`, headline) and nested-on-Gate2 (`n_gate3_given_gate2`, used for monotone Sankey + sensitivity). `n_gate3 > n_gate2` is valid; `n_gate3_given_gate2 <= min(n_gate2, n_gate3)` always holds.

**Deliberately NOT in the data model:**
- No effect-size, τ², MA pooling — registry-integrity audit, not meta-analysis.
- No per-author / per-investigator fields — ARAC's domain.
- No per-gate `last_updated_date` — snapshot freezing is the only versioning.
- No free-text fields beyond `sponsor_name_raw` (kept for sponsor-class audit trail) — minimises LLM-fabrication surface.

## 9. Data flow

```
ICTRP weekly CSV (~600 MB, ~750K rows, all 17 registries)
  │ ictrp_loader.load_pactr_snapshot
  ▼
PACTR-only DataFrame (~6-8K rows)
  │ condition_matcher.assign_condition (drop if 0 or ≥2 matches)
  ▼
~1-2K rows tagged with one of 10 conditions
  │ nct_bridge.extract_nct (populate nct_secondary; flip tier0_invisible)
  ▼
Trials with optional NCT twin
  │ results_posting.gate1   (ICTRP "Results URL")
  │ publication_match.gate2 (Europe PMC by NCT, fallback PACTR-ID)
  │ cochrane_match.match_trial (ensemble: NCT-bridge → PACTR-ID literal → Pairwise70)
  ▼
trials.parquet (one row per trial, all four gates filled)
  │ funnel.compute_funnel (clustered bootstrap CI on gate0→gate3, cluster = country_lead)
  ▼
atlas.csv (10 rows, one per condition)
  │ dashboard_builder.build (Sankey + per-condition forest, inline-SVG)
  ▼
dashboard/index.html (single-file, Pages-ready)
```

**Deterministic ordering rules:**
1. Preflight is a hard gate — its failure makes downstream imports raise `PreflightFailed`.
2. Each module reads only the previous step's parquet — re-run from any checkpoint via `python -m pilots.run_all --from <module>`.
3. Cochrane match is last among gates — re-running with a Cochrane-source bug fix doesn't redo Gates 0–2.
4. Bootstrap clusters on `country_lead`.
5. Snapshot freezing happens once at preflight; all downstream consumers read from the pinned sha256 metadata.

**Caching boundaries:**

| Step | Cached? | Invalidated by |
|---|---|---|
| ICTRP fetch | Yes (sha256 in metadata) | manual replace + new metadata |
| Condition assignment | Yes | change to keyword/MeSH table |
| Europe PMC lookup | Yes (per-NCT JSON cache) | manual cache nuke |
| Cochrane match | No — always recomputed | source-of-truth volatility |

**Performance budget:**
- ICTRP filter + write: ≤30 s.
- Condition matching: ≤5 s for 8K trials.
- Europe PMC + Cochrane match: ≤10 min total.
- Dashboard build: ≤3 s.
- Full `pilots.run_all` from frozen snapshot: ≤15 min wall-clock.
- >2× budget on any step → `PERFORMANCE_REGRESSION` warning (non-blocking, logged to `sentinel-findings.md`).

## 10. Error handling

Philosophy: **explicit verdicts, no silent substitution, no fabricated defaults.**

| Failure | Module | Verdict | Action |
|---|---|---|---|
| ICTRP URL 404 / auth wall | `preflight` | `PREFLIGHT_NETWORK_FAIL` | Halt; print exact URL + curl command; suggest fallback B (PACTR scrape) |
| ICTRP schema drift (column missing/renamed) | `ictrp_loader` | `SCHEMA_DRIFT` | Halt; diff observed vs frozen schema |
| Frozen snapshot file missing | `ictrp_loader` | `SNAPSHOT_MISSING` | Halt; refuse silent re-fetch (breaks reproducibility) |
| Condition matcher hits 0 or <20 trials | `condition_matcher` | `CONDITION_DENOMINATOR_BELOW_MIN` | Halt at preflight; log to `STUCK_FAILURES.jsonl` |
| Trial matches ≥2 conditions | `condition_matcher` | drop with `multi_condition` flag | Logged to `multi_condition_drops.csv` |
| `Secondary IDs` empty/malformed | `nct_bridge` | `nct_secondary = None`, `tier0_invisible = True` | Data, not error — surfaced as equity finding |
| NCT regex matches non-NCT | `nct_bridge` | reject | Strict `^NCT\d{8}$` after stripping |
| Europe PMC 429 / 503 | `publication_match` | retry exponential backoff (max 5, 30s cap), then `gate2_lookup_failed = True` | Verdict becomes `unknown`, not `False` |
| Europe PMC ≥2 PMIDs for one NCT | `publication_match` | `gate2_ambiguous = True`, lowest PMID | Sensitivity `--reject-ambiguous` flag re-runs at v0.1.0 |
| Cochrane source missing | `cochrane_match` | `COCHRANE_SOURCE_MISSING` | Halt at preflight; numerical witness skip ≠ release pass |
| Cochrane ensemble disagrees | `cochrane_match` | primary verdict = NCT bridge; `gate3_ensemble_disagree = True` | Counted in atlas.csv |
| Bootstrap fails (k<3 cell) | `funnel` | report point estimate, omit CI, flag `ci_undefined` | Never extrapolate |
| Performance budget >2× | `pilots.run_all` | `PERFORMANCE_REGRESSION` | Non-blocking warning |
| cp1252 mojibake on Windows | all CLIs | `io.TextIOWrapper(stdout, encoding='utf-8', errors='replace')` at every entry point | per portfolio cp1252 lesson |
| Empty DataFrame in `funnel` | `funnel` | `if df.empty: raise EmptyFunnelInput` | per P1-empty-dataframe-access sentinel rule |

**Structural rules:**
1. No `"unknown"` / `0` / `1.0` defaults for missing required fields — typed exceptions only.
2. Numeric extractions check preceding 30 chars for negation words.
3. `hmac.compare_digest` for sha256 verification on snapshots.
4. Bulk patches to keyword/MeSH tables are idempotent-checked (grep-before-insert).
5. All blockers go to `STUCK_FAILURES.md` + `STUCK_FAILURES.jsonl`.
6. `data/processed/atlas_baseline.csv` committed at v0.1.0; cell drift >1pp without `BASELINE_BUMP_REASON.md` → Sentinel BLOCK.

## 11. Testing & validation

**Test stratification (target 60–100 tests):**

| Layer | Count | What | When |
|---|---|---|---|
| Unit | ~40 | each module's public functions in isolation | every commit |
| Contract | ~10 | inter-module interfaces (`MatchVerdict` shape, parquet column contract) | every commit |
| Integration | ~10 | full pipeline on 50-trial fixture CSV | every commit |
| Snapshot regression | ~5 | live `atlas.csv` byte-equality vs `atlas_baseline.csv` | every commit + nightly |
| Stochastic | ~5 | bootstrap CI coverage on synthetic data, atol=0.05 | nightly only |
| Smoke | ~3 | `pilots.preflight` green; `pilots.run_all --dry-run`; dashboard renders without external CDN | pre-push hook |

**Validation against external claims (gates v0.1.0 ship):**
1. **TrialScout sanity check.** Gate 0→2 rate for cross-registered subset within ±10pp of TrialScout's CT.gov ~63.6% baseline.
2. **Manual spot-check of 30 random trials.** The project lead audits each gate verdict against the underlying ICTRP / Europe PMC / CDSR records (solo for v0.1.0; Makerere cohort at v0.2). Required agreement ≥27/30 (90%). The 30-trial sample, the auditor's verdicts, and any disagreements are committed to `data/processed/spotcheck_v0.1.0.csv` as part of the v0.1.0 release.
3. **Cochrane match ensemble disagreement rate.** `gate3_ensemble_disagree` count <5% of `gate3_in_cochrane`.

## 12. Preregistration sequencing (HARD GATE)

Before any TDD code is written:

1. `git rev-parse --show-toplevel` → confirm not inside an existing repo.
2. `git init` in `C:/Projects/pactr-hiddenness-atlas/`.
3. Commit this design doc + `e156-submission/protocol.md` (preregistration summary) + `README.md` stub + `LICENSE` (MIT).
4. `git tag prereg-v0.0.1 -m "Protocol preregistered before implementation"`.
5. `gh repo create mahmood726-cyber/pactr-hiddenness-atlas --public --source=. --remote=origin --push`.
6. `git push origin --tags`.
7. OpenTimestamps the tagged commit: `ots stamp .git/refs/tags/prereg-v0.0.1`; commit the resulting `.ots` receipt.
8. Internet Archive snapshot the GitHub tag tree URL.
9. Write `.preregistration_commit.txt` containing tag SHA + OTS receipt path + IA snapshot URL + fetched-at timestamp.
10. Commit `.preregistration_commit.txt` as the first post-prereg commit. The diff between `prereg-v0.0.1` and this commit is the audit trail.

**Project-local Sentinel rule:** any commit that touches `src/`, `pilots/`, or `tests/` before `.preregistration_commit.txt` exists → BLOCK.

## 13. Out-of-scope

- Effect-size pooling, τ², MA aggregation.
- Per-author / per-investigator analysis (ARAC's job).
- PACTR website scrape (deferred to v0.2).
- CDSR licensing changes — out of automatic recovery scope.
- Trial appearance in non-Cochrane systematic reviews (JBI, Campbell) — v0.3 question.

## 14. Future versions

| Version | Scope |
|---|---|
| v0.1.1 | ICTRP weekly refresh; diff against v0.1.0 baseline |
| v0.2 | Makerere cohort verification UI; PACTR website scrape for results-posting fidelity; malaria cross-validation against `malaria-ct-recon` |
| v0.3 | Non-Cochrane systematic-review comparison (JBI, Campbell); per-condition forest of Δ between Cochrane-only vs all-syntheses metrics |

## 15. References (portfolio + literature)

**Portfolio:**
- ARAC — Cochrane representation atlas (Makerere PhD-cohort flagship)
- Hiddenness Atlas (CT.gov) — `C:/Projects/ctgov-analyses/ctgov-hiddenness-atlas/`
- Trial-Truthfulness Atlas — registry-coherence audit
- malaria-ct-recon — pilot pattern; PACTR Hiddenness Atlas reuses this scaffold
- responder-floor-atlas — clustered-bootstrap-CI dashboard pattern
- Pairwise70 — Cochrane MA dataset for NCT-bridge index

**External:**
- TrialScout (medRxiv 2026.03.15) — ~63.6% CT.gov registration → publication linkage
- WHO ICTRP — Pan-African registry feed: `https://www.who.int/clinical-trials-registry-platform`
- PACTR — `https://pactr.samrc.ac.za/`
- INSPECT-SR (medRxiv 2025.09.03) — trustworthiness checks orthogonal to RoB
- arXiv:2406.19228 — confident-tone tool failures invisible to agents (informs §10 explicit-verdict rule)
- Cochrane Handbook v6.5 — methodological reference (§13 reporting bias)
