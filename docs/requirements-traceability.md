# Requirements traceability

Status values are `DESIGNED`, `IMPLEMENTED`, `VERIFIED`, and `BLOCKED`. A design
entry is not evidence that a requirement works.

| ID | Requirement | Code / artifact | Verification | Documentation | Status |
| --- | --- | --- | --- | --- | --- |
| SYS-001 | End-to-end MQTT condition telemetry | `contracts/`, `services/`, `web/` | Compose integration test | `docs/system-overview.md` | DESIGNED |
| SYS-002 | Safe low-voltage relay command | command schema, gateway command task | auth/audit/ack test | `docs/safety.md` | DESIGNED |
| DAT-001 | Versioned SI-unit telemetry envelope | `contracts/schemas/telemetry.v1.schema.json` | `tests/test_contracts.py` (8 passing) | `contracts/README.md` | VERIFIED |
| DAT-002 | Idempotent ordered replay | `message_id`, device sequence | duplicate/replay test | `contracts/README.md` | DESIGNED |
| ESP-001 | Sensor sampling and aggregation | `firmware/esp32-gateway/` | host calculation tests | firmware design guide | DESIGNED |
| ESP-002 | Bounded durable offline queue | `firmware/esp32-gateway/` | queue/replay tests | offline behavior guide | DESIGNED |
| STM-001 | Versioned Modbus RTU node | `firmware/stm32-modbus-node/` | golden frame tests | register map | DESIGNED |
| API-001 | JWT authentication and authorization | `services/api/` | auth tests | API guide | DESIGNED |
| API-002 | Device, alarm, calibration, maintenance APIs | `services/api/` | REST integration tests | OpenAPI and workflows | DESIGNED |
| UI-001 | Accessible responsive operator workflows | `web/` | component and browser tests | dashboard guide | DESIGNED |
| ML-001 | Explainable per-device Isolation Forest | `services/anomaly-worker/` | reproducibility/evaluation tests | anomaly guide | DESIGNED |
| HW-001 | Editable KiCad design and fabrication outputs | `hardware/kicad/`, `hardware/fabrication/` | ERC/DRC/provenance checks | hardware guide | DESIGNED |
| DOC-001 | English and Persian reproducible PDFs | `docs/report/` | render and visual inspection | report build guide | DESIGNED |
| SEC-001 | Secrets, malformed input, replay, CSV, WS threat controls | all modules | security checks | threat model | DESIGNED |

This table is updated at every milestone. `VERIFIED` requires a corresponding
passing row in `docs/verification-report.md`.
