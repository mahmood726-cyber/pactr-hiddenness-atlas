# PACTR Hiddenness Atlas — Preregistration Protocol

**Version:** v0.0.1
**Date:** 2026-05-03
**Status:** preregistered before implementation
**Full design document:** `docs/superpowers/specs/2026-05-03-pactr-hiddenness-atlas-design.md`

This file is the condensed, paper-ready preregistration summary. The full design + decision rationale + module contracts live in the spec document. Both files are committed and tagged together as `prereg-v0.0.1` and Bitcoin-anchored via OpenTimestamps before any implementation work begins.

## Question

Of all PACTR-registered trials in 10 high-burden African conditions, what fraction are ever cited in a Cochrane meta-analysis?

## Conditions (10, fixed at preregistration)

Tuberculosis, HIV, sickle cell disease, schistosomiasis, maternal sepsis / postpartum haemorrhage, neonatal sepsis, snakebite envenoming, soil-transmitted helminths, cervical cancer / HPV, cholera.

Exclusions made and locked at v0.0.1: malaria (covered by `malaria-ct-recon`); diabetes / hypertension (thin PACTR denominators); onchocerciasis, Buruli ulcer, Lassa fever (registration counts too low for stable per-condition statistics).

## Funnel

```
gate 0: PACTR registered
gate 1: Results posted on PACTR        (proxy: ICTRP "Results URL" non-null — lower bound)
gate 2: Peer-reviewed publication      (Europe PMC lookup by NCT, fallback PACTR-ID)
gate 3: Cited in any Cochrane MA       (NCT-bridge primary; PACTR-ID literal sensitivity)
```

**Headline metric:** percentage gate 0 → gate 3, per condition and pooled. Compared against the published CT.gov baseline (TrialScout, ~63.6%, medRxiv 2026.03.15).

## Cochrane match — locked decisions

1. **Primary:** NCT cross-registration bridge. For each PACTR trial, parse `Secondary IDs` for an NCT, then look up the NCT in a Pairwise70 + Cochrane CDSR study-reference index.
2. **Sensitivity:** literal PACTR-ID search of the CDSR string index (expected low recall, surfaces direct citations).
3. **Validation cohort:** restrict to Pairwise70-covered Cochrane MAs; manually verify the algorithmic verdict on every trial in this subset.
4. **`tier0_invisible` is a first-class equity finding.** Trials with no NCT cross-registration cannot, by construction, be matched via NCT bridge. The atlas surfaces them as Tier-0 ("not even visible to global registry infra"), and their per-condition share is a primary paper finding.

Fuzzy title+author+year matching is **rejected** at preregistration. Recall would gain from it, but the false-include rate documented across this portfolio (~92% of remaining errors are over-inclusions in 2-LLM screening) would explode v0.1.0 scope without proportionate epistemic gain.

## Data source — locked at preregistration

- **PRIMARY (v0.1.0):** WHO ICTRP weekly export (CSV bulk dump, all primary registries combined). Filter `Source Register == "PACTR"`. Snapshot is pinned by sha256 in `data/snapshots/ictrp_metadata.json` at the moment of first successful preflight; no module re-fetches without an explicit human action and a metadata bump.
- **DEFERRED to v0.2:** PACTR website scrape for results-posting timestamps.

## Preflight (Task 0) — fail-closed gates

Implementation cannot begin (no test, no module) until every preflight check passes. The `pilots/preflight.py` script (to be written post-prereg) verifies: `paths.toml` resolves; ICTRP URL responds 200 and parses; PACTR filter ≥ 5,000 rows; `Secondary IDs` and `Conditions` populated; each of the 10 conditions has ≥ 20 PACTR-tagged trials; Pairwise70 + CDSR indexes readable; Europe PMC API responds 200; required Python imports resolve; snapshot sha256 validates.

## Cohort involvement

v0.1.0 ships engine-only. Makerere PhD verification UI (ARAC pattern) deferred to v0.2.

## Validation gates (pre-ship)

1. **TrialScout sanity check.** The cross-registered subset's gate 0 → 2 rate must fall within ±10 pp of the published CT.gov baseline (~63.6%).
2. **Manual spot-check.** Project lead audits 30 randomly sampled trials; required agreement ≥ 27/30 (90%).
3. **Cochrane match ensemble disagreement rate.** `gate3_ensemble_disagree` count must be < 5% of `gate3_in_cochrane`.

If any gate fails, v0.1.0 does not ship; the spec is amended via a new tag `prereg-v0.1.0-amend-N`.

## Out of scope

Effect-size pooling; per-author or per-investigator analysis (ARAC's domain); CDSR licensing changes; non-Cochrane systematic reviews.

## Anti-HARKing commitment

The 10 conditions, the four-gate definitions, the Cochrane-match ensemble, the fuzzy-matching rejection, and the three validation gates are all locked at this commit. Any change after `prereg-v0.0.1` requires a new tag whose name documents the amendment, and an entry in `AMENDMENTS.md` describing what changed and why.
