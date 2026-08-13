# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
idf_component_register(
    SRCS
        "app_main.c"
        "gateway_platform.c"
        "provisioning.c"
        "sensor_drivers.c"
        "../../shared/src/iiot_core.c"
    INCLUDE_DIRS
        "."
        "../../shared/include"
    REQUIRES
        app_update
        esp_driver_gpio
        esp_driver_i2c
        esp_driver_spi
        esp_driver_uart
        esp_event
        esp_netif
        esp_timer
        esp_wifi
        mqtt
        nvs_flash
)

target_compile_options(${COMPONENT_LIB} PRIVATE -Wall -Wextra -Werror)
