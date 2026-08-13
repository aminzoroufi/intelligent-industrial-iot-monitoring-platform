/*
 * SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
 * SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
 */
#include "iiot_core.h"

#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

static void test_configuration(void) {
    iiot_config_t config;
    char error[48];
    iiot_config_defaults(&config);
    assert(iiot_config_validate(&config, error, sizeof(error)));
    assert(strcmp(error, "OK") == 0);

    config.device_id[0] = '-';
    iiot_config_finalize(&config);
    assert(!iiot_config_validate(&config, error, sizeof(error)));
    assert(strcmp(error, "CONFIG_ID_INVALID") == 0);

    iiot_config_defaults(&config);
    config.checksum ^= UINT32_C(1);
    assert(!iiot_config_validate(&config, error, sizeof(error)));
    assert(strcmp(error, "CONFIG_CHECKSUM_INVALID") == 0);

    const iiot_config_v0_t legacy = {"workshop-demo", "motor-01", 100U, 1000U, 55.0F,
                                     72.0F};
    assert(iiot_config_migrate_v0(&legacy, &config));
    assert(config.schema_version == 1U);
    assert(fabsf(config.temperature.warning - 55.0F) < 0.001F);
}

static void test_aggregation(void) {
    iiot_sample_window_t window;
    iiot_sample_window_begin(&window, 4U);
    iiot_sample_window_add(&window, 40.0F, IIOT_SENSOR_GOOD, 0.5F, IIOT_SENSOR_GOOD,
                           1.0F, IIOT_SENSOR_GOOD);
    iiot_sample_window_add(&window, 42.0F, IIOT_SENSOR_GOOD, 0.7F, IIOT_SENSOR_GOOD,
                           -1.0F, IIOT_SENSOR_GOOD);
    iiot_sample_window_add(&window, 44.0F, IIOT_SENSOR_GOOD, 0.9F, IIOT_SENSOR_GOOD,
                           2.0F, IIOT_SENSOR_GOOD);
    iiot_sample_window_add(&window, 300.0F, IIOT_SENSOR_GOOD, NAN, IIOT_SENSOR_DRIVER_ERROR,
                           -2.0F, IIOT_SENSOR_GOOD);
    const iiot_measurements_t result = iiot_sample_window_finish(&window);
    assert(fabsf(result.temperature_c - 42.0F) < 0.001F);
    assert(result.temperature_quality.status == IIOT_SENSOR_OUT_OF_RANGE);
    assert(result.temperature_quality.valid_samples == 3U);
    assert(fabsf(result.current_a - 0.7F) < 0.001F);
    assert(result.current_quality.status == IIOT_SENSOR_DRIVER_ERROR);
    assert(fabsf(result.vibration_rms_mps2 - sqrtf(2.5F)) < 0.001F);
    assert(fabsf(result.vibration_peak_mps2 - 2.0F) < 0.001F);
}

static void test_hysteresis(void) {
    const iiot_thresholds_t thresholds = {10.0F, 20.0F, 10.0F};
    iiot_threshold_state_t state = IIOT_THRESHOLD_NORMAL;
    state = iiot_threshold_update(&thresholds, state, 11.0F, true);
    assert(state == IIOT_THRESHOLD_WARNING);
    state = iiot_threshold_update(&thresholds, state, 9.5F, true);
    assert(state == IIOT_THRESHOLD_WARNING);
    state = iiot_threshold_update(&thresholds, state, 8.9F, true);
    assert(state == IIOT_THRESHOLD_NORMAL);
    state = iiot_threshold_update(&thresholds, state, 22.0F, true);
    assert(state == IIOT_THRESHOLD_CRITICAL);
    state = iiot_threshold_update(&thresholds, state, 18.5F, true);
    assert(state == IIOT_THRESHOLD_CRITICAL);
    state = iiot_threshold_update(&thresholds, state, 17.9F, true);
    assert(state == IIOT_THRESHOLD_WARNING);
    assert(iiot_threshold_update(&thresholds, state, NAN, false) == state);
}

static iiot_telemetry_t telemetry(uint64_t sequence) {
    iiot_telemetry_t value = {0};
    (void)snprintf(value.message_id, sizeof(value.message_id),
                   "00000000-0000-4000-8000-%012llu", (unsigned long long)sequence);
    (void)snprintf(value.site_id, sizeof(value.site_id), "workshop-demo");
    (void)snprintf(value.device_id, sizeof(value.device_id), "motor-01");
    (void)snprintf(value.firmware_version, sizeof(value.firmware_version), "0.1.0");
    value.sequence = sequence;
    value.uptime_ms = sequence * 1000U;
    value.measurements.temperature_c = 42.3F;
    value.measurements.vibration_rms_mps2 = 1.21F;
    value.measurements.vibration_peak_mps2 = 2.88F;
    value.measurements.vibration_crest_factor = 2.3802F;
    value.measurements.current_a = 0.64F;
    value.measurements.temperature_quality =
        (iiot_sample_quality_t){IIOT_SENSOR_GOOD, 10U, 10U};
    value.measurements.vibration_quality =
        (iiot_sample_quality_t){IIOT_SENSOR_GOOD, 10U, 10U};
    value.measurements.current_quality =
        (iiot_sample_quality_t){IIOT_SENSOR_GOOD, 10U, 10U};
    return value;
}

static void test_queue_order_and_loss_policy(void) {
    iiot_offline_queue_t queue;
    iiot_offline_queue_init(&queue, 3U);
    for (uint64_t sequence = 1U; sequence <= 4U; ++sequence) {
        const iiot_telemetry_t item = telemetry(sequence);
        const bool retained_without_drop = iiot_offline_queue_push(&queue, &item);
        assert(retained_without_drop == (sequence <= 3U));
    }
    assert(queue.count == 3U);
    assert(queue.dropped_message_count == 1U);
    for (uint64_t expected = 2U; expected <= 4U; ++expected) {
        iiot_telemetry_t item;
        assert(iiot_offline_queue_pop(&queue, &item));
        assert(item.sequence == expected);
    }
    iiot_telemetry_t empty;
    assert(!iiot_offline_queue_pop(&queue, &empty));
}

static void test_topics_serialization_and_backoff(void) {
    char topic[IIOT_TOPIC_MAX];
    assert(iiot_make_topic(topic, sizeof(topic), "workshop-demo", "motor-01", "telemetry"));
    assert(strcmp(topic, "iiot/v1/workshop-demo/motor-01/telemetry") == 0);
    assert(!iiot_make_topic(topic, sizeof(topic), "Workshop", "motor-01", "telemetry"));
    assert(!iiot_make_topic(topic, sizeof(topic), "workshop-demo", "motor-01", "unknown"));

    iiot_telemetry_t value = telemetry(42U);
    value.fault_flags = IIOT_FAULT_MODBUS | IIOT_FAULT_OFFLINE_QUEUE_DROP;
    char json[IIOT_JSON_MAX];
    assert(iiot_serialize_telemetry(&value, json, sizeof(json)));
    assert(strstr(json, "\"sequence\":42") != NULL);
    assert(strstr(json, "\"device_time\":null") != NULL);
    assert(strstr(json, "\"clock_synchronized\":false") != NULL);
    assert(strstr(json, "\"replayed\":false") != NULL);
    assert(strstr(json, "\"MODBUS_FAULT\"") != NULL);
    assert(strstr(json, "\"OFFLINE_QUEUE_DROP\"") != NULL);
    assert(iiot_reconnect_delay_ms(0U, 0U) == 1000U);
    assert(iiot_reconnect_delay_ms(10U, 0U) == 30000U);
    assert(iiot_reconnect_delay_ms(10U, UINT32_C(999999)) <= 36000U);
}

int main(void) {
    test_configuration();
    test_aggregation();
    test_hysteresis();
    test_queue_order_and_loss_policy();
    test_topics_serialization_and_backoff();
    puts("iiot_core_tests: all checks passed");
    return 0;
}
