# Third-Party Notices

Third-party packages and container images remain under their own licenses. The
committed `docs/dependency-license-inventory.csv` records all 602 exact Python
runtime and JavaScript lockfile rows, license expressions, scope, and review
disposition. `requirements/python-license-policy.csv` is the reviewed Python
policy input; JavaScript license metadata comes from `web/package-lock.json`.

Core technologies selected at the architecture baseline include ESP-IDF
(Apache-2.0), STM32Cube components (their applicable ST terms), Mosquitto
(EPL-2.0 or EDL-1.0), PostgreSQL (PostgreSQL License), Python (PSF-2.0),
FastAPI (MIT), SQLAlchemy (MIT), Pydantic (MIT), scikit-learn (BSD-3-Clause),
Next.js (MIT), and React (MIT). This summary is informational; exact locked
versions and transitive licenses take precedence.

No third-party binary CAD model is committed. The STEP files named `-envelope`
are project-authored dimensional shapes and their provenance is recorded in
`hardware/model-provenance.csv`.

`docs/report/fonts/NotoSansArabic-Regular.ttf` and
`NotoSansArabic-Bold.ttf` are from the Noto Arabic project, copyright 2022 The
Noto Project Authors, and are distributed under the SIL Open Font License 1.1.
The required copyright and complete license are preserved in
`docs/report/fonts/OFL.txt`. The fonts are embedded into the Persian PDF.

`web/app/fonts/geist-latin.woff2` and `geist-mono-latin.woff2` are unmodified
Geist subsets bundled by the exact locked Next.js 16.2.12 package. Geist is
copyright 2024 The Geist Project Authors and distributed under the SIL Open
Font License 1.1. The required copyright, complete license, source package,
retrieval date, and SHA-256 checksums are preserved in `web/app/fonts/OFL.txt`
and `web/app/fonts/provenance.csv`. They are self-hosted so the dashboard build
does not fetch fonts from a third-party service.
