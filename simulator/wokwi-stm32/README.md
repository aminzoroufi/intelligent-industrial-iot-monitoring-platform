# STM32 Wokwi path

The Blue Pill simulation exercises the 10 Hz timer, ADC fixture, GPIO, USART2,
and shared Modbus state. Build it with:

```sh
export STM32CUBE_F1_PATH=/path/to/STM32CubeF1-v1.8.6
cmake -S firmware/stm32-modbus-node \
  -B firmware/stm32-modbus-node/build-wokwi \
  -DCMAKE_TOOLCHAIN_FILE=cmake/arm-none-eabi.cmake \
  -DIIOT_WOKWI=ON
cmake --build firmware/stm32-modbus-node/build-wokwi --parallel
```

The potentiometer defaults to ADC count 2048 and the logic analyzer observes
USART2 TX, RX, and driver enable. Wokwi documents ADC1 as partial and does not
model the independent watchdog, power controller, RTC/backup domain, MAX3485
electrical layer, line termination, or biasing. The Wokwi build therefore
disables IWDG and uses a simulated reset count; these omissions are explicit.

No Wokwi execution or serial trace is claimed because the runner and ARM
toolchain are unavailable in the current environment.
