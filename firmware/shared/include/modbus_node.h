/*
 * SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
 * SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
 */
#ifndef MODBUS_NODE_H
#define MODBUS_NODE_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define MODBUS_NODE_CONFIG_MAGIC UINT32_C(0x4d4f4442)
#define MODBUS_NODE_CONFIG_VERSION 1U
#define MODBUS_NODE_REGISTER_COUNT 18U
#define MODBUS_NODE_MAX_RESPONSE 41U

typedef enum {
    MODBUS_NODE_NO_RESPONSE = 0,
    MODBUS_NODE_RESPONSE,
} modbus_node_result_t;

typedef enum {
    MODBUS_SENSOR_OK = 0,
    MODBUS_SENSOR_STALE = 1,
    MODBUS_SENSOR_OUT_OF_RANGE = 2,
    MODBUS_SENSOR_ADC_ERROR = 3,
} modbus_sensor_status_t;

typedef struct {
    uint32_t magic;
    uint16_t schema_version;
    uint16_t struct_size;
    uint32_t generation;
    uint8_t node_address;
    uint8_t reserved[3];
    int16_t calibration_offset_centi_c;
    uint16_t calibration_gain_q15;
    uint32_t checksum;
} modbus_node_config_t;

typedef bool (*modbus_persist_config_t)(const modbus_node_config_t *config, void *context);

typedef struct {
    modbus_node_config_t config;
    int16_t temperature_centi_c;
    uint16_t adc_raw;
    uint16_t sensor_status;
    uint16_t fault_flags;
    uint32_t uptime_ms;
    uint32_t reset_count;
    uint32_t crc_error_count;
    uint32_t exception_count;
    modbus_persist_config_t persist_config;
    void *persist_context;
} modbus_node_t;

uint16_t modbus_crc16(const uint8_t *data, size_t length);
void modbus_node_config_defaults(modbus_node_config_t *config);
void modbus_node_config_finalize(modbus_node_config_t *config);
bool modbus_node_config_validate(const modbus_node_config_t *config);
void modbus_node_init(modbus_node_t *node, const modbus_node_config_t *config,
                      modbus_persist_config_t persist_config, void *persist_context);
void modbus_node_set_measurement(modbus_node_t *node, uint16_t adc_raw,
                                 int16_t temperature_centi_c,
                                 modbus_sensor_status_t sensor_status, uint16_t fault_flags,
                                 uint32_t uptime_ms, uint32_t reset_count);
modbus_node_result_t modbus_node_handle_request(modbus_node_t *node, const uint8_t *request,
                                                size_t request_length, uint8_t *response,
                                                size_t response_capacity,
                                                size_t *response_length);

#ifdef __cplusplus
}
#endif

#endif
