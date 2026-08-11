# Verification report

Verification date baseline: 2026-08-11  
Environment: macOS workspace, hardware not supplied  
Repository commit: recorded after each milestone

| Area | Command or inspection | Result | Level | Evidence / reason |
| --- | --- | --- | --- | --- |
| Identity inputs | `rg` placeholder scan | PASS | N/A | No unresolved configured identity tokens found |
| Contracts | `.venv/bin/pytest tests/test_contracts.py -q` | PASS (8 tests) | SIMULATED | Seven positive examples and one clock-sync negative case |
| Contract quality | Ruff and Mypy | PASS | SIMULATED | Format/lint clean; strict typing clean for `contracts` |
| Python services | Ruff, strict Mypy, Pytest | PASS (18 tests) | SIMULATED | Contracts, auth, authorization, ingestion, migration, topic identity, simulator |
| Database migrations | Alembic SQLite upgrade/downgrade test and PostgreSQL startup migration | PASS | SIMULATED | Baseline revision `20260811_0001`; PostgreSQL 18.3 log inspected |
| Software ingestion slice | Compose health + deterministic 12-message MQTT publish + authenticated API query | PASS | SIMULATED | PostgreSQL, Mosquitto, API, and ingestor healthy; API returned 12 rows, newest sequence 10011 |
| Idempotent replay | Republish identical 12-message batch | PASS | SIMULATED | Ingestor logged all messages as duplicate; API count remained 12 |
| ESP32 | Build and host tests | Not run | SIMULATED | Firmware milestone pending |
| STM32 | Build and golden frames | Not run | SIMULATED | Firmware milestone pending |
| Hardware | KiCad ERC/DRC | Not run | SIMULATED | CAD sources not yet implemented |
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
.venv/bin/ruff check contracts services simulator tests conftest.py
.venv/bin/mypy contracts services simulator
```

The same simulator command was executed twice. The first execution inserted 12
rows. The second produced 12 duplicate statuses and no additional rows.
