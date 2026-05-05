# Extraction audit — known limitations of v0.1.0

This file is the living record of every documented limit on the v0.1.0
release. Anything claimed in the paper that is bounded by one of these
limits MUST be paired with a citation to this section.

## Gate 1 (results-posted) is a lower bound — and may be an upper bound

The original spec described Gate 1 as a **lower bound** assuming
`Results URL` is conservatively populated. The v0.1.0 dry-run against
the full PACTR registry (5,878 trials, 768 matched 10 conditions)
revealed the OPPOSITE: PACTR populates `Results URL` for **100%** of
matched trials regardless of whether real results are posted. The
field is over-broad, so Gate 1 = `True` is an UPPER bound on actual
results posting. The 30-trial spot-check at v0.1.0 release time
quantifies the gap between Results-URL non-null and actual results
content; the auditor verdicts feed into the released percentages.
v0.2 (direct PACTR website scrape per trial detail page) will tighten
by inspecting each trial's results section, not just the URL field.

## v0.1.0 known data gap: PACTR 2019

The v0.1.0 PACTR snapshot (`pactr_full_2026-05-04.csv`, sha256
`44f99b14...`, 5,878 trials) was assembled by date-paginated scrape of
PACTR Search_v2.aspx with year windows 2008–2026. The 2019 window
returned PACTR server-side download timeout 9 times across ~600s
attempts in two scraping runs. Estimated ~456 trials lost (using the
~500-trials/year mean across surrounding years 2017, 2018, 2020, 2021).
The gap is RECORDED in `data/snapshots/ictrp_metadata.json` under
`known_gaps`. Because the gap is structural (server-side timeout, not
a content filter) it should not bias condition-mix; affected per-
condition counts are uniformly under by ~5–10% with no obvious
selection. v0.1.1 will retry the 2019 window after PACTR server
issues are resolved.

## v0.1.0 low-denominator conditions (n_registered < 20)

Five of the locked 10 conditions have fewer than 20 PACTR-registered
trials in the v0.1.0 snapshot:

| condition | n_registered |
|---|---:|
| snakebite | 4 |
| neonatal sepsis | 7 |
| cholera | 8 |
| soil-transmitted helminths | 11 |
| schistosomiasis | 14 |

The original spec set a **20-trial-per-condition** preflight floor as
a minimum-power gate. v0.1.0 explicitly documents these conditions as
having unreliable per-condition CIs, but does NOT drop them — dropping
preregistered conditions would constitute a HARK (hypothesizing after
results known) violation of `prereg-v0.0.1`. The pooled headline metric
across all 10 conditions remains valid (n=768); only the per-condition
breakdown for these 5 conditions is underpowered. v0.2 may either
(a) re-scrape with broader keyword strategies for these niche conditions,
OR (b) explicitly downgrade them to a "structural-zero" category if
PACTR genuinely does not register them in adequate numbers.

## Gate 2 (publication) depends on Europe PMC linkage

Europe PMC's NCT-to-PMID linkage is best-effort. Publications that do
not declare an NCT in the metadata are missed. Estimated under-count:
TBD post-spot-check.

## Gate 3 (Cochrane) bounded by Cochrane CDSR coverage

Non-Cochrane systematic reviews (JBI, Campbell, AHRQ) are out of scope.
Trials reaching JBI but not Cochrane are counted as gate-3 misses.

## tier0_invisible is a structural finding, not noise

Trials with no NCT cross-reference cannot, by construction, be matched
through the NCT bridge. v0.1.0 reports the per-condition share and does
not attempt fuzzy bridging.

## Bootstrap CI undefined when k_clusters < 3

Per the spec ordering rule, clustered-bootstrap CIs use country_lead.
Conditions whose trials are concentrated in <3 countries report point
estimates only.
