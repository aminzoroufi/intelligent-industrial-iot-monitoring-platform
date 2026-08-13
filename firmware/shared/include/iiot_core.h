/*
 * SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
 * SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
 */
#ifndef IIOT_CORE_H
#define IIOT_CORE_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define IIOT_CONFIG_MAGIC UINT32_C(0x49494f54)
#define IIOT_CONFIG_SCHEMA_VERSION 1U
#define IIOT_TOPIC_MAX 192U
#define IIOT_JSON_MAX 1536U
#define IIOT_OFFLINE_CAPACITY_MAX 32U
#define IIOT_ID_MAX 63U

typedef enum {
    IIOT_SENSOR_GOOD = 0,
    IIOT_SENSOR_MISSING,
    IIOT_SENSOR_STUCK,
    IIOT_SENSOR_OUT_OF_RANGE,
    IIOT_SENSOR_NOISY,
    IIOT_SENSOR_RATE_INVALID,
    IIOT_SENSOR_DRIVER_ERROR,
} iiot_sensor_status_t;

typedef enum {
    IIOT_THRESHOLD_NORMAL = 0,
    IIOT_THRESHOLD_WARNING,
    IIOT_THRESHOLD_CRITICAL,
} iiot_threshold_state_t;

typedef enum {
    IIOT_FAULT_NONE = 0,
    IIOT_FAULT_TEMPERATURE_SENSOR = 1U << 0,
    IIOT_FAULT_CURRENT_SENSOR = 1U << 1,
    IIOT_FAULT_VIBRATION_SENSOR = 1U << 2,
    IIOT_FAULT_MODBUS = 1U << 3,
    IIOT_FAULT_CONFIG_FALLBACK = 1U << 4,
    IIOT_FAULT_OFFLINE_QUEUE_DROP = 1U << 5,
    IIOT_FAULT_REBOOT_LOOP_GUARD = 1U << 6,
} iiot_fault_flags_t;

typedef struct {
    float warning;
    float critical;
    float hysteresis_percent;
} iiot_thresholds_t;

typedef struct {
    uint32_t magic;
    uint16_t schema_version;
    uint16_t struct_size;
    uint32_t generation;
    char site_id[IIOT_ID_MAX + 1U];
    char device_id[IIOT_ID_MAX + 1U];
    char wifi_ssid[33];
    char wifi_password[65];
    char mqtt_host[128];
    uint16_t mqtt_port;
    uint16_t sample_interval_ms;
    uint16_t telemetry_interval_ms;
    uint8_t offline_capacity;
    uint8_t reserved;
    iiot_thresholds_t temperature;
    iiot_thresholds_t vibration;
    iiot_thresholds_t current;
    uint32_t checksum;
} iiot_config_t;

typedef struct {
    char site_id[IIOT_ID_MAX + 1U];
    char device_id[IIOT_ID_MAX + 1U];
    uint16_t sample_interval_ms;
    uint16_t telemetry_interval_ms;
    float temperature_warning_c;
    float temperature_critical_c;
} iiot_config_v0_t;

typedef struct {
    iiot_sensor_status_t status;
    uint16_t valid_samples;
    uint16_t expected_samples;
} iiot_sample_quality_t;

typedef struct {
    double temperature_sum;
    double current_sum;
    double vibration_square_sum;
    float vibration_peak_mps2;
    uint16_t temperature_valid;
    uint16_t current_valid;
    uint16_t vibration_valid;
    uint16_t expected_samples;
    iiot_sensor_status_t temperature_status;
    iiot_sensor_status_t current_status;
    iiot_sensor_status_t vibration_status;
} iiot_sample_window_t;

typedef struct {
    float temperature_c;
    float current_a;
    float vibration_rms_mps2;
    float vibration_peak_mps2;
    float vibration_crest_factor;
    iiot_sample_quality_t temperature_quality;
    iiot_sample_quality_t current_quality;
    iiot_sample_quality_t vibration_quality;
} iiot_measurements_t;

typedef struct {
    char message_id[37];
    char site_id[IIOT_ID_MAX + 1U];
    char device_id[IIOT_ID_MAX + 1U];
    char firmware_version[49];
    char device_time[32];
    uint64_t sequence;
    uint64_t uptime_ms;
    bool clock_synchronized;
    bool replayed;
    iiot_measurements_t measurements;
    uint32_t fault_flags;
} iiot_telemetry_t;

typedef struct {
    iiot_telemetry_t records[IIOT_OFFLINE_CAPACITY_MAX];
    uint32_t dropped_message_count;
    uint8_t head;
    uint8_t count;
    uint8_t capacity;
} iiot_offline_queue_t;

uint32_t iiot_crc32(const void *data, size_t length);
void iiot_config_defaults(iiot_config_t *config);
void iiot_config_finalize(iiot_config_t *config);
bool iiot_config_validate(const iiot_config_t *config, char *error, size_t error_size);
bool iiot_config_migrate_v0(const iiot_config_v0_t *old_config, iiot_config_t *config);

void iiot_sample_window_begin(iiot_sample_window_t *window, uint16_t expected_samples);
void iiot_sample_window_add(iiot_sample_window_t *window, float temperature_c,
                            iiot_sensor_status_t temperature_status, float current_a,
                            iiot_sensor_status_t current_status, float vibration_mps2,
                            iiot_sensor_status_t vibration_status);
iiot_measurements_t iiot_sample_window_finish(const iiot_sample_window_t *window);

iiot_threshold_state_t iiot_threshold_update(const iiot_thresholds_t *thresholds,
                                             iiot_threshold_state_t previous, float value,
                                             bool sample_valid);
uint32_t iiot_reconnect_delay_ms(uint8_t attempt, uint32_t jitter_value);

void iiot_offline_queue_init(iiot_offline_queue_t *queue, uint8_t capacity);
bool iiot_offline_queue_push(iiot_offline_queue_t *queue,
                             const iiot_telemetry_t *telemetry);
bool iiot_offline_queue_peek(const iiot_offline_queue_t *queue,
                             iiot_telemetry_t *telemetry);
bool iiot_offline_queue_pop(iiot_offline_queue_t *queue, iiot_telemetry_t *telemetry);

bool iiot_make_topic(char *output, size_t output_size, const char *site_id,
                     const char *device_id, const char *suffix);
bool iiot_serialize_telemetry(const iiot_telemetry_t *telemetry, char *output,
                             size_t output_size);
const char *iiot_sensor_status_name(iiot_sensor_status_t status);

#ifdef __cplusplus
}
#endif

#endif
