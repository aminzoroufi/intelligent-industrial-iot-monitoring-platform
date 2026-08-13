# Toolchain versions

Version selection was checked on 2026-08-11 against the linked primary project
sources. Patch versions are locked in their owning manifests or container
references; this table records the architecture baseline.

| Tool | Selected line | Verification source | Rationale |
| --- | --- | --- | --- |
| Python | 3.14.6 | https://www.python.org/downloads/release/python-3146/ | Current stable maintenance release |
| FastAPI | 0.141.1 | https://pypi.org/project/fastapi/ | Current non-prerelease package |
| Pydantic | 2.13.4 | https://pypi.org/project/pydantic/ | Current non-prerelease package |
| SQLAlchemy | 2.0.51 | https://pypi.org/project/SQLAlchemy/ | Current stable 2.0 release; 2.1 was beta |
| psycopg | 3.3.4 | https://pypi.org/project/psycopg/ | Current non-prerelease package |
| Paho MQTT | 2.1.0 | https://pypi.org/project/paho-mqtt/ | Maintained MQTT v5-capable release |
| scikit-learn | 1.9.0 | https://pypi.org/project/scikit-learn/ | Current non-prerelease package |
| Node.js | 24.15.0 | https://nodejs.org/en/about/previous-releases | Active LTS container runtime |
| Next.js | 16.2.12 | https://nextjs.org/blog | Active LTS security release; 16.3 is preview |
| React | 19.2.8 | https://www.npmjs.com/package/react | Exact dashboard runtime lock |
| Mosquitto | 2.1.2 (`2.1.2-alpine` image) | https://mosquitto.org/blog/ and https://hub.docker.com/_/eclipse-mosquitto/tags | Current bug-fix release and exact published official image tag |
| PostgreSQL | 18.3 (`18.3-bookworm` image) | https://www.postgresql.org/developer/roadmap/ and https://hub.docker.com/_/postgres | Current supported major/minor before the scheduled 2026-08-13 update |
| ESP-IDF | 6.0.2 | https://docs.espressif.com/projects/esp-idf/en/stable/esp32/get-started/index.html | Current stable documentation and exact component constraint; target build not yet executed |
| STM32CubeF1 | 1.8.6 | https://www.st.com/en/embedded-software/stm32cubef1.html | Current STM32F1 package selected for an external exact-tag checkout; target build not yet executed |
| KiCad | 10.0.4 | https://www.kicad.org/blog/ | Current stable bug-fix release |
| ReportLab | 4.4.9 | https://pypi.org/project/reportlab/ | Exact reproducible PDF generator lock |
| pip-audit | 2.10.1 | https://pypi.org/project/pip-audit/ | Exact CI vulnerability-audit tool |
| Gitleaks | 8.30.1 | https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1 | Exact binary and Linux x64 SHA-256 pinned in CI |
| `actions/checkout` | 7.0.1 | https://github.com/actions/checkout/releases/tag/v7.0.1 | Full release commit pinned in workflows |
| `actions/setup-python` | 7.0.0 | https://github.com/actions/setup-python/releases/tag/v7.0.0 | Full immutable release commit pinned in workflows |
| `actions/setup-node` | 7.0.0 | https://github.com/actions/setup-node/releases/tag/v7.0.0 | Full immutable release commit pinned in workflows |
| `actions/upload-artifact` | 7.0.1 | https://github.com/actions/upload-artifact/releases/tag/v7.0.1 | Full release commit pinned in workflows |

All Python runtime and JavaScript transitive versions and license expressions
are recorded in `docs/dependency-license-inventory.csv`. Container tags are
exact, but their immutable registry digests are not yet locked and remain a
documented supply-chain improvement. A version is not called verified here
solely because it is familiar; each entry has a dated primary source. GitHub
Action and security-tool selections were rechecked on 2026-08-12.
