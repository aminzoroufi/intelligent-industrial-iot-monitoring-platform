/*
 * SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
 * SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
 */
#ifndef SENSOR_DRIVERS_H
#define SENSOR_DRIVERS_H

#include "gateway_platform.h"

#include "driver/i2c_master.h"
#include "driver/spi_master.h"

typedef struct {
    i2c_master_bus_handle_t i2c_bus;
    i2c_master_dev_handle_t tmp117;
    i2c_master_dev_handle_t ina219;
    spi_device_handle_t adxl345;
    uint32_t simulation_step;
    uint8_t simulation_fault;
    bool initialized;
} sensor_context_t;

esp_err_t sensor_drivers_init(sensor_context_t *context);
gateway_sample_t sensor_drivers_read(sensor_context_t *context);
const char *sensor_drivers_modbus_status(void);

#endif
