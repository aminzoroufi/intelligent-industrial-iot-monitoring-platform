# Local software development

## Prerequisites

- Docker Engine with Compose v2;
- Python 3.12 through 3.14 for host tools;
- a virtual environment populated with `pip install -e '.[dev]'`.

## Start the backend vertical slice

```sh
cp .env.example .env
make demo
make demo-status
```

If the host's `make` executable is unavailable, the equivalent start command is
`docker compose up --build -d` after creating `.env`; inspect it with
`docker compose ps`.

The five-service slice starts PostgreSQL, Mosquitto, the API, the MQTT ingestor,
and a clearly simulated gateway. The API is served on `http://localhost:8000`,
OpenAPI on `/docs`, Mosquitto on localhost port 1883, and PostgreSQL on localhost
port 5432. These published ports are for local development only.

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

Browser clients open `ws://localhost:8000/api/v1/ws` with two WebSocket
subprotocol values: `bearer` and the access token. Tokens must not be placed in
the WebSocket URL because request URLs are commonly logged. See
`docs/operations-workflows.md` for the exact browser example.

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
only that project's PostgreSQL and Mosquitto named volumes.
