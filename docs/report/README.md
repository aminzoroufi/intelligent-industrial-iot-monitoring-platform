# Reproducible bilingual reports

The editable English and Persian sources are in `src/`. Install the locked
host dependencies with `pip install -r requirements/ci.lock`, ensure Poppler `pdftoppm` is on
`PATH`, then generate both PDFs:

```sh
python scripts/build_reports.py
```

Render and verify every page with:

```sh
python scripts/verify_reports.py
```

The Persian pipeline uses project-bundled Noto Sans Arabic under SIL OFL 1.1.
Because a HarfBuzz binding is not assumed, `build_reports.py` performs a bounded
Arabic/Persian presentation-form shaping pass and visual RTL ordering for the
characters used by the report. The verification script rejects missing text,
unembedded fonts, blank pages, unexpected page counts, and render failures; it
also creates temporary contact sheets under `tmp/pdfs/` for visual inspection.

ReportLab invariant mode makes PDF metadata and file identifiers deterministic.
The generator refreshes `checksums.sha256`, and verification rejects any PDF
whose SHA-256 differs from the manifest. Source changes therefore require an
intentional report rebuild rather than an unexplained binary replacement.

The report describes only retained evidence. `SIMULATED`, `BLOCKED`, `NOT RUN`,
and `A0-UNVERIFIED` labels must not be softened without new direct evidence.
