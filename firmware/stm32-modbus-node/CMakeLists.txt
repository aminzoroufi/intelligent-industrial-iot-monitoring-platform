# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
cmake_minimum_required(VERSION 3.22)
project(iiot_stm32_modbus_node VERSION 0.1.0 LANGUAGES C ASM)

if(NOT DEFINED ENV{STM32CUBE_F1_PATH})
    message(FATAL_ERROR "Set STM32CUBE_F1_PATH to an STM32CubeF1 v1.8.6 checkout")
endif()
set(CUBE "$ENV{STM32CUBE_F1_PATH}")
option(IIOT_WOKWI "Disable peripherals not modeled by Wokwi" OFF)

set(CORE_FLAGS
    -mcpu=cortex-m3
    -mthumb
    -ffunction-sections
    -fdata-sections
    -fno-common
    -Wall
    -Wextra
    -Wpedantic
    -Werror
)

add_executable(${PROJECT_NAME}.elf
    Core/Src/main.c
    Core/Src/stm32f1xx_it.c
    ../shared/src/iiot_core.c
    ../shared/src/modbus_node.c
    "${CUBE}/Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal.c"
    "${CUBE}/Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_adc.c"
    "${CUBE}/Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_adc_ex.c"
    "${CUBE}/Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_cortex.c"
    "${CUBE}/Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_flash.c"
    "${CUBE}/Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_flash_ex.c"
    "${CUBE}/Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_gpio.c"
    "${CUBE}/Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_iwdg.c"
    "${CUBE}/Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_pwr.c"
    "${CUBE}/Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_rcc.c"
    "${CUBE}/Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_rcc_ex.c"
    "${CUBE}/Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_tim.c"
    "${CUBE}/Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_uart.c"
    "${CUBE}/Drivers/CMSIS/Device/ST/STM32F1xx/Source/Templates/system_stm32f1xx.c"
    "${CUBE}/Drivers/CMSIS/Device/ST/STM32F1xx/Source/Templates/gcc/startup_stm32f103xb.s"
)

target_include_directories(${PROJECT_NAME}.elf PRIVATE
    Core/Inc
    ../shared/include
    "${CUBE}/Drivers/STM32F1xx_HAL_Driver/Inc"
    "${CUBE}/Drivers/STM32F1xx_HAL_Driver/Inc/Legacy"
    "${CUBE}/Drivers/CMSIS/Device/ST/STM32F1xx/Include"
    "${CUBE}/Drivers/CMSIS/Include"
)
target_compile_definitions(${PROJECT_NAME}.elf PRIVATE USE_HAL_DRIVER STM32F103xB)
if(IIOT_WOKWI)
    target_compile_definitions(${PROJECT_NAME}.elf PRIVATE IIOT_WOKWI=1)
endif()
target_compile_options(${PROJECT_NAME}.elf PRIVATE ${CORE_FLAGS} $<$<COMPILE_LANGUAGE:C>:-std=c11>)
target_link_options(${PROJECT_NAME}.elf PRIVATE
    ${CORE_FLAGS}
    -T${CMAKE_CURRENT_SOURCE_DIR}/STM32F103C8Tx_FLASH.ld
    -specs=nano.specs
    -specs=nosys.specs
    -Wl,--gc-sections
    -Wl,-Map=${PROJECT_NAME}.map
    -Wl,--print-memory-usage
)
target_link_libraries(${PROJECT_NAME}.elf PRIVATE m)

add_custom_command(TARGET ${PROJECT_NAME}.elf POST_BUILD
    COMMAND ${CMAKE_OBJCOPY} -O ihex $<TARGET_FILE:${PROJECT_NAME}.elf>
            ${CMAKE_CURRENT_BINARY_DIR}/${PROJECT_NAME}.hex
    COMMAND ${CMAKE_OBJCOPY} -O binary $<TARGET_FILE:${PROJECT_NAME}.elf>
            ${CMAKE_CURRENT_BINARY_DIR}/${PROJECT_NAME}.bin
    COMMAND ${CMAKE_SIZE} $<TARGET_FILE:${PROJECT_NAME}.elf>
)
