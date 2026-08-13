# STM32 Modbus RTU sensor node

This focused node targets the STM32F103C8T6 Blue Pill supported by Wokwi. It
does not duplicate gateway networking or storage. A timer schedules a
deterministic ADC fixture, USART2 serves the versioned Modbus RTU map through a
MAX3485-class transceiver, and the independent watchdog covers main-loop
stalls. The implementation uses STM32CubeF1 1.8.6 HAL sources from an external,
exact-version checkout rather than copying vendor code into this repository.

## Build

```sh
git clone --recursive --depth 1 --branch v1.8.6 \
  https://github.com/STMicroelectronics/STM32CubeF1.git /path/to/STM32CubeF1
export STM32CUBE_F1_PATH=/path/to/STM32CubeF1
cmake -S firmware/stm32-modbus-node -B firmware/stm32-modbus-node/build \
  -DCMAKE_TOOLCHAIN_FILE=cmake/arm-none-eabi.cmake
cmake --build firmware/stm32-modbus-node/build --parallel
```

The build emits ELF, HEX, BIN, linker map, and an `arm-none-eabi-size` report.
The compiler, CMake, and STM32Cube checkout are unavailable in the current
environment, so none of those outputs or a target build pass is claimed.

## Timing and fault path

TIM3 interrupts at 10 Hz and only marks a sample due. ADC conversion and
calibration execute in the main loop. USART2 uses 115200 baud, 8 data bits,
even parity, and 1 stop bit; receive-to-idle interrupts hand an eight-byte frame
to the main loop. CRC, address, function, range, and value checks happen in the
same dependency-free core exercised by host tests. Incomplete frames are
discarded and reported as a UART fault.

The ADC fixture maps 0–3.3 V to 20.00–100.00 °C before signed offset and Q15 gain
calibration. Readings within ten ADC counts of a rail are marked out of range.
A missing 500 ms sampling deadline raises `SAMPLE_STALE`. The physical build
refreshes a roughly two-second independent watchdog; Wokwi builds explicitly
disable IWDG because that peripheral is not modeled by the simulator.

Configuration occupies the final 1 KiB flash page and carries a magic value,
schema version, structure size, generation, limits, and CRC-32. Writes erase
and verify that one page. An interrupted write loads safe defaults and exposes
the configuration-fallback fault. Reset count uses the backup domain when
available and is explicitly reduced to a simulated value in Wokwi.

## Wiring

| Function | STM32 pin | MAX3485 / fixture connection | Note |
| --- | --- | --- | --- |
| fixture input | PA0 / ADC1_IN0 | 0–3.3 V potentiometer or conditioned sensor | never exceed MCU rails |
| Modbus TX | PA2 / USART2_TX | DI | 3.3 V logic |
| Modbus RX | PA3 / USART2_RX | RO | 3.3 V logic |
| driver enable | PB1 | DE and active-high `/RE` control | receiver disabled while sending |
| status LED | PC13 | onboard LED | active low on common Blue Pill boards |
| SWD | PA13 / PA14 | SWDIO / SWCLK | retain for recovery/debug |

Place 120 Ω termination only at each physical bus end, not every node. Fit one
known bias network for the whole bus, provide a shared reference conductor,
and add connector-side surge/ESD protection appropriate to the installation.
This is a 3.3 V, low-voltage demonstration and is not an isolated industrial
interface until a documented isolated transceiver/power design is used.
