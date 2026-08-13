/*
 * SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
 * SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
 */
#include "gateway_platform.h"

#include <ctype.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "cJSON.h"
#include "esp_attr.h"
#include "esp_log.h"
#include "esp_system.h"
#include "esp_task_wdt.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"
#include "freertos/task.h"

#define COMMAND_PAYLOAD_MAX 2048U
#define REBOOT_GUARD_MAGIC UINT32_C(0x52424744)

typedef struct {
    char bytes[COMMAND_PAYLOAD_MAX];
    size_t length;
} command_input_t;

static const char *const TAG = "gateway";
static iiot_config_t config;
static iiot_offline_queue_t offline_queue;
static QueueHandle_t sample_queue;
static QueueHandle_t telemetry_queue;
static QueueHandle_t command_queue;
static SemaphoreHandle_t offline_mutex;
static esp_timer_handle_t relay_timer;
static atomic_uint_fast32_t active_faults;
static bool relay_locked;

RTC_NOINIT_ATTR static uint32_t reboot_guard_magic;
RTC_NOINIT_ATTR static uint32_t consecutive_reboots;

static StaticQueue_t sample_queue_state;
static StaticQueue_t telemetry_queue_state;
static StaticQueue_t command_queue_state;
static uint8_t sample_queue_storage[32U * sizeof(gateway_sample_t)];
static uint8_t telemetry_queue_storage[8U * sizeof(iiot_telemetry_t)];
static uint8_t command_queue_storage[4U * sizeof(command_input_t)];
static StaticSemaphore_t offline_mutex_state;

static StaticTask_t sampling_task_state;
static StaticTask_t aggregation_task_state;
static StaticTask_t communication_task_state;
static StaticTask_t command_task_state;
static StaticTask_t health_task_state;
static StaticTask_t network_task_state;
static StaticTask_t stability_task_state;
static StackType_t sampling_stack[1536];
static StackType_t aggregation_stack[2048];
static StackType_t communication_stack[2304];
static StackType_t command_stack[2304];
static StackType_t health_stack[2048];
static StackType_t network_stack[1536];
static StackType_t stability_stack[768];

static void set_fault(uint32_t flag, bool active) {
    if (active) {
        (void)atomic_fetch_or(&active_faults, flag);
    } else {
        (void)atomic_fetch_and(&active_faults, ~flag);
    }
}

static bool uuid_is_valid(const char *value) {
    if (value == NULL || strlen(value) != 36U) {
        return false;
    }
    for (size_t index = 0U; index < 36U; ++index) {
        if (index == 8U || index == 13U || index == 18U || index == 23U) {
            if (value[index] != '-') {
                return false;
            }
        } else if (!isxdigit((unsigned char)value[index])) {
            return false;
        }
    }
    return true;
}

static bool utc_value_is_valid(const char *value) {
    if (value == NULL) {
        return false;
    }
    const size_t length = strlen(value);
    if (length < 20U || length > 30U || value[4] != '-' || value[7] != '-' ||
        value[10] != 'T' || value[13] != ':' || value[16] != ':' || value[length - 1U] != 'Z') {
        return false;
    }
    for (size_t index = 0U; index < 19U; ++index) {
        if (index != 4U && index != 7U && index != 10U && index != 13U && index != 16U &&
            !isdigit((unsigned char)value[index])) {
            return false;
        }
    }
    if (length > 20U) {
        if (length < 22U) {
            return false;
        }
        if (value[19] != '.') {
            return false;
        }
        for (size_t index = 20U; index < length - 1U; ++index) {
            if (!isdigit((unsigned char)value[index])) {
                return false;
            }
        }
    }
    return true;
}

static bool utc_expired(const char now[32], const char *expires_at) {
    const int seconds_comparison = strncmp(now, expires_at, 19U);
    return seconds_comparison > 0 ||
           (seconds_comparison == 0 && expires_at[19] == 'Z');
}

static const char *firmware_version(void) {
#if CONFIG_IIOT_SIMULATION
    return IIOT_FIRMWARE_VERSION "-sim";
#else
    return IIOT_FIRMWARE_VERSION;
#endif
}

static const char *json_time(char storage[32]) {
    if (gateway_utc_now(storage, 32U)) {
        char formatted[36];
        (void)snprintf(formatted, sizeof(formatted), "\"%s\"", storage);
        (void)snprintf(storage, 32U, "%s", formatted);
        return storage;
    }
    return "null";
}

static void append_fault_names(char *output, size_t capacity, uint32_t flags) {
    static const struct {
        uint32_t flag;
        const char *name;
    } names[] = {{IIOT_FAULT_TEMPERATURE_SENSOR, "TEMPERATURE_SENSOR_FAULT"},
                 {IIOT_FAULT_CURRENT_SENSOR, "CURRENT_SENSOR_FAULT"},
                 {IIOT_FAULT_VIBRATION_SENSOR, "VIBRATION_SENSOR_FAULT"},
                 {IIOT_FAULT_MODBUS, "MODBUS_FAULT"},
                 {IIOT_FAULT_CONFIG_FALLBACK, "CONFIG_FALLBACK"},
                 {IIOT_FAULT_OFFLINE_QUEUE_DROP, "OFFLINE_QUEUE_DROP"},
                 {IIOT_FAULT_REBOOT_LOOP_GUARD, "REBOOT_LOOP_GUARD"}};
    size_t used = 0U;
    bool first = true;
    output[used++] = '[';
    output[used] = '\0';
    for (size_t index = 0U; index < sizeof(names) / sizeof(names[0]); ++index) {
        if ((flags & names[index].flag) == 0U) {
            continue;
        }
        const int written = snprintf(output + used, capacity - used, "%s\"%s\"",
                                     first ? "" : ",", names[index].name);
        if (written < 0 || (size_t)written >= capacity - used) {
            break;
        }
        used += (size_t)written;
        first = false;
    }
    if (used + 2U <= capacity) {
        output[used++] = ']';
        output[used] = '\0';
    }
}

static void publish_command_ack(const char *command_id, const char *status,
                                const char *result_code) {
    char message_id[37];
    char time_value[32];
    char payload[768];
    gateway_make_uuid(message_id);
    (void)snprintf(payload, sizeof(payload),
                   "{\"schema_version\":1,\"message_id\":\"%s\","
                   "\"command_id\":\"%s\",\"site_id\":\"%s\","
                   "\"device_id\":\"%s\",\"device_time\":%s,\"status\":\"%s\","
                   "\"result_code\":\"%s\",\"detail\":null,\"relay_on\":%s}",
                   message_id, command_id, config.site_id, config.device_id,
                   json_time(time_value), status, result_code,
                   gateway_relay_is_on() ? "true" : "false");
    (void)gateway_mqtt_publish("command-acks", payload, 1, false);
}

static void relay_timeout(void *argument) {
    (void)argument;
    gateway_relay_force_off();
    ESP_LOGW(TAG, "code=RELAY_AUTO_OFF relay=off");
}

static void mqtt_command_received(const char *payload, size_t length) {
    if (length == 0U || length >= COMMAND_PAYLOAD_MAX) {
        ESP_LOGW(TAG, "code=COMMAND_REJECTED reason=PAYLOAD_SIZE");
        return;
    }
    command_input_t input = {.length = length};
    memcpy(input.bytes, payload, length);
    input.bytes[length] = '\0';
    if (xQueueSend(command_queue, &input, 0U) != pdPASS) {
        ESP_LOGW(TAG, "code=COMMAND_REJECTED reason=QUEUE_FULL");
    }
}

static void command_task(void *argument) {
    (void)argument;
    command_input_t input;
    for (;;) {
        if (xQueueReceive(command_queue, &input, portMAX_DELAY) != pdPASS) {
            continue;
        }
        cJSON *root = cJSON_ParseWithLength(input.bytes, input.length);
        if (root == NULL || !cJSON_IsObject(root)) {
            cJSON_Delete(root);
            ESP_LOGW(TAG, "code=COMMAND_REJECTED reason=INVALID_JSON");
            continue;
        }
        const cJSON *command_id = cJSON_GetObjectItemCaseSensitive(root, "command_id");
        const cJSON *schema_version =
            cJSON_GetObjectItemCaseSensitive(root, "schema_version");
        const cJSON *site_id = cJSON_GetObjectItemCaseSensitive(root, "site_id");
        const cJSON *device_id = cJSON_GetObjectItemCaseSensitive(root, "device_id");
        const cJSON *expires_at = cJSON_GetObjectItemCaseSensitive(root, "expires_at");
        const cJSON *kind = cJSON_GetObjectItemCaseSensitive(root, "kind");
        const cJSON *parameters = cJSON_GetObjectItemCaseSensitive(root, "parameters");
        if (!cJSON_IsNumber(schema_version) || schema_version->valuedouble != 1.0 ||
            !cJSON_IsString(command_id) || !uuid_is_valid(command_id->valuestring)) {
            cJSON_Delete(root);
            ESP_LOGW(TAG, "code=COMMAND_REJECTED reason=COMMAND_ID_INVALID");
            continue;
        }
        if (!cJSON_IsString(site_id) || !cJSON_IsString(device_id) ||
            strcmp(site_id->valuestring, config.site_id) != 0 ||
            strcmp(device_id->valuestring, config.device_id) != 0) {
            publish_command_ack(command_id->valuestring, "rejected", "IDENTITY_MISMATCH");
            cJSON_Delete(root);
            continue;
        }
        char now[32];
        if (!cJSON_IsString(expires_at) || !utc_value_is_valid(expires_at->valuestring) ||
            !gateway_utc_now(now, sizeof(now))) {
            publish_command_ack(command_id->valuestring, "failed", "CLOCK_UNSYNCHRONIZED");
            cJSON_Delete(root);
            continue;
        }
        if (utc_expired(now, expires_at->valuestring)) {
            publish_command_ack(command_id->valuestring, "expired", "COMMAND_EXPIRED");
            cJSON_Delete(root);
            continue;
        }
        if (!cJSON_IsString(kind) || strcmp(kind->valuestring, "set_demo_relay") != 0) {
            publish_command_ack(command_id->valuestring, "rejected", "UNSUPPORTED_COMMAND");
            cJSON_Delete(root);
            continue;
        }
        if (relay_locked) {
            publish_command_ack(command_id->valuestring, "rejected",
                                "RELAY_LOCKED_REBOOT_GUARD");
            cJSON_Delete(root);
            continue;
        }
        const cJSON *relay = cJSON_GetObjectItemCaseSensitive(parameters, "relay_on");
        const cJSON *timeout = cJSON_GetObjectItemCaseSensitive(parameters, "timeout_s");
        if (!cJSON_IsObject(parameters) || cJSON_GetArraySize(parameters) != 2 ||
            !cJSON_IsBool(relay) || !cJSON_IsNumber(timeout) ||
            timeout->valuedouble < 1.0 || timeout->valuedouble > 30.0 ||
            timeout->valuedouble != (double)(int)timeout->valuedouble) {
            publish_command_ack(command_id->valuestring, "rejected", "PARAMETERS_INVALID");
            cJSON_Delete(root);
            continue;
        }
        (void)esp_timer_stop(relay_timer);
        const bool enabled = cJSON_IsTrue(relay);
        gateway_relay_set(enabled);
        if (enabled) {
            (void)esp_timer_start_once(relay_timer,
                                       (uint64_t)(int)timeout->valuedouble * 1000000U);
        }
        publish_command_ack(command_id->valuestring, "completed",
                            enabled ? "RELAY_ON" : "RELAY_OFF");
        ESP_LOGI(TAG, "code=COMMAND_APPLIED kind=set_demo_relay relay=%s",
                 enabled ? "on" : "off");
        cJSON_Delete(root);
    }
}

static void publish_threshold_event(const char *metric, iiot_threshold_state_t state,
                                    float value) {
    char message_id[37];
    char time_value[32];
    char payload[896];
    const char *severity = state == IIOT_THRESHOLD_CRITICAL
                               ? "critical"
                               : state == IIOT_THRESHOLD_WARNING ? "warning" : "info";
    const char *event_state = state == IIOT_THRESHOLD_NORMAL ? "cleared" : "active";
    gateway_make_uuid(message_id);
    (void)snprintf(payload, sizeof(payload),
                   "{\"schema_version\":1,\"message_id\":\"%s\","
                   "\"site_id\":\"%s\",\"device_id\":\"%s\",\"sequence\":%llu,"
                   "\"device_time\":%s,\"event_code\":\"%s_THRESHOLD\","
                   "\"severity\":\"%s\",\"state\":\"%s\","
                   "\"summary\":\"%s threshold state changed.\",\"synthetic\":%s,"
                   "\"details\":{\"value\":%.5g}}",
                   message_id, config.site_id, config.device_id,
                   (unsigned long long)gateway_next_sequence(), json_time(time_value), metric,
                   severity, event_state, metric,
#if CONFIG_IIOT_SIMULATION
                   "true",
#else
                   "false",
#endif
                   (double)value);
    (void)gateway_mqtt_publish("events", payload, 1, false);
}

static void sampling_task(void *argument) {
    (void)argument;
    ESP_ERROR_CHECK(esp_task_wdt_add(NULL));
    TickType_t wake = xTaskGetTickCount();
    for (;;) {
        const gateway_sample_t sample = gateway_sensors_read();
        if (xQueueSend(sample_queue, &sample, 0U) != pdPASS) {
            ESP_LOGW(TAG, "code=SAMPLE_QUEUE_FULL");
        }
        ESP_ERROR_CHECK(esp_task_wdt_reset());
        xTaskDelayUntil(&wake, pdMS_TO_TICKS(config.sample_interval_ms));
    }
}

static void fill_sensor_faults(const iiot_measurements_t *measurements) {
    set_fault(IIOT_FAULT_TEMPERATURE_SENSOR,
              measurements->temperature_quality.status != IIOT_SENSOR_GOOD);
    set_fault(IIOT_FAULT_CURRENT_SENSOR,
              measurements->current_quality.status != IIOT_SENSOR_GOOD);
    set_fault(IIOT_FAULT_VIBRATION_SENSOR,
              measurements->vibration_quality.status != IIOT_SENSOR_GOOD);
    set_fault(IIOT_FAULT_MODBUS, strcmp(gateway_modbus_status(), "ok") != 0);
}

static void aggregation_task(void *argument) {
    (void)argument;
    ESP_ERROR_CHECK(esp_task_wdt_add(NULL));
    const uint16_t expected = config.telemetry_interval_ms / config.sample_interval_ms;
    iiot_sample_window_t window;
    iiot_sample_window_begin(&window, expected);
    uint16_t samples = 0U;
    iiot_threshold_state_t temperature_state = IIOT_THRESHOLD_NORMAL;
    iiot_threshold_state_t vibration_state = IIOT_THRESHOLD_NORMAL;
    iiot_threshold_state_t current_state = IIOT_THRESHOLD_NORMAL;
    for (;;) {
        gateway_sample_t sample;
        if (xQueueReceive(sample_queue, &sample, portMAX_DELAY) != pdPASS) {
            continue;
        }
        iiot_sample_window_add(&window, sample.temperature_c, sample.temperature_status,
                               sample.current_a, sample.current_status, sample.vibration_mps2,
                               sample.vibration_status);
        if (++samples < expected) {
            ESP_ERROR_CHECK(esp_task_wdt_reset());
            continue;
        }
        iiot_telemetry_t telemetry = {0};
        gateway_make_uuid(telemetry.message_id);
        (void)snprintf(telemetry.site_id, sizeof(telemetry.site_id), "%s", config.site_id);
        (void)snprintf(telemetry.device_id, sizeof(telemetry.device_id), "%s",
                       config.device_id);
        (void)snprintf(telemetry.firmware_version, sizeof(telemetry.firmware_version), "%s",
                       firmware_version());
        telemetry.sequence = gateway_next_sequence();
        telemetry.uptime_ms = gateway_uptime_ms();
        telemetry.clock_synchronized =
            gateway_utc_now(telemetry.device_time, sizeof(telemetry.device_time));
        telemetry.measurements = iiot_sample_window_finish(&window);
        fill_sensor_faults(&telemetry.measurements);
        telemetry.fault_flags = (uint32_t)atomic_load(&active_faults);

        const iiot_threshold_state_t next_temperature = iiot_threshold_update(
            &config.temperature, temperature_state, telemetry.measurements.temperature_c,
            telemetry.measurements.temperature_quality.status == IIOT_SENSOR_GOOD);
        const iiot_threshold_state_t next_vibration = iiot_threshold_update(
            &config.vibration, vibration_state, telemetry.measurements.vibration_rms_mps2,
            telemetry.measurements.vibration_quality.status == IIOT_SENSOR_GOOD);
        const iiot_threshold_state_t next_current = iiot_threshold_update(
            &config.current, current_state, telemetry.measurements.current_a,
            telemetry.measurements.current_quality.status == IIOT_SENSOR_GOOD);
        if (next_temperature != temperature_state) {
            publish_threshold_event("TEMPERATURE", next_temperature,
                                    telemetry.measurements.temperature_c);
            temperature_state = next_temperature;
        }
        if (next_vibration != vibration_state) {
            publish_threshold_event("VIBRATION", next_vibration,
                                    telemetry.measurements.vibration_rms_mps2);
            vibration_state = next_vibration;
        }
        if (next_current != current_state) {
            publish_threshold_event("CURRENT", next_current,
                                    telemetry.measurements.current_a);
            current_state = next_current;
        }
        if (xQueueSend(telemetry_queue, &telemetry, pdMS_TO_TICKS(50)) != pdPASS) {
            xSemaphoreTake(offline_mutex, portMAX_DELAY);
            const uint32_t before = offline_queue.dropped_message_count;
            (void)gateway_offline_push(&offline_queue, &telemetry);
            if (offline_queue.dropped_message_count != before) {
                set_fault(IIOT_FAULT_OFFLINE_QUEUE_DROP, true);
            }
            xSemaphoreGive(offline_mutex);
        }
        samples = 0U;
        iiot_sample_window_begin(&window, expected);
        ESP_ERROR_CHECK(esp_task_wdt_reset());
    }
}

static bool publish_telemetry(iiot_telemetry_t *telemetry) {
    char payload[IIOT_JSON_MAX];
    return iiot_serialize_telemetry(telemetry, payload, sizeof(payload)) &&
           gateway_mqtt_publish("telemetry", payload, 1, false);
}

static void communication_task(void *argument) {
    (void)argument;
    ESP_ERROR_CHECK(esp_task_wdt_add(NULL));
    for (;;) {
        if (gateway_mqtt_connected()) {
            for (;;) {
                iiot_telemetry_t replay;
                xSemaphoreTake(offline_mutex, portMAX_DELAY);
                const bool available = iiot_offline_queue_peek(&offline_queue, &replay);
                xSemaphoreGive(offline_mutex);
                if (!available) {
                    break;
                }
                replay.replayed = true;
                if (!publish_telemetry(&replay)) {
                    break;
                }
                xSemaphoreTake(offline_mutex, portMAX_DELAY);
                iiot_telemetry_t removed;
                const bool removed_ok = gateway_offline_pop(&offline_queue, &removed);
                xSemaphoreGive(offline_mutex);
                if (!removed_ok) {
                    break;
                }
            }
        }
        iiot_telemetry_t telemetry;
        if (xQueueReceive(telemetry_queue, &telemetry, pdMS_TO_TICKS(250)) == pdPASS &&
            !publish_telemetry(&telemetry)) {
            xSemaphoreTake(offline_mutex, portMAX_DELAY);
            const uint32_t before = offline_queue.dropped_message_count;
            (void)gateway_offline_push(&offline_queue, &telemetry);
            if (offline_queue.dropped_message_count != before) {
                set_fault(IIOT_FAULT_OFFLINE_QUEUE_DROP, true);
            }
            xSemaphoreGive(offline_mutex);
        }
        ESP_ERROR_CHECK(esp_task_wdt_reset());
    }
}

static void health_task(void *argument) {
    (void)argument;
    for (;;) {
        const uint32_t flags = (uint32_t)atomic_load(&active_faults);
        char fault_names[320];
        char message_id[37];
        char time_value[32];
        char payload[1280];
        append_fault_names(fault_names, sizeof(fault_names), flags);
        gateway_make_uuid(message_id);
        xSemaphoreTake(offline_mutex, portMAX_DELAY);
        const uint8_t queue_depth = offline_queue.count;
        const uint32_t dropped = offline_queue.dropped_message_count;
        xSemaphoreGive(offline_mutex);
        const bool degraded = flags != 0U || queue_depth > 0U ||
                              strcmp(gateway_modbus_status(), "ok") != 0;
        (void)snprintf(payload, sizeof(payload),
                       "{\"schema_version\":1,\"message_id\":\"%s\","
                       "\"site_id\":\"%s\",\"device_id\":\"%s\",\"sequence\":%llu,"
                       "\"device_time\":%s,\"uptime_ms\":%llu,"
                       "\"firmware_version\":\"%s\",\"status\":\"%s\","
                       "\"rssi_dbm\":%d,\"reset_reason\":\"%s\",\"reset_count\":%lu,"
                       "\"queue_depth\":%u,\"queue_capacity\":%u,"
                       "\"dropped_message_count\":%lu,\"modbus_status\":\"%s\","
                       "\"active_faults\":%s}",
                       message_id, config.site_id, config.device_id,
                       (unsigned long long)gateway_next_sequence(), json_time(time_value),
                       (unsigned long long)gateway_uptime_ms(), firmware_version(),
                       degraded ? "degraded" : "online", gateway_wifi_rssi_dbm(),
                       gateway_reset_reason(), (unsigned long)gateway_reset_count(),
                       (unsigned)queue_depth, (unsigned)offline_queue.capacity,
                       (unsigned long)dropped, gateway_modbus_status(), fault_names);
        (void)gateway_mqtt_publish("health", payload, 1, true);
        vTaskDelay(pdMS_TO_TICKS(10000));
    }
}

static void network_task(void *argument) {
    (void)argument;
    gateway_network_wait_and_reconnect();
}

static void stability_task(void *argument) {
    (void)argument;
    vTaskDelay(pdMS_TO_TICKS(60000));
    consecutive_reboots = 0U;
    relay_locked = false;
    set_fault(IIOT_FAULT_REBOOT_LOOP_GUARD, false);
    ESP_LOGI(TAG, "code=REBOOT_GUARD_CLEARED stable_ms=60000");
    vTaskDelete(NULL);
}

static void initialize_reboot_guard(void) {
    if (reboot_guard_magic != REBOOT_GUARD_MAGIC || esp_reset_reason() == ESP_RST_POWERON) {
        reboot_guard_magic = REBOOT_GUARD_MAGIC;
        consecutive_reboots = 1U;
    } else if (consecutive_reboots < UINT32_MAX) {
        ++consecutive_reboots;
    }
    relay_locked = consecutive_reboots >= 3U;
    set_fault(IIOT_FAULT_REBOOT_LOOP_GUARD, relay_locked);
    if (relay_locked) {
        ESP_LOGE(TAG, "code=REBOOT_LOOP_GUARD relay=locked count=%lu",
                 (unsigned long)consecutive_reboots);
    }
}

void app_main(void) {
    ESP_ERROR_CHECK(gateway_platform_init());
    gateway_relay_force_off();
    if (gateway_factory_reset_requested()) {
        ESP_LOGW(TAG, "code=FACTORY_RESET_CONFIRMED");
        gateway_config_erase();
        esp_restart();
    }
    initialize_reboot_guard();
    bool used_fallback = false;
    (void)gateway_config_load(&config, &used_fallback);
    set_fault(IIOT_FAULT_CONFIG_FALLBACK, used_fallback);
    if (used_fallback) {
        ESP_LOGE(TAG, "code=CONFIG_FALLBACK reason=validation relay=off");
    }
    if (!gateway_is_provisioned(&config)) {
        const bool saved = gateway_serial_provision(&config, 120000U);
        if (saved) {
            esp_restart();
        }
        ESP_LOGW(TAG, "code=UNPROVISIONED relay=off");
        for (;;) {
            gateway_relay_force_off();
            vTaskDelay(pdMS_TO_TICKS(1000));
        }
    }

    sample_queue = xQueueCreateStatic(32U, sizeof(gateway_sample_t), sample_queue_storage,
                                      &sample_queue_state);
    telemetry_queue = xQueueCreateStatic(8U, sizeof(iiot_telemetry_t), telemetry_queue_storage,
                                         &telemetry_queue_state);
    command_queue = xQueueCreateStatic(4U, sizeof(command_input_t), command_queue_storage,
                                       &command_queue_state);
    offline_mutex = xSemaphoreCreateMutexStatic(&offline_mutex_state);
    if (sample_queue == NULL || telemetry_queue == NULL || command_queue == NULL ||
        offline_mutex == NULL) {
        ESP_LOGE(TAG, "code=STATIC_RESOURCE_INIT_FAILED relay=off");
        abort();
    }
    if (!gateway_offline_load(&offline_queue, config.offline_capacity)) {
        ESP_LOGE(TAG, "code=OFFLINE_QUEUE_LOAD_FAILED");
    }
    const esp_timer_create_args_t relay_timer_args = {
        .callback = relay_timeout,
        .name = "relay_auto_off",
    };
    ESP_ERROR_CHECK(esp_timer_create(&relay_timer_args, &relay_timer));
    const esp_err_t sensor_result = gateway_sensors_init();
    if (sensor_result != ESP_OK) {
        ESP_LOGE(TAG, "code=SENSOR_INIT_FAILED error=%s", esp_err_to_name(sensor_result));
    }
    const esp_err_t network_result = gateway_network_start(&config, mqtt_command_received);
    if (network_result != ESP_OK) {
        ESP_LOGE(TAG, "code=NETWORK_INIT_FAILED error=%s", esp_err_to_name(network_result));
    }

    (void)xTaskCreateStaticPinnedToCore(sampling_task, "sampling", sizeof(sampling_stack) /
                                           sizeof(sampling_stack[0]),
                                       NULL, 8U, sampling_stack, &sampling_task_state, 1);
    (void)xTaskCreateStaticPinnedToCore(aggregation_task, "aggregation",
                                       sizeof(aggregation_stack) / sizeof(aggregation_stack[0]),
                                       NULL, 7U, aggregation_stack, &aggregation_task_state, 1);
    (void)xTaskCreateStaticPinnedToCore(
        communication_task, "communication",
        sizeof(communication_stack) / sizeof(communication_stack[0]), NULL, 6U,
        communication_stack, &communication_task_state, 0);
    (void)xTaskCreateStaticPinnedToCore(command_task, "commands",
                                       sizeof(command_stack) / sizeof(command_stack[0]), NULL,
                                       7U, command_stack, &command_task_state, 0);
    (void)xTaskCreateStaticPinnedToCore(health_task, "health",
                                       sizeof(health_stack) / sizeof(health_stack[0]), NULL, 4U,
                                       health_stack, &health_task_state, 0);
    if (network_result == ESP_OK) {
        (void)xTaskCreateStaticPinnedToCore(
            network_task, "network", sizeof(network_stack) / sizeof(network_stack[0]), NULL,
            5U, network_stack, &network_task_state, 0);
    }
    (void)xTaskCreateStaticPinnedToCore(stability_task, "stability",
                                       sizeof(stability_stack) / sizeof(stability_stack[0]), NULL,
                                       1U, stability_stack, &stability_task_state, 0);
    ESP_LOGI(TAG, "code=GATEWAY_STARTED version=%s relay=off simulated=%s",
             firmware_version(),
#if CONFIG_IIOT_SIMULATION
             "true"
#else
             "false"
#endif
    );
}
