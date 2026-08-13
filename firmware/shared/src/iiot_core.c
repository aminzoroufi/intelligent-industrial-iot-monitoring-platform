/*
 * SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
 * SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
 */
#include "iiot_core.h"

#include <math.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>

static bool identifier_is_valid(const char *value) {
    const size_t length = strnlen(value, IIOT_ID_MAX + 1U);
    if (length == 0U || length > IIOT_ID_MAX) {
        return false;
    }
    for (size_t index = 0; index < length; ++index) {
        const char character = value[index];
        const bool allowed = (character >= 'a' && character <= 'z') ||
                             (character >= '0' && character <= '9') || character == '-';
        if (!allowed || (index == 0U && character == '-')) {
            return false;
        }
    }
    return true;
}

static void set_error(char *error, size_t error_size, const char *message) {
    if (error != NULL && error_size > 0U) {
        (void)snprintf(error, error_size, "%s", message);
    }
}

static bool thresholds_are_valid(const iiot_thresholds_t *thresholds, float minimum,
                                 float maximum) {
    return isfinite(thresholds->warning) && isfinite(thresholds->critical) &&
           thresholds->warning >= minimum && thresholds->critical <= maximum &&
           thresholds->warning < thresholds->critical &&
           thresholds->hysteresis_percent >= 1.0F &&
           thresholds->hysteresis_percent <= 25.0F;
}

uint32_t iiot_crc32(const void *data, size_t length) {
    const uint8_t *bytes = data;
    uint32_t crc = UINT32_C(0xffffffff);
    for (size_t index = 0; index < length; ++index) {
        crc ^= bytes[index];
        for (uint8_t bit = 0; bit < 8U; ++bit) {
            const uint32_t mask = (uint32_t)(-(int32_t)(crc & 1U));
            crc = (crc >> 1U) ^ (UINT32_C(0xedb88320) & mask);
        }
    }
    return ~crc;
}

void iiot_config_defaults(iiot_config_t *config) {
    memset(config, 0, sizeof(*config));
    config->magic = IIOT_CONFIG_MAGIC;
    config->schema_version = IIOT_CONFIG_SCHEMA_VERSION;
    config->struct_size = (uint16_t)sizeof(*config);
    config->generation = 1U;
    (void)snprintf(config->site_id, sizeof(config->site_id), "workshop-demo");
    (void)snprintf(config->device_id, sizeof(config->device_id), "motor-01");
    (void)snprintf(config->mqtt_host, sizeof(config->mqtt_host), "192.168.4.2");
    config->mqtt_port = 1883U;
    config->sample_interval_ms = 100U;
    config->telemetry_interval_ms = 1000U;
    config->offline_capacity = IIOT_OFFLINE_CAPACITY_MAX;
    config->temperature = (iiot_thresholds_t){60.0F, 75.0F, 5.0F};
    config->vibration = (iiot_thresholds_t){4.5F, 7.0F, 10.0F};
    config->current = (iiot_thresholds_t){1.2F, 1.8F, 10.0F};
    iiot_config_finalize(config);
}

void iiot_config_finalize(iiot_config_t *config) {
    config->magic = IIOT_CONFIG_MAGIC;
    config->schema_version = IIOT_CONFIG_SCHEMA_VERSION;
    config->struct_size = (uint16_t)sizeof(*config);
    config->checksum = iiot_crc32(config, offsetof(iiot_config_t, checksum));
}

bool iiot_config_validate(const iiot_config_t *config, char *error, size_t error_size) {
    if (config == NULL) {
        set_error(error, error_size, "CONFIG_NULL");
        return false;
    }
    if (config->magic != IIOT_CONFIG_MAGIC ||
        config->schema_version != IIOT_CONFIG_SCHEMA_VERSION ||
        config->struct_size != sizeof(*config)) {
        set_error(error, error_size, "CONFIG_SCHEMA_INVALID");
        return false;
    }
    if (config->checksum != iiot_crc32(config, offsetof(iiot_config_t, checksum))) {
        set_error(error, error_size, "CONFIG_CHECKSUM_INVALID");
        return false;
    }
    if (!identifier_is_valid(config->site_id) || !identifier_is_valid(config->device_id)) {
        set_error(error, error_size, "CONFIG_ID_INVALID");
        return false;
    }
    if (strnlen(config->mqtt_host, sizeof(config->mqtt_host)) == 0U ||
        strnlen(config->mqtt_host, sizeof(config->mqtt_host)) >= sizeof(config->mqtt_host) ||
        config->mqtt_port == 0U) {
        set_error(error, error_size, "CONFIG_MQTT_INVALID");
        return false;
    }
    if (config->sample_interval_ms < 10U || config->sample_interval_ms > 1000U ||
        config->telemetry_interval_ms < config->sample_interval_ms ||
        config->telemetry_interval_ms > 60000U ||
        config->telemetry_interval_ms % config->sample_interval_ms != 0U) {
        set_error(error, error_size, "CONFIG_TIMING_INVALID");
        return false;
    }
    if (config->offline_capacity == 0U ||
        config->offline_capacity > IIOT_OFFLINE_CAPACITY_MAX) {
        set_error(error, error_size, "CONFIG_QUEUE_INVALID");
        return false;
    }
    if (!thresholds_are_valid(&config->temperature, -80.0F, 200.0F) ||
        !thresholds_are_valid(&config->vibration, 0.0F, 2000.0F) ||
        !thresholds_are_valid(&config->current, 0.0F, 10.0F)) {
        set_error(error, error_size, "CONFIG_THRESHOLDS_INVALID");
        return false;
    }
    set_error(error, error_size, "OK");
    return true;
}

bool iiot_config_migrate_v0(const iiot_config_v0_t *old_config, iiot_config_t *config) {
    if (old_config == NULL || config == NULL || !identifier_is_valid(old_config->site_id) ||
        !identifier_is_valid(old_config->device_id)) {
        return false;
    }
    iiot_config_defaults(config);
    (void)snprintf(config->site_id, sizeof(config->site_id), "%s", old_config->site_id);
    (void)snprintf(config->device_id, sizeof(config->device_id), "%s", old_config->device_id);
    config->sample_interval_ms = old_config->sample_interval_ms;
    config->telemetry_interval_ms = old_config->telemetry_interval_ms;
    config->temperature.warning = old_config->temperature_warning_c;
    config->temperature.critical = old_config->temperature_critical_c;
    config->generation = 1U;
    iiot_config_finalize(config);
    return iiot_config_validate(config, NULL, 0U);
}

static iiot_sensor_status_t merge_status(iiot_sensor_status_t current,
                                         iiot_sensor_status_t next) {
    return next > current ? next : current;
}

void iiot_sample_window_begin(iiot_sample_window_t *window, uint16_t expected_samples) {
    memset(window, 0, sizeof(*window));
    window->expected_samples = expected_samples == 0U ? 1U : expected_samples;
}

void iiot_sample_window_add(iiot_sample_window_t *window, float temperature_c,
                            iiot_sensor_status_t temperature_status, float current_a,
                            iiot_sensor_status_t current_status, float vibration_mps2,
                            iiot_sensor_status_t vibration_status) {
    if (temperature_status == IIOT_SENSOR_GOOD && isfinite(temperature_c) &&
        temperature_c >= -80.0F && temperature_c <= 200.0F) {
        window->temperature_sum += temperature_c;
        ++window->temperature_valid;
    } else {
        if (temperature_status == IIOT_SENSOR_GOOD) {
            temperature_status = IIOT_SENSOR_OUT_OF_RANGE;
        }
        window->temperature_status = merge_status(window->temperature_status, temperature_status);
    }
    if (current_status == IIOT_SENSOR_GOOD && isfinite(current_a) && current_a >= -0.1F &&
        current_a <= 10.0F) {
        window->current_sum += current_a;
        ++window->current_valid;
    } else {
        if (current_status == IIOT_SENSOR_GOOD) {
            current_status = IIOT_SENSOR_OUT_OF_RANGE;
        }
        window->current_status = merge_status(window->current_status, current_status);
    }
    if (vibration_status == IIOT_SENSOR_GOOD && isfinite(vibration_mps2) &&
        fabsf(vibration_mps2) <= 4000.0F) {
        window->vibration_square_sum += (double)vibration_mps2 * (double)vibration_mps2;
        const float absolute = fabsf(vibration_mps2);
        if (absolute > window->vibration_peak_mps2) {
            window->vibration_peak_mps2 = absolute;
        }
        ++window->vibration_valid;
    } else {
        if (vibration_status == IIOT_SENSOR_GOOD) {
            vibration_status = IIOT_SENSOR_OUT_OF_RANGE;
        }
        window->vibration_status = merge_status(window->vibration_status, vibration_status);
    }
}

static iiot_sample_quality_t quality(iiot_sensor_status_t status, uint16_t valid,
                                     uint16_t expected) {
    if (status == IIOT_SENSOR_GOOD && valid < expected) {
        status = IIOT_SENSOR_MISSING;
    }
    return (iiot_sample_quality_t){status, valid, expected};
}

iiot_measurements_t iiot_sample_window_finish(const iiot_sample_window_t *window) {
    iiot_measurements_t result = {0};
    result.temperature_c = window->temperature_valid > 0U
                               ? (float)(window->temperature_sum / window->temperature_valid)
                               : NAN;
    result.current_a = window->current_valid > 0U
                           ? (float)(window->current_sum / window->current_valid)
                           : NAN;
    result.vibration_rms_mps2 =
        window->vibration_valid > 0U
            ? sqrtf((float)(window->vibration_square_sum / window->vibration_valid))
            : NAN;
    result.vibration_peak_mps2 =
        window->vibration_valid > 0U ? window->vibration_peak_mps2 : NAN;
    result.vibration_crest_factor =
        isfinite(result.vibration_rms_mps2) && result.vibration_rms_mps2 > 0.000001F
            ? result.vibration_peak_mps2 / result.vibration_rms_mps2
            : NAN;
    result.temperature_quality = quality(window->temperature_status, window->temperature_valid,
                                         window->expected_samples);
    result.current_quality = quality(window->current_status, window->current_valid,
                                     window->expected_samples);
    result.vibration_quality = quality(window->vibration_status, window->vibration_valid,
                                       window->expected_samples);
    return result;
}

iiot_threshold_state_t iiot_threshold_update(const iiot_thresholds_t *thresholds,
                                             iiot_threshold_state_t previous, float value,
                                             bool sample_valid) {
    if (!sample_valid || !isfinite(value)) {
        return previous;
    }
    if (value >= thresholds->critical) {
        return IIOT_THRESHOLD_CRITICAL;
    }
    if (previous == IIOT_THRESHOLD_CRITICAL) {
        const float critical_clear =
            thresholds->critical * (1.0F - thresholds->hysteresis_percent / 100.0F);
        if (value >= critical_clear) {
            return IIOT_THRESHOLD_CRITICAL;
        }
    }
    if (value >= thresholds->warning) {
        return IIOT_THRESHOLD_WARNING;
    }
    if (previous != IIOT_THRESHOLD_NORMAL) {
        const float warning_clear =
            thresholds->warning * (1.0F - thresholds->hysteresis_percent / 100.0F);
        if (value >= warning_clear) {
            return IIOT_THRESHOLD_WARNING;
        }
    }
    return IIOT_THRESHOLD_NORMAL;
}

uint32_t iiot_reconnect_delay_ms(uint8_t attempt, uint32_t jitter_value) {
    const uint8_t shift = attempt > 5U ? 5U : attempt;
    const uint32_t base = UINT32_C(1000) << shift;
    const uint32_t bounded = base > UINT32_C(30000) ? UINT32_C(30000) : base;
    return bounded + jitter_value % (bounded / 5U + 1U);
}

void iiot_offline_queue_init(iiot_offline_queue_t *queue, uint8_t capacity) {
    memset(queue, 0, sizeof(*queue));
    queue->capacity =
        capacity == 0U || capacity > IIOT_OFFLINE_CAPACITY_MAX ? IIOT_OFFLINE_CAPACITY_MAX
                                                               : capacity;
}

bool iiot_offline_queue_push(iiot_offline_queue_t *queue,
                             const iiot_telemetry_t *telemetry) {
    bool dropped = false;
    if (queue->count == queue->capacity) {
        queue->head = (uint8_t)((queue->head + 1U) % queue->capacity);
        --queue->count;
        ++queue->dropped_message_count;
        dropped = true;
    }
    const uint8_t tail = (uint8_t)((queue->head + queue->count) % queue->capacity);
    queue->records[tail] = *telemetry;
    ++queue->count;
    return !dropped;
}

bool iiot_offline_queue_peek(const iiot_offline_queue_t *queue,
                             iiot_telemetry_t *telemetry) {
    if (queue->count == 0U) {
        return false;
    }
    *telemetry = queue->records[queue->head];
    return true;
}

bool iiot_offline_queue_pop(iiot_offline_queue_t *queue, iiot_telemetry_t *telemetry) {
    if (!iiot_offline_queue_peek(queue, telemetry)) {
        return false;
    }
    queue->head = (uint8_t)((queue->head + 1U) % queue->capacity);
    --queue->count;
    return true;
}

bool iiot_make_topic(char *output, size_t output_size, const char *site_id,
                     const char *device_id, const char *suffix) {
    if (!identifier_is_valid(site_id) || !identifier_is_valid(device_id) || suffix == NULL) {
        return false;
    }
    const bool known = strcmp(suffix, "telemetry") == 0 || strcmp(suffix, "health") == 0 ||
                       strcmp(suffix, "events") == 0 || strcmp(suffix, "commands") == 0 ||
                       strcmp(suffix, "command-acks") == 0 ||
                       strcmp(suffix, "availability") == 0;
    if (!known) {
        return false;
    }
    const int written = snprintf(output, output_size, "iiot/v1/%s/%s/%s", site_id, device_id,
                                 suffix);
    return written >= 0 && (size_t)written < output_size;
}

const char *iiot_sensor_status_name(iiot_sensor_status_t status) {
    static const char *const names[] = {"good",       "missing", "stuck",
                                        "out_of_range", "noisy",   "rate_invalid",
                                        "driver_error"};
    return status <= IIOT_SENSOR_DRIVER_ERROR ? names[status] : "driver_error";
}

typedef struct {
    char *output;
    size_t capacity;
    size_t used;
    bool valid;
} json_writer_t;

static void append(json_writer_t *writer, const char *format, ...) {
    if (!writer->valid || writer->used >= writer->capacity) {
        writer->valid = false;
        return;
    }
    va_list arguments;
    va_start(arguments, format);
    const int written = vsnprintf(writer->output + writer->used, writer->capacity - writer->used,
                                  format, arguments);
    va_end(arguments);
    if (written < 0 || (size_t)written >= writer->capacity - writer->used) {
        writer->valid = false;
        return;
    }
    writer->used += (size_t)written;
}

static void append_number(json_writer_t *writer, float value) {
    if (isfinite(value)) {
        append(writer, "%.5g", (double)value);
    } else {
        append(writer, "null");
    }
}

static void append_quality(json_writer_t *writer, const char *name,
                           const iiot_sample_quality_t *quality_value, bool trailing) {
    append(writer,
           "\"%s\":{\"status\":\"%s\",\"valid_samples\":%u,"
           "\"expected_samples\":%u}%s",
           name, iiot_sensor_status_name(quality_value->status),
           (unsigned)quality_value->valid_samples, (unsigned)quality_value->expected_samples,
           trailing ? "," : "");
}

static void append_faults(json_writer_t *writer, uint32_t flags) {
    static const struct {
        uint32_t flag;
        const char *name;
    } values[] = {{IIOT_FAULT_TEMPERATURE_SENSOR, "TEMPERATURE_SENSOR_FAULT"},
                  {IIOT_FAULT_CURRENT_SENSOR, "CURRENT_SENSOR_FAULT"},
                  {IIOT_FAULT_VIBRATION_SENSOR, "VIBRATION_SENSOR_FAULT"},
                  {IIOT_FAULT_MODBUS, "MODBUS_FAULT"},
                  {IIOT_FAULT_CONFIG_FALLBACK, "CONFIG_FALLBACK"},
                  {IIOT_FAULT_OFFLINE_QUEUE_DROP, "OFFLINE_QUEUE_DROP"},
                  {IIOT_FAULT_REBOOT_LOOP_GUARD, "REBOOT_LOOP_GUARD"}};
    bool first = true;
    append(writer, "[");
    for (size_t index = 0; index < sizeof(values) / sizeof(values[0]); ++index) {
        if ((flags & values[index].flag) != 0U) {
            append(writer, "%s\"%s\"", first ? "" : ",", values[index].name);
            first = false;
        }
    }
    append(writer, "]");
}

bool iiot_serialize_telemetry(const iiot_telemetry_t *telemetry, char *output,
                             size_t output_size) {
    if (telemetry == NULL || output == NULL || output_size == 0U ||
        !identifier_is_valid(telemetry->site_id) ||
        !identifier_is_valid(telemetry->device_id) || strlen(telemetry->message_id) != 36U) {
        return false;
    }
    json_writer_t writer = {output, output_size, 0U, true};
    append(&writer,
           "{\"schema_version\":1,\"message_id\":\"%s\",\"site_id\":\"%s\","
           "\"device_id\":\"%s\",\"sequence\":%llu,\"device_time\":",
           telemetry->message_id, telemetry->site_id, telemetry->device_id,
           (unsigned long long)telemetry->sequence);
    if (telemetry->clock_synchronized) {
        append(&writer, "\"%s\"", telemetry->device_time);
    } else {
        append(&writer, "null");
    }
    append(&writer,
           ",\"clock_synchronized\":%s,\"uptime_ms\":%llu,"
           "\"firmware_version\":\"%s\",\"quality\":\"",
           telemetry->clock_synchronized ? "true" : "false",
           (unsigned long long)telemetry->uptime_ms, telemetry->firmware_version);
    const bool bad =
        (telemetry->measurements.temperature_quality.status != IIOT_SENSOR_GOOD &&
         telemetry->measurements.temperature_quality.status != IIOT_SENSOR_MISSING) ||
        (telemetry->measurements.current_quality.status != IIOT_SENSOR_GOOD &&
         telemetry->measurements.current_quality.status != IIOT_SENSOR_MISSING) ||
        (telemetry->measurements.vibration_quality.status != IIOT_SENSOR_GOOD &&
         telemetry->measurements.vibration_quality.status != IIOT_SENSOR_MISSING);
    const bool degraded = telemetry->measurements.temperature_quality.status != IIOT_SENSOR_GOOD ||
                          telemetry->measurements.current_quality.status != IIOT_SENSOR_GOOD ||
                          telemetry->measurements.vibration_quality.status != IIOT_SENSOR_GOOD;
    append(&writer, "%s\",\"replayed\":%s,\"measurements\":{\"temperature_c\":",
           bad ? "bad" : degraded ? "degraded" : "good",
           telemetry->replayed ? "true" : "false");
    append_number(&writer, telemetry->measurements.temperature_c);
    append(&writer, ",\"vibration_rms_mps2\":");
    append_number(&writer, telemetry->measurements.vibration_rms_mps2);
    append(&writer, ",\"vibration_peak_mps2\":");
    append_number(&writer, telemetry->measurements.vibration_peak_mps2);
    append(&writer, ",\"vibration_crest_factor\":");
    append_number(&writer, telemetry->measurements.vibration_crest_factor);
    append(&writer, ",\"current_a\":");
    append_number(&writer, telemetry->measurements.current_a);
    append(&writer, "},\"sample_quality\":{");
    append_quality(&writer, "temperature", &telemetry->measurements.temperature_quality, true);
    append_quality(&writer, "vibration", &telemetry->measurements.vibration_quality, true);
    append_quality(&writer, "current", &telemetry->measurements.current_quality, false);
    append(&writer, "},\"fault_flags\":");
    append_faults(&writer, telemetry->fault_flags);
    append(&writer, "}");
    return writer.valid;
}
