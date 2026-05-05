<!-- e156-submission/synthesis-methods-note.md
     Target: Synthēsis Methods Note (<= 400 words).
     Vancouver refs; Calibri 11pt or TNR 12pt; A4 1.5spc; OJS upload .docx. -->

# NCT-bridge methodology is structurally blind to PACTR-registered African trial publications

**Background.** Every existing audit of evidence-to-synthesis conversion (TrialScout, the California-universities audit, Hiddenness Atlas CT.gov) draws from ClinicalTrials.gov via NCT cross-registration. None measures whether African-led trials registered with the WHO-recognised Pan-African Clinical Trials Registry (PACTR) are detectable through this same methodology. PACTR is the primary registry for ~5878 African trials.

**Methods.** From the WHO ICTRP weekly export (snapshot 2026-05-04, sha256 44f99b14) we filtered to `Source Register == PACTR` (n = 5878) and assigned each trial to one of ten high-burden conditions via a locked keyword + MeSH table (n = 768 matched). Four gates were measured: registered (gate 0), results-posted (gate 1: ICTRP `Results URL` non-null), peer-published (gate 2), Cochrane-cited (gate 3). Algorithm gate 2 used NCT cross-registration to Europe PMC; a parallel 30-trial blinded spot-check used independent direct search by trial title and PACTR ID. Gate 3 used NCT-bridge to a Pairwise70 + CDSR study-reference index. Trials with no NCT cross-reference were tagged `tier0_invisible`.

**Results.** Algorithm: 3.6% peer-published (gate 2), 0.5% Cochrane-cited (gate 3). Blinded spot-check (n = 30): 53.3% peer-published (16/30), 1/30 Cochrane-cited (WOMAN trial, PACTR201007000192283 / NCT00872469 / Cochrane CD012964). Algorithm publication-detection sensitivity was 6.2% (16 auditor True, 1 algorithm True). The algorithm missed the WOMAN-Cochrane link because Pairwise70 study_references.parquet has zero rows for CD012964, a CDE coverage gap independent of the matcher. 96.0% of PACTR trials carry no NCT cross-reference and are structurally invisible to NCT-bridge methods.

**Limitations.** The `Results URL` field is a lower bound on gate 1; a 2019 PACTR scrape gap (~456 trials) applies; 5 of 10 conditions fell below the 20-trial preflight floor; spot-check used a single auditor with no inter-rater reliability estimate. CDE `study_references.parquet` completeness is not formally documented.

**Reproducibility.** Protocol preregistered as `prereg-v0.0.1` (c9cd90b) before implementation. ICTRP snapshot pinned by sha256; OpenTimestamps Bitcoin anchor + Internet Archive snapshot recorded in `.preregistration_commit.txt`. Code: `github.com/mahmood726-cyber/pactr-hiddenness-atlas`, tagged `v0.1.0`.
