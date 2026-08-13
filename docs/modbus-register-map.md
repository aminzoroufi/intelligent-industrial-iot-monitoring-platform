# STM32 Modbus RTU register map

Protocol version 1 uses slave address 1 by default, 115200 baud, 8E1, and
standard Modbus CRC-16 (polynomial representation `0xA001`, low CRC byte first).
Function `0x03` reads holding registers; `0x06` writes only the explicitly
writable configuration registers. Multi-register writes and broadcast writes
are not supported.

| Address | Name | Access | Encoding / unit |
| ---: | --- | --- | --- |
| 0 | map version | R | `0x0100` = v1.0 |
| 1 | product identity | R | `0x4949` (`II`) |
| 2 | node address | R/W | 1–247; takes effect after echoed response |
| 3 | firmware version | R | `0x0001` = 0.1 |
| 4 | sensor status | R | 0 good, 1 stale, 2 out of range, 3 ADC error |
| 5 | fault flags | R | bit 0 config fallback, bit 1 ADC range, bit 2 stale, bit 3 UART |
| 6 | fixture temperature | R | signed 0.01 °C |
| 7 | ADC raw | R | 0–4095 counts |
| 8–9 | uptime | R | unsigned 32-bit milliseconds, high word first |
| 10–11 | reset count | R | unsigned 32-bit, high word first |
| 12 | CRC error count | R | low 16 bits |
| 13 | exception count | R | low 16 bits |
| 14–15 | config generation | R | unsigned 32-bit, high word first |
| 16 | calibration offset | R/W | signed 0.01 °C, −5000 to +5000 |
| 17 | calibration gain | R/W | unsigned Q1.15, 16384–65535 |

Reads must request 1–18 registers wholly inside the map. Illegal function,
address, and value exceptions use codes `0x01`, `0x02`, and `0x03`; a flash
persistence failure uses `0x04`. A bad CRC, wrong slave address, incomplete
frame, or timeout receives no RTU response.

## Golden frames

Read registers 0–7 from node 1:

```text
request:  01 03 00 00 00 08 44 0C
response: 01 03 10 01 00 49 49 00 01 00 01 00 00 00 00 10 9A 08 00 A4 0A
```

The response fixture represents 42.50 °C, ADC count 2048, good status, and no
fault flags. Both the C host suite and the executed Python pseudo-terminal suite
assert the exact bytes. Only the Python suite has run in the current environment.
