# Anomaly detection and model lifecycle

The anomaly subsystem is a comparison detector, not a safety controller and not
a prediction of remaining useful life. Deterministic threshold hysteresis,
sensor-quality flags, impossible-range checks, rate checks, missing data, and
stuck/noisy sensor rules remain authoritative whether or not a statistical model
is ready.

## Causal feature schema

Feature schema version 1 uses a trailing 12-sample window, requires at least six
finite samples, and resets across gaps longer than 30 seconds. No future sample
is used.

| Feature | Unit / interpretation |
| --- | --- |
| temperature level | °C at the current sample |
| temperature slope | °C/min from the causal window |
| temperature variation | population standard deviation in °C |
| current mean and variation | A |
| vibration RMS mean | m/s² |
| vibration peak maximum | m/s² |
| crest-factor mean | dimensionless ratio |
| vibration/current ratio | m/s²/A, denominator bounded away from zero |

Training windows accept only complete `quality=good` telemetry with no fault
flags. A window containing one rejected sample is excluded in full. This is an
explicit healthy-baseline policy, not an assumption that all historical data is
healthy.

## Training and registry

Select and review a healthy window using UTC `received_at` timestamps, then run:

```sh
docker compose exec anomaly-worker python -m services.anomaly_worker.main train \
  --device-id motor-01 \
  --start 2026-08-11T08:00:00Z \
  --end 2026-08-11T09:00:00Z
```

The default gate requires 200 feature rows. Data is split chronologically into
training and validation portions; the estimator uses 200 trees, contamination
`0.02`, one worker, and fixed seed `20260811`. A deterministic model version is
derived from the device, selected interval, schema, contamination, and seed.

The artifact is stored under `IIOT_MODEL_ROOT` and registered in PostgreSQL with
its feature schema, interval, row counts, library version, SHA-256 checksum, and
last-scored time. The API exposes registry metadata at
`GET /api/v1/devices/{device_id}/anomaly-model` but never exposes the internal
artifact path.

Model files are serialized with Joblib. That format can execute code while
loading, so the model root is an administrator-controlled trust boundary: never
place uploaded or untrusted model files there. The worker resolves registry
paths beneath the configured root, verifies the adjacent artifact checksum,
cross-checks it against PostgreSQL, and requires exact feature-schema and
scikit-learn versions before loading.

## Scoring, explanations, and fallback

The raw score is `-IsolationForest.score_samples`, so larger values are more
anomalous. The displayed percentile is the empirical rank against healthy
validation scores. It is not a probability or calibrated confidence.

An explanation identifies up to two features outside the healthy training
window's 1st/99th percentiles, with value and unit. If the estimator detects an
unusual multivariate combination without a univariate tail, the reason says so
without inventing a mechanical diagnosis.

The model states are:

- `model_not_ready`: no registered model; rules continue and a rate-limited
  diagnostic is persisted;
- `ready`: checksum/schema/version checks passed and scoring is enabled;
- `stale`: the artifact exceeds `IIOT_MODEL_STALE_AFTER_DAYS`; retraining is
  required and statistical scoring stops;
- `error`: path, metadata, checksum, or compatibility validation failed; rules
  continue and the failure is visible.

Statistical alarms use source `anomaly`. Independent sensor-rule alarms use
source `sensor_rule`. Threshold alarms keep source `threshold`, so operators can
distinguish all three.

## Reproducible synthetic evaluation

Regenerate the versioned report with:

```sh
.venv/bin/python -m services.anomaly_worker.main evaluate-demo
```

The checked-in evidence is
[`data/demo/anomaly-evaluation.v1.json`](../data/demo/anomaly-evaluation.v1.json).
It contains confusion counts, precision, recall, F1, false-positive rate, and
first detection delay for deterministic normal, temperature, vibration,
current, and stuck-sensor fixtures. The current synthetic Isolation Forest
result is F1 `0.7293` with false-positive rate `0.0545`; the deterministic
threshold-plus-sensor result is F1 `0.6787` with false-positive rate `0.0`.

These numbers compare two algorithms on a seeded fixture. They are not bench or
field performance, do not establish a maintenance interval, and must not be
generalized to real equipment without a separately documented validation
protocol.
