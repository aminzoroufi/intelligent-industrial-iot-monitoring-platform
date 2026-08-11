# ADR 0002: Sensor and interface selection

Status: accepted — 2026-08-11

The gateway uses a TMP117 temperature sensor and INA219 DC current monitor over
I2C, an ADXL345 accelerometer over SPI with a data-ready interrupt, UART with a
MAX3485-class transceiver for RS-485, and GPIO for the low-voltage relay and
status signals. These parts provide explicit digital interfaces, realistic
register-level production drivers, and a credible low-voltage retrofit demo.
Simulation adapters may replace the electrical device only at compile time and
must preserve units, range, status, and deterministic fault controls.

