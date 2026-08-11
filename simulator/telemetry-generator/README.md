# Telemetry generator path

The executable package is `simulator/telemetry_generator` because Python module
names cannot contain hyphens. It publishes clearly labeled deterministic
scenarios through MQTT with QoS 1 and waits for each acknowledgement.

