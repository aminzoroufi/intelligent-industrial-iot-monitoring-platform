# Troubleshooting

## Make exits before running a target on macOS

An unaccepted system Xcode license can prevent `/usr/bin/make` from starting.
Review and accept system licenses yourself if appropriate, or use the equivalent
Docker Compose and Python commands documented in `docs/local-development.md`.
Project setup does not require changing a system-wide agreement.

## Occupied ports

The demo binds only loopback ports 3000, 8000, 1883, and 5432. Stop the conflicting
local service or change the host-side port in `compose.yaml`; do not alter the
container-side service addresses.

## Migration or API startup failure

Inspect `docker compose logs api postgres`. The API runs `alembic upgrade head`
before seeding and serving. A changed database password does not modify an
already initialized volume; use the bounded `make reset-demo` only when losing
local demo data is intended.

## MQTT messages are not persisted

Check that Mosquitto and `mqtt-ingestor` are healthy, then inspect their logs.
The worker rejects payloads over 16 KiB, invalid JSON/schema, invalid topics,
and topic/payload identity mismatches. Duplicate message IDs are accepted as
idempotent duplicates rather than inserted again.

## API returns 401

Obtain a bearer token from `/api/v1/auth/token` using form-encoded OAuth2
password fields. Tokens are audience-bound, expire after 30 minutes by default,
and are invalid after changing `IIOT_JWT_SECRET`.

## Missing WebSocket data

For the dashboard, sign out and back in to refresh the HttpOnly session cookie,
and open the dashboard with a host listed exactly in `IIOT_CORS_ORIGINS`. The
configured WebSocket URL and dashboard URL must use the same hostname so the
host-only cookie is sent; the dashboard normalizes the common local loopback
names. For a non-browser diagnostic client, offer `bearer` and the access token
as subprotocols in that order. Query-string tokens are intentionally rejected.
Then inspect API logs for listener reconnect warnings and ingestor logs for the
corresponding persisted message.

## Missing anomaly model

Open `GET /api/v1/devices/{device_id}/anomaly-model` or the detector-comparison
dashboard. `MODEL_NOT_READY` means no reviewed training window has been
registered; it is not silently replaced with a global model. Confirm the window
has at least `IIOT_ANOMALY_MINIMUM_FEATURE_ROWS` eligible causal rows, no bad
quality or fault flags, and explicit UTC bounds.

For `STALE` or `ERROR`, inspect `docker compose logs anomaly-worker` and the
`error_logs` table. Do not copy downloaded artifacts into `IIOT_MODEL_ROOT`.
Checksum, registry, feature-schema, or scikit-learn version mismatches require a
trusted retrain; deterministic threshold and sensor rules continue meanwhile.
