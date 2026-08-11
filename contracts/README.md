# MQTT contracts

All application topics use this root:

```text
iiot/v1/{site_id}/{device_id}/telemetry
iiot/v1/{site_id}/{device_id}/health
iiot/v1/{site_id}/{device_id}/events
iiot/v1/{site_id}/{device_id}/commands
iiot/v1/{site_id}/{device_id}/command-acks
iiot/v1/{site_id}/{device_id}/availability
```

`site_id` and `device_id` must match `^[a-z0-9][a-z0-9-]{0,62}$`. Payloads are
UTF-8 JSON and must not exceed 16 KiB. Unknown schema versions, malformed JSON,
oversized payloads, topic/payload identity mismatches, non-finite numbers, and
unknown command kinds are rejected, counted, and recorded without logging
secrets or the complete offending payload.

| Suffix | QoS | Retained | Notes |
| --- | ---: | --- | --- |
| telemetry | 1 | no | duplicates removed by globally unique `message_id` |
| health | 1 | yes | latest bounded snapshot; never contains credentials |
| events | 1 | no | state changes and diagnostics |
| commands | 1 | no | authenticated server origin, short expiry |
| command-acks | 1 | no | one acknowledgement per command attempt |
| availability | 1 | yes | LWT publishes `offline`; successful boot publishes `online` |

## Time and ordering

Timestamps are RFC 3339 UTC. When the device clock is not synchronized,
`device_time` is `null`, `clock_synchronized` is false, and backend receipt time
is the display fallback. The monotonic `sequence` orders messages from one
device across a configuration-preserving reboot. `uptime_ms` may reset and reset
reason is reported in health. No order is assumed across different MQTT topics.

During disconnection, the gateway retains a bounded durable telemetry ring.
Replay is oldest-first with the original `message_id`, `sequence`, and
`device_time`; `replayed` becomes true. If capacity is exhausted, the oldest
telemetry record is dropped, `dropped_message_count` increments, and local
threshold monitoring continues. This deterministic policy preserves the newest
condition evidence while making loss visible.

## Compatibility

Additive optional fields are allowed within version 1. Removing a field,
changing a unit or meaning, relaxing an identity boundary, or changing field
type requires a new schema and topic major version. Consumers ignore unknown
optional properties only when the schema permits them; these schemas otherwise
use `additionalProperties: false` to catch accidental drift.

