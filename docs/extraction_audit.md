# Extraction audit — known limitations of v0.1.0

This file is the living record of every documented limit on the v0.1.0
release. Anything claimed in the paper that is bounded by one of these
limits MUST be paired with a citation to this section.

## Gate 1 (results-posted) is a lower bound

ICTRP exposes a `Results URL` field but not all PACTR results pages
populate it. v0.1.0 reports gate 1 as a lower bound. v0.2 (PACTR
website scrape) will tighten.

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
