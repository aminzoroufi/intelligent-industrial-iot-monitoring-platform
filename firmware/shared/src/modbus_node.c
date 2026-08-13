/*
 * SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
 * SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
 */
#include "modbus_node.h"

#include "iiot_core.h"

#include <string.h>

#define MODBUS_FUNCTION_READ_HOLDING 0x03U
#define MODBUS_FUNCTION_WRITE_SINGLE 0x06U
#define MODBUS_EXCEPTION_ILLEGAL_FUNCTION 0x01U
#define MODBUS_EXCEPTION_ILLEGAL_ADDRESS 0x02U
#define MODBUS_EXCEPTION_ILLEGAL_VALUE 0x03U
#define MODBUS_EXCEPTION_DEVICE_FAILURE 0x04U

static void append_crc(uint8_t *frame, size_t length_without_crc) {
    const uint16_t crc = modbus_crc16(frame, length_without_crc);
    frame[length_without_crc] = (uint8_t)crc;
    frame[length_without_crc + 1U] = (uint8_t)(crc >> 8U);
}

uint16_t modbus_crc16(const uint8_t *data, size_t length) {
    uint16_t crc = UINT16_C(0xffff);
    for (size_t index = 0U; index < length; ++index) {
        crc ^= data[index];
        for (uint8_t bit = 0U; bit < 8U; ++bit) {
            crc = (crc & 1U) != 0U ? (crc >> 1U) ^ UINT16_C(0xa001) : crc >> 1U;
        }
    }
    return crc;
}

void modbus_node_config_defaults(modbus_node_config_t *config) {
    memset(config, 0, sizeof(*config));
    config->magic = MODBUS_NODE_CONFIG_MAGIC;
    config->schema_version = MODBUS_NODE_CONFIG_VERSION;
    config->struct_size = (uint16_t)sizeof(*config);
    config->generation = 1U;
    config->node_address = 1U;
    config->calibration_gain_q15 = UINT16_C(32768);
    modbus_node_config_finalize(config);
}

void modbus_node_config_finalize(modbus_node_config_t *config) {
    config->magic = MODBUS_NODE_CONFIG_MAGIC;
    config->schema_version = MODBUS_NODE_CONFIG_VERSION;
    config->struct_size = (uint16_t)sizeof(*config);
    config->checksum = iiot_crc32(config, offsetof(modbus_node_config_t, checksum));
}

bool modbus_node_config_validate(const modbus_node_config_t *config) {
    return config != NULL && config->magic == MODBUS_NODE_CONFIG_MAGIC &&
           config->schema_version == MODBUS_NODE_CONFIG_VERSION &&
           config->struct_size == sizeof(*config) && config->node_address >= 1U &&
           config->node_address <= 247U && config->calibration_offset_centi_c >= -5000 &&
           config->calibration_offset_centi_c <= 5000 &&
           config->calibration_gain_q15 >= UINT16_C(16384) &&
           config->checksum == iiot_crc32(config, offsetof(modbus_node_config_t, checksum));
}

void modbus_node_init(modbus_node_t *node, const modbus_node_config_t *config,
                      modbus_persist_config_t persist_config, void *persist_context) {
    memset(node, 0, sizeof(*node));
    if (modbus_node_config_validate(config)) {
        node->config = *config;
    } else {
        modbus_node_config_defaults(&node->config);
        node->fault_flags = UINT16_C(1) << 0U;
    }
    node->persist_config = persist_config;
    node->persist_context = persist_context;
}

void modbus_node_set_measurement(modbus_node_t *node, uint16_t adc_raw,
                                 int16_t temperature_centi_c,
                                 modbus_sensor_status_t sensor_status, uint16_t fault_flags,
                                 uint32_t uptime_ms, uint32_t reset_count) {
    node->adc_raw = adc_raw;
    node->temperature_centi_c = temperature_centi_c;
    node->sensor_status = (uint16_t)sensor_status;
    node->fault_flags = (uint16_t)((node->fault_flags & 1U) | fault_flags);
    node->uptime_ms = uptime_ms;
    node->reset_count = reset_count;
}

static void registers(const modbus_node_t *node, uint16_t values[MODBUS_NODE_REGISTER_COUNT]) {
    values[0] = UINT16_C(0x0100);
    values[1] = UINT16_C(0x4949);
    values[2] = node->config.node_address;
    values[3] = UINT16_C(0x0001);
    values[4] = node->sensor_status;
    values[5] = node->fault_flags;
    values[6] = (uint16_t)node->temperature_centi_c;
    values[7] = node->adc_raw;
    values[8] = (uint16_t)(node->uptime_ms >> 16U);
    values[9] = (uint16_t)node->uptime_ms;
    values[10] = (uint16_t)(node->reset_count >> 16U);
    values[11] = (uint16_t)node->reset_count;
    values[12] = (uint16_t)node->crc_error_count;
    values[13] = (uint16_t)node->exception_count;
    values[14] = (uint16_t)(node->config.generation >> 16U);
    values[15] = (uint16_t)node->config.generation;
    values[16] = (uint16_t)node->config.calibration_offset_centi_c;
    values[17] = node->config.calibration_gain_q15;
}

static modbus_node_result_t exception_response(modbus_node_t *node, uint8_t address,
                                               uint8_t function, uint8_t exception,
                                               uint8_t *response, size_t response_capacity,
                                               size_t *response_length) {
    if (response_capacity < 5U) {
        *response_length = 0U;
        return MODBUS_NODE_NO_RESPONSE;
    }
    response[0] = address;
    response[1] = function | 0x80U;
    response[2] = exception;
    append_crc(response, 3U);
    *response_length = 5U;
    ++node->exception_count;
    return MODBUS_NODE_RESPONSE;
}

static modbus_node_result_t read_registers(modbus_node_t *node, const uint8_t *request,
                                           uint8_t *response, size_t response_capacity,
                                           size_t *response_length) {
    const uint16_t first = ((uint16_t)request[2] << 8U) | request[3];
    const uint16_t quantity = ((uint16_t)request[4] << 8U) | request[5];
    if (quantity == 0U || quantity > MODBUS_NODE_REGISTER_COUNT) {
        return exception_response(node, request[0], request[1], MODBUS_EXCEPTION_ILLEGAL_VALUE,
                                  response, response_capacity, response_length);
    }
    if (first >= MODBUS_NODE_REGISTER_COUNT || first + quantity > MODBUS_NODE_REGISTER_COUNT) {
        return exception_response(node, request[0], request[1],
                                  MODBUS_EXCEPTION_ILLEGAL_ADDRESS, response,
                                  response_capacity, response_length);
    }
    const size_t length = 5U + (size_t)quantity * 2U;
    if (response_capacity < length) {
        *response_length = 0U;
        return MODBUS_NODE_NO_RESPONSE;
    }
    uint16_t values[MODBUS_NODE_REGISTER_COUNT];
    registers(node, values);
    response[0] = request[0];
    response[1] = MODBUS_FUNCTION_READ_HOLDING;
    response[2] = (uint8_t)(quantity * 2U);
    for (uint16_t offset = 0U; offset < quantity; ++offset) {
        const uint16_t value = values[first + offset];
        response[3U + offset * 2U] = (uint8_t)(value >> 8U);
        response[4U + offset * 2U] = (uint8_t)value;
    }
    append_crc(response, length - 2U);
    *response_length = length;
    return MODBUS_NODE_RESPONSE;
}

static bool write_value_is_valid(uint16_t address, uint16_t value) {
    if (address == 2U) {
        return value >= 1U && value <= 247U;
    }
    if (address == 16U) {
        const int16_t signed_value = (int16_t)value;
        return signed_value >= -5000 && signed_value <= 5000;
    }
    return address == 17U && value >= UINT16_C(16384);
}

static modbus_node_result_t write_register(modbus_node_t *node, const uint8_t *request,
                                           uint8_t *response, size_t response_capacity,
                                           size_t *response_length) {
    const uint16_t address = ((uint16_t)request[2] << 8U) | request[3];
    const uint16_t value = ((uint16_t)request[4] << 8U) | request[5];
    if (address != 2U && address != 16U && address != 17U) {
        return exception_response(node, request[0], request[1],
                                  MODBUS_EXCEPTION_ILLEGAL_ADDRESS, response,
                                  response_capacity, response_length);
    }
    if (!write_value_is_valid(address, value)) {
        return exception_response(node, request[0], request[1], MODBUS_EXCEPTION_ILLEGAL_VALUE,
                                  response, response_capacity, response_length);
    }
    if (response_capacity < 8U) {
        *response_length = 0U;
        return MODBUS_NODE_NO_RESPONSE;
    }
    modbus_node_config_t previous = node->config;
    if (address == 2U) {
        node->config.node_address = (uint8_t)value;
    } else if (address == 16U) {
        node->config.calibration_offset_centi_c = (int16_t)value;
    } else {
        node->config.calibration_gain_q15 = value;
    }
    ++node->config.generation;
    modbus_node_config_finalize(&node->config);
    if (node->persist_config != NULL &&
        !node->persist_config(&node->config, node->persist_context)) {
        node->config = previous;
        return exception_response(node, request[0], request[1], MODBUS_EXCEPTION_DEVICE_FAILURE,
                                  response, response_capacity, response_length);
    }
    memcpy(response, request, 8U);
    *response_length = 8U;
    return MODBUS_NODE_RESPONSE;
}

modbus_node_result_t modbus_node_handle_request(modbus_node_t *node, const uint8_t *request,
                                                size_t request_length, uint8_t *response,
                                                size_t response_capacity,
                                                size_t *response_length) {
    *response_length = 0U;
    if (request_length != 8U || request == NULL || response == NULL) {
        return MODBUS_NODE_NO_RESPONSE;
    }
    const uint16_t expected_crc = modbus_crc16(request, request_length - 2U);
    const uint16_t frame_crc = (uint16_t)request[request_length - 2U] |
                               ((uint16_t)request[request_length - 1U] << 8U);
    if (expected_crc != frame_crc) {
        ++node->crc_error_count;
        return MODBUS_NODE_NO_RESPONSE;
    }
    if (request[0] != node->config.node_address) {
        return MODBUS_NODE_NO_RESPONSE;
    }
    if (request[1] == MODBUS_FUNCTION_READ_HOLDING) {
        return read_registers(node, request, response, response_capacity, response_length);
    }
    if (request[1] == MODBUS_FUNCTION_WRITE_SINGLE) {
        return write_register(node, request, response, response_capacity, response_length);
    }
    return exception_response(node, request[0], request[1], MODBUS_EXCEPTION_ILLEGAL_FUNCTION,
                              response, response_capacity, response_length);
}
