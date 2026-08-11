# ADR 0006: Isolation Forest as a comparison detector

Status: accepted — 2026-08-11

Deterministic sensor-quality rules and threshold hysteresis remain authoritative
for impossible values and configured bounds. A per-device Isolation Forest
provides a modest comparison using rolling temperature, current, vibration, and
crest-factor features. It is reproducible, handles multivariate outliers, and
does not require invented fault labels. Its score is not a probability; the UI
will show raw score, healthy-baseline percentile, evidence-based reasons, model
metadata, and fallback state.

