# PACTR Hiddenness Atlas

A 10-condition Africa-burden audit of the WHO ICTRP weekly export, computing a four-gate hiddenness funnel (PACTR registered → results posted → published → cited in any Cochrane MA) per condition.

**Status:** implemented through v0.2.0 (four-gate funnel, NCT-bridge + PACTR-ID-literal Cochrane match, clustered-bootstrap CI, dashboard). Tag `prereg-v0.0.1` anchors the original protocol, frozen before any code was written.

## Headline question

Of N PACTR-registered African trials in 10 high-burden conditions (TB, HIV, sickle cell, schistosomiasis, maternal sepsis, neonatal sepsis, snakebite, soil-transmitted helminths, cervical cancer, cholera), what fraction reach a Cochrane meta-analysis? Compares against the TrialScout CT.gov baseline (~63.6%) to quantify the African-evidence-to-global-synthesis gap.

## Design & preregistration protocol

See [`docs/superpowers/specs/2026-05-03-pactr-hiddenness-atlas-design.md`](docs/superpowers/specs/2026-05-03-pactr-hiddenness-atlas-design.md).

A condensed paper-ready preregistration summary lives at [`e156-submission/protocol.md`](e156-submission/protocol.md).

## Sister projects

- **ARAC** — African representation *inside* Cochrane (Makerere PhD-cohort flagship).
- **Hiddenness Atlas (CT.gov)** — same pattern, different registry.
- **Trial-Truthfulness Atlas** — registry-coherence audit.
- **malaria-ct-recon** — pilot scaffold this project clones.

## Reproducibility anchors

- `prereg-v0.0.1` tag → frozen protocol; pushed before implementation.
- OpenTimestamps Bitcoin anchor on the spec file → `docs/superpowers/specs/*.ots`.
- Internet Archive snapshot → recorded in `.preregistration_commit.txt`.
- ICTRP snapshot pinned by sha256 in `data/snapshots/ictrp_metadata.json` once preflight succeeds.

## License

MIT. See `LICENSE`.
