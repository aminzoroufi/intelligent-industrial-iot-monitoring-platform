# Offline monitoring and ordered replay

The ESP32 continues sensor sampling, aggregation, deterministic threshold
tracking, watchdog service, and health/fault accounting while MQTT or Wi-Fi is
unavailable. New telemetry enters a bounded NVS-backed ring. The default is 32
one-second records; the allowed capacity is 1–32 records so storage consumption
and recovery time remain bounded.

When full, the queue drops exactly one oldest record before adding the newest.
It increments a persistent dropped-message counter and raises
`OFFLINE_QUEUE_DROP`. This favors recent condition evidence while making loss
observable. It is not lossless historian storage.

After reconnect, the communication task publishes the oldest queued record at
QoS 1 before newer records. It preserves message UUID, sequence, measurement,
quality, fault, device time, and uptime fields, changing only `replayed` to
`true`. A record is removed after the MQTT library accepts it for delivery. A
reset at that boundary can republish it, so backend UUID uniqueness is the final
idempotency control. Per-device sequence numbers order records; no ordering is
assumed across devices or MQTT topics.

The retry delay starts at one second, doubles to a 30-second cap, and adds up to
20 percent bounded jitter. A network disconnect forces the low-voltage relay
OFF. Flash-wear lifetime, RF reconnection timing, and behavior during real
brownouts require bench verification; Wokwi cannot establish them.
