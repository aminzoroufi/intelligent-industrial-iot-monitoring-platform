# ESP32 Wokwi path

This project selects the ESP32-DevKitC V4 supported by Wokwi and runs the same
gateway tasks and shared C core as the production build. Exact TMP117, INA219,
ADXL345, and RS-485 electrical behavior is not claimed: `CONFIG_IIOT_SIMULATION`
selects a deterministic adapter at the driver boundary while the real register
drivers remain in the source tree.

## Build

With ESP-IDF 6.0.2 exported in the shell:

```sh
cd firmware/esp32-gateway
idf.py set-target esp32
SDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.simulation" idf.py build
```

Open `simulator/wokwi-esp32/diagram.json` with the Wokwi extension. On first
boot, use the serial console before its 120-second deadline:

```text
SET wifi_ssid=Wokwi-GUEST
SET wifi_password=
SET mqtt_host=host.wokwi.internal
SET mqtt_port=1883
COMMIT
```

`host.wokwi.internal` is appropriate only when the Wokwi environment can reach
a broker forwarded from the development host. Do not point the command topic at
an unauthenticated public broker. The serial flow masks password values in its
responses.

After reboot, each short press of **NEXT SYNTHETIC FAULT** advances through
normal, rising temperature, vibration increase, current overload, temperature
driver failure, and Modbus timeout, then returns to normal. Values are formula
driven, not random. Holding that GPIO during boot for ten seconds intentionally
factory-resets NVS, so do not hold it while resetting unless erasure is desired.

No Wokwi execution is claimed in the current verification report: ESP-IDF and
the Wokwi runner were unavailable in the implementation environment. In
particular, simulator timing, Wi-Fi/RF behavior, flash wear, analog fidelity,
and RS-485 electrical behavior remain unverified by Wokwi.
