# ADR 0003: Focused STM32 Modbus RTU sensor node

Status: accepted — 2026-08-11

The ESP32 is the single Modbus RTU master and one STM32F103C8T6-class node is a
slave on a half-duplex 3.3 V RS-485 link. This demonstrates legacy industrial
interoperability without duplicating the gateway. Function codes 0x03 and 0x06
cover versioned measurement reads and constrained configuration writes. The
node validates CRC, address, register range, and timing and returns standard
exception responses.

