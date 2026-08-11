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

The API is served on `http://localhost:8000`, OpenAPI on `/docs`, Mosquitto on
localhost port 1883, and PostgreSQL on localhost port 5432. These published
ports are for local development only.

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

## Quality gate and bounded cleanup

```sh
make check
make clean-demo
```

`make clean-demo` removes only containers and the network in the named
`iiot-monitoring-demo` Compose project. `make reset-demo` additionally removes
only that project's PostgreSQL and Mosquitto named volumes.

