# Verification report

Verification date baseline: 2026-08-11  
Environment: macOS workspace, hardware not supplied  
Repository commit: recorded after each milestone

| Area | Command or inspection | Result | Level | Evidence / reason |
| --- | --- | --- | --- | --- |
| Identity inputs | `rg` placeholder scan | PASS | N/A | No unresolved configured identity tokens found |
| Contracts | `.venv/bin/pytest tests/test_contracts.py -q` | PASS (8 tests) | SIMULATED | Seven positive examples and one clock-sync negative case |
| Contract quality | Ruff and Mypy | PASS | SIMULATED | Format/lint clean; strict typing clean for `contracts` |
| Python services | Ruff, strict Mypy, Pytest | PASS (27 tests) | SIMULATED | Contracts, auth, authorization, ingestion, operations, migration, topic identity, simulator |
| Database migrations | Alembic SQLite upgrade/downgrade test and PostgreSQL startup migrations | PASS | SIMULATED | Revisions through `20260811_0003`; 64-bit counter migration applied on PostgreSQL 18.3 |
| Software ingestion slice | Compose health + deterministic 12-message MQTT publish + authenticated API query | PASS | SIMULATED | PostgreSQL, Mosquitto, API, and ingestor healthy; API returned 12 rows, newest sequence 10011 |
| Idempotent replay | Republish identical 12-message batch | PASS | SIMULATED | Ingestor logged all messages as duplicate; API count remained 12 |
| Live operations | Authenticated WebSocket + unique MQTT telemetry + threshold alarm | PASS | SIMULATED | Sequence 320002 arrived live; temperature alarm opened; retained health exposed RSSI, queue, reset, and Modbus state |
| Relay command workflow | Authenticated API command through MQTT acknowledgement | PASS | SIMULATED | Relay ON and OFF both reached `completed` with `RELAY_ON` / `RELAY_OFF`; durable audit records persisted |
| WebSocket credential handling | Bearer subprotocol handshake and access-log inspection | PASS | SIMULATED | Negotiated `bearer`; access log contained `/api/v1/ws` with no token in the URL |
| Aggregate Make wrapper | `make check` | BLOCKED | N/A | Host Xcode license is unaccepted; Ruff, Mypy, Pytest, and Compose config commands from the target were each run directly and passed |
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

The operations verification used the OAuth token endpoint, then opened
`/api/v1/ws` with the `bearer, <JWT>` WebSocket subprotocol pair. It published a
unique rising-temperature envelope, observed the live notification and active
alarm, issued relay ON and OFF requests, and matched both command IDs to device
acknowledgements. No physical relay was claimed or tested.
