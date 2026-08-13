/*
 * SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
 * SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
 */
#ifndef GATEWAY_PLATFORM_H
#define GATEWAY_PLATFORM_H

#include "iiot_core.h"

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "esp_err.h"

#define IIOT_FIRMWARE_VERSION "0.1.0"
#define IIOT_RELAY_GPIO 27
#define IIOT_STATUS_LED_GPIO 2
#define IIOT_PROVISION_GPIO 0

typedef struct {
    float temperature_c;
    float current_a;
    float vibration_mps2;
    iiot_sensor_status_t temperature_status;
    iiot_sensor_status_t current_status;
    iiot_sensor_status_t vibration_status;
} gateway_sample_t;

typedef void (*gateway_command_handler_t)(const char *payload, size_t length);

esp_err_t gateway_platform_init(void);
void gateway_relay_force_off(void);
void gateway_relay_set(bool enabled);
bool gateway_relay_is_on(void);
bool gateway_factory_reset_requested(void);
uint32_t gateway_reset_count(void);
const char *gateway_reset_reason(void);

bool gateway_config_load(iiot_config_t *config, bool *used_fallback);
bool gateway_config_save(const iiot_config_t *config);
void gateway_config_erase(void);
bool gateway_is_provisioned(const iiot_config_t *config);

bool gateway_offline_load(iiot_offline_queue_t *queue, uint8_t capacity);
bool gateway_offline_push(iiot_offline_queue_t *queue,
                          const iiot_telemetry_t *telemetry);
bool gateway_offline_pop(iiot_offline_queue_t *queue, iiot_telemetry_t *telemetry);
uint64_t gateway_next_sequence(void);

esp_err_t gateway_sensors_init(void);
gateway_sample_t gateway_sensors_read(void);
const char *gateway_modbus_status(void);

esp_err_t gateway_network_start(const iiot_config_t *config,
                                gateway_command_handler_t command_handler);
bool gateway_mqtt_connected(void);
bool gateway_mqtt_publish(const char *suffix, const char *payload, int qos, bool retained);
int gateway_wifi_rssi_dbm(void);
uint64_t gateway_uptime_ms(void);
bool gateway_utc_now(char *output, size_t output_size);
void gateway_make_uuid(char output[37]);
void gateway_network_wait_and_reconnect(void);

bool gateway_serial_provision(iiot_config_t *config, uint32_t timeout_ms);

#endif
