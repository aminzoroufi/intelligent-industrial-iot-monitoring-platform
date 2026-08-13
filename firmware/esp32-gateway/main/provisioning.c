/*
 * SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
 * SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
 */
#include "gateway_platform.h"

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "driver/uart.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"

#define PROVISION_UART UART_NUM_0
#define LINE_MAX 256U

#if CONFIG_IIOT_SERIAL_PROVISIONING
static const char *const TAG = "provision";

static bool copy_value(char *destination, size_t capacity, const char *value) {
    const size_t length = strlen(value);
    if (length == 0U || length >= capacity) {
        return false;
    }
    memcpy(destination, value, length + 1U);
    return true;
}

static bool parse_unsigned(const char *value, unsigned long minimum, unsigned long maximum,
                           unsigned long *parsed) {
    char *end = NULL;
    errno = 0;
    const unsigned long result = strtoul(value, &end, 10);
    if (errno != 0 || end == value || *end != '\0' || result < minimum || result > maximum) {
        return false;
    }
    *parsed = result;
    return true;
}

static bool parse_float(const char *value, float minimum, float maximum, float *parsed) {
    char *end = NULL;
    errno = 0;
    const float result = strtof(value, &end);
    if (errno != 0 || end == value || *end != '\0' || result < minimum || result > maximum) {
        return false;
    }
    *parsed = result;
    return true;
}

static bool apply_field(iiot_config_t *config, const char *field, const char *value) {
    unsigned long integer = 0U;
    if (strcmp(field, "site_id") == 0) {
        return copy_value(config->site_id, sizeof(config->site_id), value);
    }
    if (strcmp(field, "device_id") == 0) {
        return copy_value(config->device_id, sizeof(config->device_id), value);
    }
    if (strcmp(field, "wifi_ssid") == 0) {
        return copy_value(config->wifi_ssid, sizeof(config->wifi_ssid), value);
    }
    if (strcmp(field, "wifi_password") == 0) {
        if (strlen(value) >= sizeof(config->wifi_password)) {
            return false;
        }
        (void)snprintf(config->wifi_password, sizeof(config->wifi_password), "%s", value);
        return true;
    }
    if (strcmp(field, "mqtt_host") == 0) {
        return copy_value(config->mqtt_host, sizeof(config->mqtt_host), value);
    }
    if (strcmp(field, "mqtt_port") == 0 && parse_unsigned(value, 1U, 65535U, &integer)) {
        config->mqtt_port = (uint16_t)integer;
        return true;
    }
    if (strcmp(field, "sample_interval_ms") == 0 &&
        parse_unsigned(value, 10U, 1000U, &integer)) {
        config->sample_interval_ms = (uint16_t)integer;
        return true;
    }
    if (strcmp(field, "telemetry_interval_ms") == 0 &&
        parse_unsigned(value, 100U, 60000U, &integer)) {
        config->telemetry_interval_ms = (uint16_t)integer;
        return true;
    }
    if (strcmp(field, "offline_capacity") == 0 &&
        parse_unsigned(value, 1U, IIOT_OFFLINE_CAPACITY_MAX, &integer)) {
        config->offline_capacity = (uint8_t)integer;
        return true;
    }
    struct {
        const char *name;
        float *destination;
        float minimum;
        float maximum;
    } values[] = {{"temperature_warning_c", &config->temperature.warning, -80.0F, 199.0F},
                  {"temperature_critical_c", &config->temperature.critical, -79.0F, 200.0F},
                  {"vibration_warning_mps2", &config->vibration.warning, 0.0F, 1999.0F},
                  {"vibration_critical_mps2", &config->vibration.critical, 0.1F, 2000.0F},
                  {"current_warning_a", &config->current.warning, 0.0F, 9.9F},
                  {"current_critical_a", &config->current.critical, 0.1F, 10.0F},
                  {"hysteresis_percent", &config->temperature.hysteresis_percent, 1.0F,
                   25.0F}};
    for (size_t index = 0; index < sizeof(values) / sizeof(values[0]); ++index) {
        if (strcmp(field, values[index].name) == 0 &&
            parse_float(value, values[index].minimum, values[index].maximum,
                        values[index].destination)) {
            if (strcmp(field, "hysteresis_percent") == 0) {
                config->vibration.hysteresis_percent = config->temperature.hysteresis_percent;
                config->current.hysteresis_percent = config->temperature.hysteresis_percent;
            }
            return true;
        }
    }
    return false;
}

static void show_masked(const iiot_config_t *config) {
    printf("CONFIG site_id=%s device_id=%s wifi_ssid=%s wifi_password=%s mqtt_host=%s "
           "mqtt_port=%u sample_interval_ms=%u telemetry_interval_ms=%u capacity=%u\n",
           config->site_id, config->device_id,
           config->wifi_ssid[0] == '\0' ? "<unset>" : config->wifi_ssid,
           config->wifi_password[0] == '\0' ? "<unset>" : "********", config->mqtt_host,
           (unsigned)config->mqtt_port, (unsigned)config->sample_interval_ms,
           (unsigned)config->telemetry_interval_ms, (unsigned)config->offline_capacity);
}

static bool handle_line(iiot_config_t *config, char *line, bool *complete) {
    if (strcmp(line, "HELP") == 0) {
        puts("Commands: SHOW | SET field=value | COMMIT | ABORT");
        return true;
    }
    if (strcmp(line, "SHOW") == 0) {
        show_masked(config);
        return true;
    }
    if (strcmp(line, "ABORT") == 0) {
        puts("ABORTED; relay remains OFF");
        *complete = true;
        return false;
    }
    if (strcmp(line, "COMMIT") == 0) {
        char error[48];
        iiot_config_finalize(config);
        if (!gateway_is_provisioned(config) ||
            !iiot_config_validate(config, error, sizeof(error))) {
            printf("REJECTED code=%s\n", gateway_is_provisioned(config) ? error
                                                                         : "NOT_PROVISIONED");
            return true;
        }
        if (!gateway_config_save(config)) {
            puts("REJECTED code=NVS_WRITE_FAILED");
            return true;
        }
        puts("SAVED; reboot required");
        *complete = true;
        return true;
    }
    if (strncmp(line, "SET ", 4U) == 0) {
        char *assignment = line + 4U;
        char *separator = strchr(assignment, '=');
        if (separator == NULL || separator == assignment) {
            puts("REJECTED code=INVALID_SET_SYNTAX");
            return true;
        }
        *separator = '\0';
        const char *value = separator + 1U;
        if (!apply_field(config, assignment, value)) {
            puts("REJECTED code=INVALID_FIELD_OR_VALUE");
            return true;
        }
        printf("ACCEPTED field=%s value=%s\n", assignment,
               strstr(assignment, "password") != NULL ? "********" : value);
        return true;
    }
    puts("REJECTED code=UNKNOWN_COMMAND");
    return true;
}

bool gateway_serial_provision(iiot_config_t *config, uint32_t timeout_ms) {
    gateway_relay_force_off();
    if (!uart_is_driver_installed(PROVISION_UART)) {
        if (uart_driver_install(PROVISION_UART, 512, 0, 0, NULL, 0) != ESP_OK) {
            return false;
        }
    }
    puts("IIOT SERIAL PROVISIONING (time limited; relay OFF). Type HELP.");
    const int64_t deadline_us = esp_timer_get_time() + (int64_t)timeout_ms * 1000;
    char line[LINE_MAX];
    size_t used = 0U;
    bool complete = false;
    bool saved = false;
    while (!complete && esp_timer_get_time() < deadline_us) {
        uint8_t character = 0U;
        const int received =
            uart_read_bytes(PROVISION_UART, &character, 1U, pdMS_TO_TICKS(100));
        if (received <= 0) {
            continue;
        }
        if (character == '\r' || character == '\n') {
            if (used == 0U) {
                continue;
            }
            line[used] = '\0';
            saved = handle_line(config, line, &complete) && complete;
            used = 0U;
        } else if (character >= 32U && character < 127U && used < sizeof(line) - 1U) {
            line[used++] = (char)character;
        } else if (used >= sizeof(line) - 1U) {
            used = 0U;
            puts("REJECTED code=LINE_TOO_LONG");
        }
    }
    if (!complete) {
        ESP_LOGW(TAG, "code=PROVISIONING_TIMEOUT timeout_ms=%lu", (unsigned long)timeout_ms);
    }
    gateway_relay_force_off();
    return saved;
}
#else
bool gateway_serial_provision(iiot_config_t *config, uint32_t timeout_ms) {
    (void)config;
    (void)timeout_ms;
    return false;
}
#endif
