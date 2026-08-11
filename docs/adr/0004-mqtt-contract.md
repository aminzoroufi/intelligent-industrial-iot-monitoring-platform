# ADR 0004: Versioned MQTT topics and QoS

Status: accepted — 2026-08-11

Topics are rooted at `iiot/v1/{site_id}/{device_id}`. Telemetry, events,
commands, and acknowledgements use QoS 1 so duplicates are expected and removed
by `message_id`. Health uses QoS 1 and may be retained; availability uses a
retained QoS 1 last-will state. Command payloads include an ID and short expiry.
No ordering is assumed across topics, while per-device sequence numbers expose
gaps and replay order within telemetry.

