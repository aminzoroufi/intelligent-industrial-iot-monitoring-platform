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
| Next.js | 16.2.11 | https://nextjs.org/blog | Active LTS security release; 16.3 is preview |
| ESP-IDF | stable release line | https://docs.espressif.com/projects/esp-idf/en/stable/ | Final patch is locked when firmware build is exercised |
| KiCad | 10.0.4 | https://www.kicad.org/blog/ | Current stable bug-fix release |

Container image digests and all JavaScript/Python transitive versions will be
recorded after lock files are generated. A version is not called verified here
solely because it is familiar; each entry has a dated primary source.

