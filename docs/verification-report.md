# Verification report

Verification date baseline: 2026-08-13 (earlier live rows retained from 2026-08-11)
Environment: macOS workspace, hardware not supplied  
Repository commit: recorded after each milestone

| Area | Command or inspection | Result | Level | Evidence / reason |
| --- | --- | --- | --- | --- |
| Identity inputs | `rg` placeholder scan | PASS | N/A | No unresolved configured identity tokens found |
| Contracts | `.venv/bin/pytest tests/test_contracts.py -q` | PASS (8 tests) | SIMULATED | Seven positive examples and one clock-sync negative case |
| Contract quality | Ruff and Mypy | PASS | SIMULATED | Format/lint clean; strict typing clean for `contracts` |
| Python services | Ruff, strict Mypy, Pytest with branch coverage | PASS (48 tests; 77.90% coverage) | SIMULATED | 50 typed source files; 70% gate; contracts, auth, ingestion, operations, migration, WebSocket, Modbus, simulator, anomaly, gateway, and hardware static paths |
| Database migrations | Alembic SQLite upgrade/downgrade test and PostgreSQL startup migrations | PASS | SIMULATED | SQLite upgrade/downgrade and the fresh PostgreSQL Compose startup both pass through current head `20260811_0004` |
| Software ingestion slice | Compose health + deterministic 12-message MQTT publish + authenticated API query | PASS | SIMULATED | PostgreSQL, Mosquitto, API, and ingestor healthy; API returned 12 rows, newest sequence 10011 |
| Idempotent replay | Republish identical 12-message batch | PASS | SIMULATED | Ingestor logged all messages as duplicate; API count remained 12 |
| Live operations | Authenticated WebSocket + unique MQTT telemetry + threshold alarm | PASS | SIMULATED | Sequence 320002 arrived live; temperature alarm opened; retained health exposed RSSI, queue, reset, and Modbus state |
| Relay command workflow | Authenticated API command through MQTT acknowledgement | PASS | SIMULATED | Relay ON and OFF both reached `completed` with `RELAY_ON` / `RELAY_OFF`; durable audit records persisted |
| WebSocket credential handling | Bearer subprotocol handshake and access-log inspection | PASS | SIMULATED | Negotiated `bearer`; access log contained `/api/v1/ws` with no token in the URL |
| Dashboard source quality | ESLint, TypeScript, Vitest, and npm audit | PASS (6 tests; audit 0 vulnerabilities) | SIMULATED | Responsive components, bounded/gapped chart behavior, status text, and loopback-origin policy passed locally and in hosted CI |
| Dashboard production build | `npm --prefix web run build` and container build | PASS | SIMULATED | Source and production-container builds pass with checksum-tracked self-hosted Geist; the rebuilt Compose image reached health locally and in hosted CI |
| Dashboard browser smoke test | Sign-in, fleet SSR/BFF data, console, and viewport inspection | PARTIAL PASS | SIMULATED | Login and seeded fleet rendered with no error overlay, console error, or horizontal overflow |
| Dashboard browser live channel | Cookie-authenticated telemetry and command flow after loopback normalization | PASS | SIMULATED | Local desktop/mobile Playwright passed, followed by a 20-run concurrent stress pass; hosted CI then passed both profiles with the MQTT acknowledgement recorded as `RELAY_OFF` |
| Aggregate Make wrapper | `make check` | BLOCKED | N/A | Host Xcode license is unaccepted; Ruff, Mypy, Pytest, and Compose config commands from the target were each run directly and passed |
| ESP32 shared core | CMake build and CTest | BLOCKED | SIMULATED | Tests cover config/CRC/migration, calculations, hysteresis, queue loss/replay, serialization, topics, and backoff; system compiler is blocked by the unaccepted Xcode license and CMake is absent |
| ESP32 target | ESP-IDF 6.0.2 build and size report | Not run | SIMULATED | ESP-IDF toolchain is not installed in the environment; no build pass or size is claimed |
| ESP32 Wokwi | Deterministic normal/fault/reconnect/replay scenarios | Not run | SIMULATED | Editable project and driver-boundary adapter exist; Wokwi runner unavailable, so no serial capture is fabricated |
| Modbus host simulator | Ruff, strict Mypy, Pytest | PASS (5 tests) | SIMULATED | Exact golden request/response, timeout, bad response CRC, illegal address, stale registers, request CRC rejection, and PTY round trip |
| STM32 shared C protocol | CMake build and golden CTest | BLOCKED | SIMULATED | Compiler/CMake limitation is shared with the ESP32 C tests; authored byte fixtures match the executed Python suite, but no C pass is claimed |
| STM32 target and Wokwi | ARM build, size, timer/ADC/UART/watchdog scenarios | Not run | SIMULATED | ARM GCC, STM32CubeF1 checkout, and Wokwi runner unavailable; IWDG and backup-domain simulator gaps documented |
| Anomaly feature/model quality | Ruff, strict Mypy, Pytest | PASS (8 tests) | SIMULATED | Causal gap-bounded features, healthy gates, deterministic seed, score semantics, reasons, checksum/schema/staleness rejection, registry, scoring, and sensor-rule fallback |
| Anomaly synthetic evaluation | `python -m services.anomaly_worker.main evaluate-demo` | PASS | SIMULATED | Versioned report: model F1 0.7293/FPR 0.0545; deterministic F1 0.6787/FPR 0.0; `field_performance_claimed=false` |
| Anomaly Compose process | Migration, health, DB backlog scoring, dashboard model state | PARTIAL PASS | SIMULATED | Current migration and anomaly-worker health pass in local and hosted Compose; source integration tests pass, while the hosted happy path does not separately assert a new backlog score |
| Hardware source consistency | Generator check and Pytest | PASS (5 tests) | SIMULATED | Canonical design/BOM refs, required protection roles, model checksums, editable-source presence, and fabrication-release guard pass |
| Hardware placement renders | Source-derived SVG inspection | PARTIAL | SIMULATED | SVG board/enclosure review renders are present; local image viewer could not rasterize SVG, so no visual-pass claim is made |
| Hardware KiCad ERC/DRC/routing | KiCad 10.0.4 | BLOCKED | SIMULATED | Tool unavailable; legacy schematic requires KiCad 10 migration, review footprints require datasheet validation, board is intentionally un-routed, and reports say NOT RUN |
| Hardware fabrication/3D outputs | Static generator and provenance inspection | PARTIAL | SIMULATED | BOM, position, outline/drill review files, envelope STEP/STL, checksums, and FreeCAD macro exist; copper release, schematic PDF, component-accurate board STEP, and FreeCAD execution are not claimed |
| Bilingual engineering PDFs | invariant build, pypdf/pdfplumber inspection, Poppler render, contact-sheet review | PASS | SIMULATED | English 18 pages, Persian 18 pages, hardware review 4 pages; embedded fonts, text, page size/count, non-blank render, RTL/Latin samples, and every-page contact sheets passed |
| Dependency/license inventory | `scripts/check_dependency_licenses.py` | PASS (602 rows) | N/A | Exact Python runtime/CI and npm locks have non-missing license metadata; reviewed dispositions and strong-copyleft guard are current |
| Public repository hygiene | `scripts/check_repository_hygiene.py` | PASS | N/A | All eligible public text files passed identity, placeholder, machine-path, local-link, source-SPDX, action-pin, required-artifact, and dashboard-font checksum checks |
| GitHub workflow source and hosted execution | YAML policy checks, CI, and security workflows | PASS | N/A | Three YAML files parse and all actions use full commit SHAs; hosted [CI run 31684474191](https://github.com/aminzoroufi/intelligent-industrial-iot-monitoring-platform/actions/runs/31684474191) and [security run 31684474179](https://github.com/aminzoroufi/intelligent-industrial-iot-monitoring-platform/actions/runs/31684474179) passed on commit `bfdd487` |
| GitHub publication | `gh auth status`, `git push`, remote metadata inspection | PASS | N/A | The configured public repository exists under `aminzoroufi`; `main` was pushed without force, set as the remote default branch, and the requested description and topics were verified. Hosted CI status is reported separately after publication. |
| Bench | Physical procedure | Not run | BENCH-VERIFIED | No physical evidence supplied |
| Field | Validation protocol | Not run | FIELD-VALIDATED | Outside current evidence |

Only an executed pass with retained output may replace a pending or not-run
entry. Hardware-only checks are not counted as passing when skipped.

## Executed backend vertical-slice commands

```sh
IIOT_ENV_FILE=.env.example docker compose --env-file .env.example up --build -d
.venv/bin/python -m simulator.telemetry_generator.main normal \
  --count 12 --interval-s 0 --sequence-start 10000 --session-id compose-e2e
.venv/bin/pytest tests services simulator -q
.venv/bin/pytest tests services simulator -q --cov=contracts --cov=services \
  --cov=simulator --cov-branch --cov-fail-under=70
.venv/bin/ruff check contracts services simulator tests conftest.py
.venv/bin/mypy contracts services simulator
npm --prefix web run lint
npm --prefix web run typecheck
npm --prefix web test
npm --prefix web audit
npm --prefix web run build
npm --prefix web run test:e2e
.venv/bin/python scripts/compose_smoke.py
.venv/bin/python -m services.anomaly_worker.main evaluate-demo
.venv/bin/python scripts/generate_hardware_artifacts.py --check
.venv/bin/python scripts/check_dependency_licenses.py
.venv/bin/python scripts/check_repository_hygiene.py
python scripts/build_reports.py
python scripts/verify_reports.py
```

The same simulator command was executed twice. The first execution inserted 12
rows. The second produced 12 duplicate statuses and no additional rows.

The operations verification used the OAuth token endpoint, then opened
`/api/v1/ws` with the `bearer, <JWT>` WebSocket subprotocol pair. It published a
unique rising-temperature envelope, observed the live notification and active
alarm, issued relay ON and OFF requests, and matched both command IDs to device
acknowledgements. No physical relay was claimed or tested.

The dashboard production image was started with the same Compose stack. Browser
tests signed in through the same-origin backend-for-frontend, rendered the
seeded fleet, observed live telemetry, issued the simulated Force OFF command,
and matched the persisted `RELAY_OFF` acknowledgement. Loopback origins are
normalized without weakening protocol or port checks, and an acknowledgement
that outruns the HTTP 202 response is reconciled from the authoritative audit.
The final path passed locally, in a 20-run concurrent stress test, and in hosted
desktop/mobile Playwright jobs.
