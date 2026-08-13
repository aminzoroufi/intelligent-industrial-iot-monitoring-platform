# ESP32 edge gateway

The gateway targets an ESP32-DevKitC V4 with ESP-IDF 6.0.2. It is organized as
fixed-responsibility FreeRTOS tasks around the dependency-free shared C core.
The relay output is for an extra-low-voltage demonstration load only and is OFF
before NVS, networking, or command processing begins.

## Responsibilities and timing

| Responsibility | Implementation | Default behavior |
| --- | --- | --- |
| sampling | high-priority static task | 100 ms period with `vTaskDelayUntil` |
| vibration interrupt | GPIO ISR to task notification | ISR performs no bus work |
| aggregation | static task and `iiot_sample_window_t` | 1 s mean/RMS/peak/crest window |
| local alarms | shared hysteresis state machine | continues without a network |
| communication | MQTT QoS 1 and durable replay | oldest queued record first |
| storage | NVS config, slot records, metadata CRC | 32 records by default |
| commands | bounded MQTT input queue | identity/expiry/type/range validated |
| health | retained MQTT snapshot | every 10 seconds |
| watchdog | ESP task watchdog | sampling/aggregation/communication enrolled |

The ADXL345 data-ready ISR only notifies the sampling task. TMP117 and INA219
share a 400 kHz I2C bus; ADXL345 uses 5 MHz SPI mode 3. A UART in hardware
half-duplex RS-485 mode polls the focused STM32 node. All measurement fields use
the SI units encoded in the version-1 contracts.

## Pin map

| Function | ESP32 GPIO | Direction / interface | Electrical note |
| --- | ---: | --- | --- |
| TMP117 + INA219 SDA | 21 | I2C bidirectional | 3.3 V pull-ups |
| TMP117 + INA219 SCL | 22 | I2C output | 3.3 V pull-ups |
| ADXL345 MOSI / MISO / SCLK | 23 / 19 / 18 | SPI | 3.3 V only |
| ADXL345 chip select | 5 | output | pull high at reset |
| ADXL345 data ready | 34 | interrupt input | input-only GPIO |
| RS-485 TX / RX / DE | 17 / 16 / 25 | UART half duplex | MAX3485-class 3.3 V transceiver |
| demo relay driver | 27 | output | transistor + flyback; low-voltage load only |
| status LED | 2 | output | board-dependent active level |
| provision / reset | 0 | pulled-up input | 10 s boot hold required for erase |

GPIO0 is a strapping pin. Production hardware must keep its pull-up and button
network compatible with normal boot and make the ten-second reset action
deliberate.

## Configuration and provisioning

The NVS blob has a magic value, schema version, structure size, generation, and
CRC-32. Version 0 has an explicit migration function in the shared core. An
invalid blob loads conservative defaults, raises `CONFIG_FALLBACK`, and keeps
the relay OFF. Unprovisioned firmware exposes only a 120-second serial setup
window. Commands are `SHOW`, `SET field=value`, `COMMIT`, and `ABORT`; secret
values are masked in device responses. See `docs/provisioning.md` for the
operator sequence.

NVS does not by itself make stored Wi-Fi credentials confidential. Enable ESP32
Secure Boot, flash encryption, and NVS encryption with per-device provisioning
for any deployment outside the isolated demonstration.

## Offline queue and sequence durability

Payload records occupy separate NVS keys and compact metadata carries a CRC.
One enqueue writes one slot plus metadata, allowing NVS wear levelling to avoid
rewriting a monolithic queue blob. At capacity, the oldest record is replaced,
the dropped counter increments, and `OFFLINE_QUEUE_DROP` remains visible.
Reconnect replays oldest first with the original UUID and sequence and sets
`replayed=true`; a crash between publish and removal can duplicate a message,
which the backend removes by UUID.

Sequence numbers are reserved in NVS blocks of 256. A reboot can create a gap,
but cannot move the sequence backwards, and avoids a flash commit every second.
This remains a bounded demonstration design; the actual write lifetime needs a
bench workload and flash-vendor endurance calculation.

## Build and host tests

```sh
cd firmware/esp32-gateway
idf.py set-target esp32
idf.py build

cmake -S firmware/host-tests -B firmware/host-tests/build
cmake --build firmware/host-tests/build --parallel
ctest --test-dir firmware/host-tests/build --output-on-failure
```

No target or host C build is marked as passed yet because the available macOS
compiler is blocked by its system Xcode license and ESP-IDF is not installed.
The Linux CI workflow must execute these commands before the milestone can move
from implemented to verified.
