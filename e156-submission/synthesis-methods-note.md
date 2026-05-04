<!-- e156-submission/synthesis-methods-note.md
     Target: Synthēsis Methods Note (<= 400 words).
     Vancouver refs; Calibri 11pt or TNR 12pt; A4 1.5spc; OJS upload .docx. -->

# A four-gate hiddenness funnel for the Pan-African Clinical Trials Registry

**Background.** Every existing audit of evidence-to-synthesis conversion (TrialScout, the California-universities audit, Hiddenness Atlas) draws from ClinicalTrials.gov. None measures whether African-led trials registered with the WHO-recognised Pan-African Clinical Trials Registry (PACTR) reach Cochrane synthesis.

**Methods.** From the WHO ICTRP weekly export (snapshot {{SNAPSHOT_DATE}}, sha256 {{SNAPSHOT_SHA8}}…) we filtered to `Source Register == PACTR` (n = {{N_PACTR}}) and assigned each trial to one of ten high-burden African conditions via a locked keyword + MeSH table; trials matching zero or ≥2 conditions were dropped (n = {{N_DROPPED}}). For each remaining trial we measured four gates: registered (gate 0), results-posted (gate 1: ICTRP `Results URL` non-null, lower bound), peer-published (gate 2: Europe PMC lookup by NCT cross-reference), cited in any Cochrane meta-analysis (gate 3). The gate-3 verdict was an ensemble: NCT-bridge against a Pairwise70 + CDSR study-reference index (primary), and literal PACTR-ID search of the CDSR string corpus (sensitivity). Trials with no NCT cross-reference were tagged `tier0_invisible` rather than blurred into a fuzzy match. Clustered bootstrap CIs used `country_lead` as the cluster.

**Results.** {{HEADLINE_PCT}}% of PACTR-registered trials in the ten conditions reached a Cochrane MA — well below the {{TRIALSCOUT_BASELINE}}% TrialScout reports for ClinicalTrials.gov. Per-condition gate-0→3 ranged from {{MIN_PCT}}% (snakebite) to {{MAX_PCT}}% (HIV). {{TIER0_PCT}}% of PACTR trials carry no NCT cross-reference and are structurally invisible to the global registry-bridge methodology. The literal-PACTR-ID sensitivity sweep added {{ENSEMBLE_DELTA}}pp.

**Limitations.** The `Results URL` field is a lower bound on results-posting; PACTR website fields not exposed via ICTRP will tighten gate 1 in v0.2. Cochrane CDSR coverage drives the upper bound on gate 3; non-Cochrane systematic reviews are out of scope.

**Reproducibility.** Protocol preregistered as `prereg-v0.0.1` ({{PREREG_COMMIT_SHORT}}) before any implementation. ICTRP snapshot pinned by sha256; OpenTimestamps Bitcoin anchor + Internet Archive snapshot recorded in `.preregistration_commit.txt`. Code: `github.com/mahmood726-cyber/pactr-hiddenness-atlas`, tagged `v0.1.0`.
