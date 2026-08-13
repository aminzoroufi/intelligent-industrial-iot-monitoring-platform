# Local software development

## Prerequisites

- Docker Engine with Compose v2;
- Python 3.12 through 3.14 for host tools;
- a virtual environment populated with `pip install -r requirements/ci.lock`;
- Node.js 24 with `npm ci --prefix web` when running dashboard checks on the
  host.

## Start the backend vertical slice

```sh
cp .env.example .env
make demo
make demo-status
```

If the host's `make` executable is unavailable, the equivalent start command is
`docker compose up --build -d` after creating `.env`; inspect it with
`docker compose ps`.

The seven-service slice starts PostgreSQL, Mosquitto, the API, the MQTT ingestor,
the anomaly worker, a clearly simulated gateway, and the dashboard. Open the dashboard at
`http://localhost:3000`; the API is served on `http://localhost:8000`, OpenAPI
on `/docs`, Mosquitto on localhost port 1883, and PostgreSQL on localhost port
5432. These published ports are for local development only.

The seeded credentials are `demo-admin` and the password shown explicitly in
`.env.example`. They are intentionally public development values, are never a
production recommendation, and must be changed outside the local demo.

## Publish synthetic telemetry

```sh
make scenario-normal
make scenario-temperature
make scenario-vibration
make scenario-current
make scenario-stuck
```

Every line emitted by the generator includes `"synthetic": true`. Reusing the
same scenario session and sequence range intentionally exercises idempotency.

## Exercise authenticated operations

Use the interactive OpenAPI page to obtain a token, inspect fleet state,
acknowledge alarms, record calibration or maintenance, update thresholds, and
issue the demo relay command. The simulated gateway publishes retained health,
starts with its relay state OFF, rejects expired or mismatched commands, and
returns command acknowledgements through MQTT.

The dashboard signs in through its same-origin backend-for-frontend and keeps
the access token in an HttpOnly, SameSite=Strict cookie. Browser JavaScript
cannot read the token. Its direct WebSocket connection is accepted only when
the request Origin exactly matches `IIOT_CORS_ORIGINS`; the API authenticates
the handshake from the HttpOnly cookie. Command-line clients without a browser
Origin can instead offer `bearer` and the access token as WebSocket
subprotocols. Tokens must never be placed in the WebSocket URL because request
URLs are commonly logged. See `docs/operations-workflows.md` for both flows.

## Train and inspect the anomaly comparison

First publish enough normal samples for the default 200-feature-row gate and
review the interval before declaring it healthy:

```sh
.venv/bin/python -m simulator.telemetry_generator.main normal \
  --count 260 --sequence-start 10000 --session-id anomaly-baseline
docker compose exec postgres psql -U iiot_demo -d iiot_demo -c \
  "select min(received_at), max(received_at), count(*) from telemetry where device_id='motor-01';"
make anomaly-train START=2026-08-11T08:00:00Z END=2026-08-11T09:00:00Z
```

Replace the example timestamps with the reviewed query result. The continuously
running worker will score eligible backlog and new rows. The detector-comparison
dashboard shows `MODEL NOT READY`, `READY`, `STALE`, or `ERROR` from the registry
rather than inferring readiness from UI state. See `docs/anomaly-detection.md`.

The reproducible report does not need database credentials:

```sh
.venv/bin/python -m services.anomaly_worker.main evaluate-demo
```

## Quality gate and bounded cleanup

```sh
make check
make clean-demo
```

The exact quality commands behind `make check` are listed in
`docs/verification-report.md` and can be run directly when a host toolchain
prevents Make from starting.

`make clean-demo` removes only containers and the network in the named
`iiot-monitoring-demo` Compose project. `make reset-demo` additionally removes
only that project's PostgreSQL, Mosquitto, and anomaly-model named volumes.
