# Provisioning and configuration recovery

Provisioning is deliberately local and time-limited. An unprovisioned ESP32
keeps the demo relay OFF and accepts serial input for 120 seconds. Connect a
3.3 V USB/UART interface with the board powered from its documented low-voltage
supply, open the configured console baud rate, and enter one setting per line:

```text
SHOW
SET site_id=workshop-demo
SET device_id=motor-01
SET wifi_ssid=<local SSID>
SET wifi_password=<local password>
SET mqtt_host=<private broker address>
SET mqtt_port=1883
SET sample_interval_ms=100
SET telemetry_interval_ms=1000
COMMIT
```

Plain MQTT port 1883 is only for the isolated local demonstration. A deployment
should use TLS, broker authentication or client certificates, per-device ACLs,
encrypted NVS/flash, and a protected commissioning channel. Do not paste a
production credential into logs, screenshots, issue reports, or this
repository.

`SHOW` masks the Wi-Fi password. `COMMIT` succeeds only after identifier,
endpoint, timing, queue, threshold, hysteresis, schema, and CRC validation. A
timeout or `ABORT` changes nothing. The operator reboots to re-enter the window.

## Factory reset

Remove power from the demonstration actuator first. Hold the provision/reset
button continuously while resetting the ESP32. The device announces that reset
is armed; releasing the button cancels it. Only a continuous ten-second hold
erases the project's NVS namespace and restarts in the unprovisioned safe state.
The action erases Wi-Fi/MQTT settings, sequence reservation metadata, queue
records, and reset counters. It does not erase unrelated devices or host data.

## Corruption and migration

The version-1 configuration contains a schema version and CRC-32. A valid
version-0 public settings structure has an explicit migration path. Unknown,
truncated, or checksum-invalid data is not partially trusted: conservative
defaults load, `CONFIG_FALLBACK` is reported, networking requires provisioning,
and the relay stays OFF. There is no automatic remote factory reset command.
