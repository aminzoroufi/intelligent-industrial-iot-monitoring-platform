# Firmware host tests

These tests compile the exact dependency-free C core used by the ESP32 and STM32
targets. They cover configuration validation/migration/integrity, measurement
aggregation, threshold hysteresis, deterministic queue overflow and replay
order, MQTT topics, contract serialization, reconnect backoff, Modbus register
encoding, CRC/address handling, exceptions, configuration writes, and golden
RTU frames.

```sh
cmake -S firmware/host-tests -B firmware/host-tests/build
cmake --build firmware/host-tests/build --parallel
ctest --test-dir firmware/host-tests/build --output-on-failure
```

Warnings are errors. The local macOS compiler is currently blocked before
invocation by an unaccepted system Xcode license, so a local pass is not
claimed; the same commands are intended for the Linux CI job.
