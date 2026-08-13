# Requirements traceability

Status values are `DESIGNED`, `IMPLEMENTED`, `VERIFIED`, and `BLOCKED`. A design
entry is not evidence that a requirement works.

| ID | Requirement | Code / artifact | Verification | Documentation | Status |
| --- | --- | --- | --- | --- | --- |
| SYS-001 | End-to-end MQTT condition telemetry | `contracts/`, `services/`, `web/` | Backend Compose passed; dashboard sign-in/fleet smoke passed; post-fix live browser run blocked | `docs/system-overview.md`, `docs/dashboard.md` | IMPLEMENTED |
| SYS-002 | Safe low-voltage relay command | command schema, API command service, simulated gateway | unit tests plus live ON/OFF MQTT acknowledgements | `docs/safety.md`, `docs/operations-workflows.md` | VERIFIED |
| DAT-001 | Versioned SI-unit telemetry envelope | `contracts/schemas/telemetry.v1.schema.json` | `tests/test_contracts.py` (8 passing) | `contracts/README.md` | VERIFIED |
| DAT-002 | Idempotent ordered replay | `services/api/app/ingestion.py` | unit collision tests and identical Compose batch replay | `contracts/README.md` | VERIFIED |
| ESP-001 | Sensor sampling and aggregation | `firmware/esp32-gateway/`, `firmware/shared/` | C host tests authored; local compiler blocked | `firmware/esp32-gateway/README.md` | IMPLEMENTED |
| ESP-002 | Bounded durable offline queue | NVS slot journal and shared ring core | queue/loss/replay tests authored; local compiler blocked; power interruption unverified | `docs/offline-behavior.md` | IMPLEMENTED |
| STM-001 | Versioned Modbus RTU node | STM32 HAL target plus shared C protocol and PTY simulator | 5 Python PTY/protocol tests pass; C golden/target builds blocked | `docs/modbus-register-map.md`, `firmware/stm32-modbus-node/README.md` | IMPLEMENTED |
| API-001 | JWT authentication and authorization | `services/api/` | auth tests and authenticated Compose query | API OpenAPI schema | VERIFIED |
| API-002 | Device, alarm, calibration, maintenance APIs | `services/api/` | REST integration tests and Compose workflow | OpenAPI and `docs/operations-workflows.md` | VERIFIED |
| UI-001 | Accessible responsive operator workflows | `web/` | ESLint, TypeScript, 4 component tests, production build, partial browser smoke | `docs/dashboard.md` | IMPLEMENTED |
| ML-001 | Explainable per-device Isolation Forest | `services/anomaly_worker/`, model registry/API, dashboard comparison | 8 causal-feature, artifact, evaluation, registry, scoring, and fallback tests pass | `docs/anomaly-detection.md` | VERIFIED |
| HW-001 | Editable KiCad design and fabrication outputs | canonical design, KiCad review source, BOM, placement, mechanical/provenance sources | 5 static consistency/provenance/release-safety tests pass; ERC/DRC and routing blocked | `hardware/README.md`, `docs/hardware-in-the-loop.md` | IMPLEMENTED |
| SIM-001 | Reproducible named software faults | telemetry generator, Wokwi projects, Modbus PTY | Python scenario/Modbus tests; target Wokwi runs blocked | simulator READMEs and verification report | IMPLEMENTED |
| DOC-001 | English and Persian reproducible PDFs | editable sources, invariant report generator, bundled fonts | both 18-page reports and 4-page hardware review render on every page; contact sheets visually inspected | `docs/report/README.md` | VERIFIED |
| CI-001 | Credential-free hosted quality/security gates | `.github/workflows/`, Dependabot config | YAML, action-pin, command, and hygiene inspection pass; hosted execution awaits publication | `docs/ci.md` | IMPLEMENTED |
| LIC-001 | Dependency attribution and incompatible-license gate | runtime/CI locks, npm lock, Python policy, generated inventory | 602 exact rows; missing/unknown/strong-copyleft policy guards pass | `THIRD_PARTY_NOTICES.md`, `docs/ci.md` | VERIFIED |
| PROV-001 | Binary/CAD asset provenance | model and dashboard-font provenance plus license files | checksum, license, release-guard, and source checks pass | `hardware/README.md`, `THIRD_PARTY_NOTICES.md` | VERIFIED |
| SEC-001 | Secrets, malformed input, replay, CSV, WS threat controls | contracts, services, dashboard BFF, ESP32 command/config paths | validation, authorization, replay, CSV, credential-safe WS tests; ESP32 tests build-blocked | `SECURITY.md`, `docs/operations-workflows.md`, `docs/provisioning.md` | IMPLEMENTED |

This table is updated at every milestone. `VERIFIED` requires a corresponding
passing row in `docs/verification-report.md`.
