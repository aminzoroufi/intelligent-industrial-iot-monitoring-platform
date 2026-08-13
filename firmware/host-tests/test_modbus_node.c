/*
 * SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
 * SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
 */
#include "modbus_node.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

typedef struct {
    unsigned calls;
    bool succeed;
} persistence_fixture_t;

static bool persist(const modbus_node_config_t *config, void *context) {
    persistence_fixture_t *fixture = context;
    ++fixture->calls;
    return fixture->succeed && modbus_node_config_validate(config);
}

static void add_crc(uint8_t frame[8]) {
    const uint16_t crc = modbus_crc16(frame, 6U);
    frame[6] = (uint8_t)crc;
    frame[7] = (uint8_t)(crc >> 8U);
}

static modbus_node_t node(persistence_fixture_t *fixture) {
    modbus_node_config_t config;
    modbus_node_config_defaults(&config);
    modbus_node_t result;
    modbus_node_init(&result, &config, persist, fixture);
    modbus_node_set_measurement(&result, 2048U, 4250, MODBUS_SENSOR_OK, 0U, 120000U, 3U);
    return result;
}

static void test_config_integrity_and_fallback(void) {
    modbus_node_config_t config;
    modbus_node_config_defaults(&config);
    assert(modbus_node_config_validate(&config));
    config.checksum ^= UINT32_C(1);
    assert(!modbus_node_config_validate(&config));
    modbus_node_t fallback;
    modbus_node_init(&fallback, &config, NULL, NULL);
    assert(fallback.config.node_address == 1U);
    assert((fallback.fault_flags & 1U) != 0U);
}

static void test_read_golden_frame(void) {
    persistence_fixture_t fixture = {0U, true};
    modbus_node_t target = node(&fixture);
    uint8_t request[8] = {1U, 3U, 0U, 0U, 0U, 8U, 0U, 0U};
    add_crc(request);
    const uint8_t expected[] = {1U, 3U, 16U, 1U, 0U, 73U, 73U, 0U, 1U, 0U, 1U,
                                0U, 0U, 0U, 0U, 16U, 154U, 8U, 0U, 164U, 10U};
    uint8_t response[MODBUS_NODE_MAX_RESPONSE];
    size_t response_length = 0U;
    assert(modbus_node_handle_request(&target, request, sizeof(request), response,
                                      sizeof(response), &response_length) ==
           MODBUS_NODE_RESPONSE);
    assert(response_length == sizeof(expected));
    assert(memcmp(response, expected, sizeof(expected)) == 0);
}

static void test_crc_address_and_exception_behavior(void) {
    persistence_fixture_t fixture = {0U, true};
    modbus_node_t target = node(&fixture);
    uint8_t response[MODBUS_NODE_MAX_RESPONSE];
    size_t response_length = 0U;
    uint8_t request[8] = {1U, 3U, 0U, 0U, 0U, 1U, 0U, 0U};
    add_crc(request);
    request[7] ^= 1U;
    assert(modbus_node_handle_request(&target, request, sizeof(request), response,
                                      sizeof(response), &response_length) ==
           MODBUS_NODE_NO_RESPONSE);
    assert(target.crc_error_count == 1U);

    request[0] = 2U;
    add_crc(request);
    assert(modbus_node_handle_request(&target, request, sizeof(request), response,
                                      sizeof(response), &response_length) ==
           MODBUS_NODE_NO_RESPONSE);

    request[0] = 1U;
    request[1] = 4U;
    add_crc(request);
    assert(modbus_node_handle_request(&target, request, sizeof(request), response,
                                      sizeof(response), &response_length) ==
           MODBUS_NODE_RESPONSE);
    const uint8_t expected_exception[] = {1U, 0x84U, 1U, 0x82U, 0xC0U};
    assert(response_length == sizeof(expected_exception));
    assert(memcmp(response, expected_exception, sizeof(expected_exception)) == 0);
}

static void test_write_validation_and_persistence(void) {
    persistence_fixture_t fixture = {0U, true};
    modbus_node_t target = node(&fixture);
    uint8_t response[MODBUS_NODE_MAX_RESPONSE];
    size_t response_length = 0U;
    uint8_t write_address[8] = {1U, 6U, 0U, 2U, 0U, 7U, 0U, 0U};
    add_crc(write_address);
    assert(modbus_node_handle_request(&target, write_address, sizeof(write_address), response,
                                      sizeof(response), &response_length) ==
           MODBUS_NODE_RESPONSE);
    assert(response_length == sizeof(write_address));
    assert(memcmp(response, write_address, sizeof(write_address)) == 0);
    assert(target.config.node_address == 7U);
    assert(fixture.calls == 1U);

    uint8_t invalid_gain[8] = {7U, 6U, 0U, 17U, 0U, 1U, 0U, 0U};
    add_crc(invalid_gain);
    assert(modbus_node_handle_request(&target, invalid_gain, sizeof(invalid_gain), response,
                                      sizeof(response), &response_length) ==
           MODBUS_NODE_RESPONSE);
    assert(response[1] == 0x86U && response[2] == 3U);

    fixture.succeed = false;
    uint8_t offset[8] = {7U, 6U, 0U, 16U, 0U, 25U, 0U, 0U};
    add_crc(offset);
    assert(modbus_node_handle_request(&target, offset, sizeof(offset), response,
                                      sizeof(response), &response_length) ==
           MODBUS_NODE_RESPONSE);
    assert(response[1] == 0x86U && response[2] == 4U);
    assert(target.config.calibration_offset_centi_c == 0);
}

int main(void) {
    test_config_integrity_and_fallback();
    test_read_golden_frame();
    test_crc_address_and_exception_behavior();
    test_write_validation_and_persistence();
    puts("modbus_node_tests: all checks passed");
    return 0;
}
